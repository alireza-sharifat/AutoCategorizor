import os
import re
import sys
import shutil
import ctypes
import time
import subprocess
from pathlib import Path
from datetime import datetime

CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico", ".heic"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"],
    "Music": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md"],
    "Spreadsheets": [".xls", ".xlsx", ".csv", ".ods"],
    "Presentations": [".ppt", ".pptx", ".odp"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".iso"],
    "Installers": [".exe", ".msi"],
    "Code": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".json", ".xml", ".sql", ".sh", ".bat"],
    "Shortcuts": [".lnk", ".url"],
}

MOVE_SHORTCUTS = True
MISC_FOLDER = "Others"
ORGANIZE_FOLDERS = True
FOLDERS_BUCKET = "Folders"
CLEAN_FOLDER_NAMES = True
_ALLOWED_EXTRA_CHARS = r" \-_()."

def clean_folder_name(name):
    original = name
    pattern = r"[^\w" + re.escape(_ALLOWED_EXTRA_CHARS) + r"]"
    cleaned = re.sub(pattern, "", name, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"_{2,}", "_", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    cleaned = cleaned.strip(" .-_")
    return cleaned if cleaned else original

def get_desktop_path():
    CSIDL_DESKTOPDIRECTORY = 0x10
    SHGFP_TYPE_CURRENT = 0
    buf = ctypes.create_unicode_buffer(1024)
    ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOPDIRECTORY, None, SHGFP_TYPE_CURRENT, buf)
    return Path(buf.value)

def get_category(ext):
    ext = ext.lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return MISC_FOLDER

def unique_destination(folder, filename):
    target = folder / filename
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    counter = 1
    while True:
        new_name = f"{stem} ({counter}){suffix}"
        new_target = folder / new_name
        if not new_target.exists():
            return new_target
        counter += 1

def organize_files(desktop, protected_folders, exclude_paths, log):
    moved = 0
    for item in list(desktop.iterdir()):
        if item.is_dir():
            continue
        if item.name.lower() in ("desktop.ini", "thumbs.db"):
            continue
        if item.resolve() in exclude_paths:
            log.append(f"  Skipped: {item.name}")
            continue

        ext = item.suffix.lower()
        if ext in (".lnk", ".url") and not MOVE_SHORTCUTS:
            continue

        category = get_category(ext)
        dest = desktop / category if category in protected_folders else desktop / MISC_FOLDER
        dest.mkdir(exist_ok=True)
        dest_path = unique_destination(dest, item.name)

        try:
            shutil.move(str(item), str(dest_path))
            moved += 1
            log.append(f"  Moved: {item.name} -> {dest.name}/")
        except Exception as e:
            log.append(f"  Error: {item.name} - {e}")
    return moved

def unique_destination_dir(parent, name):
    target = parent / name
    if not target.exists():
        return target
    counter = 1
    while True:
        new_target = parent / f"{name} ({counter})"
        if not new_target.exists():
            return new_target
        counter += 1

def organize_folders(desktop, protected_folders, exclude_paths, log):
    if not ORGANIZE_FOLDERS:
        return 0
    moved = 0
    bucket = desktop / FOLDERS_BUCKET
    for item in list(desktop.iterdir()):
        if not item.is_dir():
            continue
        if item.name in protected_folders:
            continue
        if item.resolve() in exclude_paths:
            log.append(f"  Skipped folder: {item.name}")
            continue

        new_name = clean_folder_name(item.name) if CLEAN_FOLDER_NAMES else item.name
        bucket.mkdir(exist_ok=True)
        dest = unique_destination_dir(bucket, new_name)

        try:
            shutil.move(str(item), str(dest))
            moved += 1
            if new_name != item.name:
                log.append(f"  Folder moved & renamed: {item.name} -> {FOLDERS_BUCKET}/{dest.name}")
            else:
                log.append(f"  Folder moved: {item.name} -> {FOLDERS_BUCKET}/")
        except Exception as e:
            log.append(f"  Error moving folder {item.name}: {e}")
    return moved

def sort_desktop_by_name():
    try:
        user32 = ctypes.windll.user32
        progman = user32.FindWindowW("Progman", None)
        defview = user32.FindWindowExW(progman, 0, "SHELLDLL_DefView", None)

        if not defview:
            def enum_callback(hwnd, lparam):
                nonlocal defview
                inner = user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
                if inner:
                    defview = inner
                    return False
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

        if not defview:
            return

        listview = user32.FindWindowExW(defview, 0, "SysListView32", None)
        if not listview:
            return

        def compare_func(lParam1, lParam2, lParamSort):
            buf1 = ctypes.create_unicode_buffer(256)
            buf2 = ctypes.create_unicode_buffer(256)
            LVM_GETITEMTEXT = 0x102D
            LVIF_TEXT = 0x0001

            class LVITEM(ctypes.Structure):
                _fields_ = [
                    ("mask", ctypes.c_uint),
                    ("iItem", ctypes.c_int),
                    ("iSubItem", ctypes.c_int),
                    ("state", ctypes.c_uint),
                    ("stateMask", ctypes.c_uint),
                    ("pszText", ctypes.c_wchar_p),
                    ("cchTextMax", ctypes.c_int),
                    ("iImage", ctypes.c_int),
                    ("lParam", ctypes.c_long),
                    ("iIndent", ctypes.c_int),
                ]

            item1 = LVITEM()
            item1.mask = LVIF_TEXT
            item1.iItem = lParam1
            item1.iSubItem = 0
            item1.pszText = buf1
            item1.cchTextMax = 255
            item2 = LVITEM()
            item2.mask = LVIF_TEXT
            item2.iItem = lParam2
            item2.iSubItem = 0
            item2.pszText = buf2
            item2.cchTextMax = 255

            user32.SendMessageW(listview, LVM_GETITEMTEXT, lParam1, ctypes.byref(item1))
            user32.SendMessageW(listview, LVM_GETITEMTEXT, lParam2, ctypes.byref(item2))

            name1, name2 = buf1.value.lower(), buf2.value.lower()
            return -1 if name1 < name2 else 1 if name1 > name2 else 0

        LVM_SORTITEMSEX = 0x1051
        COMPAREFUNC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_long, ctypes.c_long, ctypes.c_long)
        cmp_func = COMPAREFUNC(compare_func)
        user32.SendMessageW(listview, LVM_SORTITEMSEX, 0, cmp_func)
    except:
        pass

def refresh_desktop():
    try:
        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32

        sort_desktop_by_name()

        progman = user32.FindWindowW("Progman", None)
        defview = user32.FindWindowExW(progman, 0, "SHELLDLL_DefView", None)
        if not defview:
            def enum_callback(hwnd, lparam):
                nonlocal defview
                inner = user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
                if inner:
                    defview = inner
                    return False
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

        if defview:
            listview = user32.FindWindowExW(defview, 0, "SysListView32", None)
            if listview:
                LVM_FIRST = 0x1000
                LVM_ARRANGE = LVM_FIRST + 22
                LVA_SNAPTOGRID = 5
                user32.SendMessageW(listview, LVM_ARRANGE, LVA_SNAPTOGRID, 0)
                user32.SendMessageW(defview, 0x0111, 0x7031, 0)
                time.sleep(0.3)
                user32.SendMessageW(listview, LVM_ARRANGE, LVA_SNAPTOGRID, 0)
                user32.SendMessageW(defview, 0x0111, 0x7031, 0)

        desktop_path = str(get_desktop_path())
        SHCNE_UPDATEDIR = 0x00002000
        SHCNF_PATHW = 0x0005
        shell32.SHChangeNotify(SHCNE_UPDATEDIR, SHCNF_PATHW, desktop_path, None)
        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_IDLIST = 0x0000
        shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)

        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SPI_SETDESKWALLPAPER = 0x0014
        user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, SPI_SETDESKWALLPAPER, 0)
        time.sleep(0.2)
        shell32.SHChangeNotify(SHCNE_UPDATEDIR, SHCNF_PATHW, desktop_path, None)
    except:
        pass

def delete_self(script_path):
    try:
        if script_path.suffix.lower() != '.exe':
            return
        desktop = get_desktop_path()
        batch_path = desktop / "delete_organizer.bat"
        with open(batch_path, "w", encoding="utf-8") as f:
            f.write(f"@echo off\n")
            f.write(f"timeout /t 2 /nobreak > nul\n")
            f.write(f"del /f /q \"{script_path}\"\n")
            f.write(f"del /f /q \"{batch_path}\"\n")
        subprocess.Popen(str(batch_path), shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except:
        pass

def show_message(title, msg):
    ctypes.windll.user32.MessageBoxW(0, msg, title, 0x40 | 0x0)

def main():
    if sys.platform != "win32":
        print("Only Windows is supported.")
        input("Press Enter to exit...")
        return

    desktop = get_desktop_path()
    script_path = Path(sys.argv[0]).resolve()

    exclude_paths = {script_path}
    if script_path.parent != desktop and script_path.parent.parent == desktop:
        exclude_paths.add(script_path.parent)

    log = [f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
    log.append(f"Desktop: {desktop}")
    log.append(f"Excluded: {[str(p) for p in exclude_paths]}")
    log.append("")

    protected = set(CATEGORIES.keys()) | {MISC_FOLDER, FOLDERS_BUCKET}

    log.append("Files:")
    moved_files = organize_files(desktop, protected, exclude_paths, log)

    log.append("")
    log.append("Folders:")
    moved_folders = organize_folders(desktop, protected, exclude_paths, log)

    refresh_desktop()

    log.append("")
    log.append(f"Done. Files: {moved_files}, Folders: {moved_folders}")

    print("\n".join(log))

    try:
        log_path = desktop / "organize_log.txt"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n\n")
    except:
        pass

    show_message(
        "Desktop Organizer",
        f"Desktop organized!\nFiles: {moved_files}\nFolders: {moved_folders}\n\nLog saved.\nSelf-deleting now."
    )

    delete_self(script_path)

if __name__ == "__main__":
    main()
