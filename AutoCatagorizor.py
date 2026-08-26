"""
Desktop Organizer - Auto Delete After Run
-----------------------------------------
- Moves all files (including shortcuts) to category folders.
- Sorts desktop by Name.
- Deletes itself after completion (if run as .exe).
"""

import os
import re
import sys
import shutil
import ctypes
import time
import subprocess
from pathlib import Path
from datetime import datetime

# -------------------------------------------------------------------
# Settings
# -------------------------------------------------------------------
CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp",
               ".tiff", ".ico", ".heic"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"],
    "Music": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md"],
    "Spreadsheets": [".xls", ".xlsx", ".csv", ".ods"],
    "Presentations": [".ppt", ".pptx", ".odp"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".iso"],
    "Installers": [".exe", ".msi"],
    "Code": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".json",
             ".xml", ".sql", ".sh", ".bat"],
    "Shortcuts": [".lnk", ".url"],
}

MOVE_SHORTCUTS = True          # All shortcuts go to "Shortcuts" folder
MISC_FOLDER = "Others"
ORGANIZE_FOLDERS = True
FOLDERS_BUCKET = "Folders"
CLEAN_FOLDER_NAMES = True

_ALLOWED_EXTRA_CHARS = r" \-_()."


def clean_folder_name(name: str) -> str:
    original = name
    pattern = r"[^\w" + re.escape(_ALLOWED_EXTRA_CHARS) + r"]"
    cleaned = re.sub(pattern, "", name, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"_{2,}", "_", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    cleaned = cleaned.strip(" .-_")
    return cleaned if cleaned else original


def get_desktop_path() -> Path:
    CSIDL_DESKTOPDIRECTORY = 0x10
    SHGFP_TYPE_CURRENT = 0
    buf = ctypes.create_unicode_buffer(1024)
    ctypes.windll.shell32.SHGetFolderPathW(
        None, CSIDL_DESKTOPDIRECTORY, None, SHGFP_TYPE_CURRENT, buf
    )
    return Path(buf.value)


def get_category_for_extension(ext: str) -> str:
    ext = ext.lower()
    for category, extensions in CATEGORIES.items():
        if ext in extensions:
            return category
    return MISC_FOLDER


def unique_destination(dest_folder: Path, filename: str) -> Path:
    target = dest_folder / filename
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    counter = 1
    while True:
        new_name = f"{stem} ({counter}){suffix}"
        new_target = dest_folder / new_name
        if not new_target.exists():
            return new_target
        counter += 1


def organize_files(desktop: Path, protected_folder_names: set,
                   exclude_paths: set, log_lines: list) -> int:
    moved_count = 0
    for item in list(desktop.iterdir()):
        if item.is_dir():
            continue
        if item.name.lower() in ("desktop.ini", "thumbs.db"):
            continue
        if item.resolve() in exclude_paths:
            log_lines.append(f"  Skipped (running script): {item.name}")
            continue

        ext = item.suffix.lower()
        if ext in (".lnk", ".url") and not MOVE_SHORTCUTS:
            continue

        category = get_category_for_extension(ext)
        dest_folder = desktop / category if category in protected_folder_names else desktop / MISC_FOLDER
        dest_folder.mkdir(exist_ok=True)
        destination = unique_destination(dest_folder, item.name)

        try:
            shutil.move(str(item), str(destination))
            moved_count += 1
            log_lines.append(f"  Moved: {item.name}  ->  {dest_folder.name}/")
        except Exception as e:
            log_lines.append(f"  Error moving {item.name}: {e}")

    return moved_count


def unique_destination_dir(dest_parent: Path, name: str) -> Path:
    target = dest_parent / name
    if not target.exists():
        return target
    counter = 1
    while True:
        new_target = dest_parent / f"{name} ({counter})"
        if not new_target.exists():
            return new_target
        counter += 1


def organize_folders(desktop: Path, protected_folder_names: set,
                     exclude_paths: set, log_lines: list) -> int:
    if not ORGANIZE_FOLDERS:
        return 0
    moved_count = 0
    bucket = desktop / FOLDERS_BUCKET
    for item in list(desktop.iterdir()):
        if not item.is_dir():
            continue
        if item.name in protected_folder_names:
            continue
        if item.resolve() in exclude_paths:
            log_lines.append(f"  Skipped folder (contains running script): {item.name}")
            continue

        new_name = clean_folder_name(item.name) if CLEAN_FOLDER_NAMES else item.name
        bucket.mkdir(exist_ok=True)
        destination = unique_destination_dir(bucket, new_name)

        try:
            shutil.move(str(item), str(destination))
            moved_count += 1
            if new_name != item.name:
                log_lines.append(f"  Folder moved and renamed: {item.name}  ->  {FOLDERS_BUCKET}/{destination.name}")
            else:
                log_lines.append(f"  Folder moved: {item.name}  ->  {FOLDERS_BUCKET}/")
        except Exception as e:
            log_lines.append(f"  Error moving folder {item.name}: {e}")

    return moved_count


def sort_desktop_by_name():
    """Sort desktop icons by Name (equivalent to right-click → Sort by → Name)."""
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

        # Use LVM_SORTITEMSEX with a simple case-insensitive name compare
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

            name1 = buf1.value.lower()
            name2 = buf2.value.lower()
            if name1 < name2:
                return -1
            elif name1 > name2:
                return 1
            return 0

        LVM_SORTITEMSEX = 0x1051
        COMPAREFUNC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_long, ctypes.c_long, ctypes.c_long)
        cmp_func = COMPAREFUNC(compare_func)
        user32.SendMessageW(listview, LVM_SORTITEMSEX, 0, cmp_func)

    except Exception:
        pass


def refresh_desktop_icons():
    """Full refresh: sort by name, arrange to grid, and notify Explorer."""
    try:
        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32

        # 1) Sort by Name
        sort_desktop_by_name()

        # 2) Arrange to grid (twice)
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
                user32.SendMessageW(defview, 0x0111, 0x7031, 0)  # F5
                time.sleep(0.3)
                user32.SendMessageW(listview, LVM_ARRANGE, LVA_SNAPTOGRID, 0)
                user32.SendMessageW(defview, 0x0111, 0x7031, 0)

        # 3) Notify shell
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

    except Exception:
        pass


def delete_self_later(script_path: Path):
    """
    Creates a batch file that waits 2 seconds and then deletes the executable,
    then deletes itself. This runs as a separate process.
    """
    try:
        # Only attempt if the file is an .exe (not .py)
        if script_path.suffix.lower() != '.exe':
            return

        # Create a batch file on the desktop
        desktop = get_desktop_path()
        batch_path = desktop / "delete_organizer.bat"
        with open(batch_path, "w", encoding="utf-8") as f:
            f.write(f"@echo off\n")
            f.write(f"timeout /t 2 /nobreak > nul\n")
            f.write(f"del /f /q \"{script_path}\"\n")
            f.write(f"del /f /q \"{batch_path}\"\n")
        # Run the batch file hidden
        subprocess.Popen(str(batch_path), shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass


def show_result_messagebox(title: str, message: str):
    MB_OK = 0x0
    MB_ICONINFORMATION = 0x40
    ctypes.windll.user32.MessageBoxW(0, message, title, MB_OK | MB_ICONINFORMATION)


def main():
    if sys.platform != "win32":
        print("This program is designed for Windows only.")
        input("Press Enter to exit...")
        return

    desktop = get_desktop_path()
    script_path = Path(sys.argv[0]).resolve()

    # Exclude the script itself (and its parent folder if on desktop)
    exclude_paths = {script_path}
    if script_path.parent != desktop and script_path.parent.parent == desktop:
        exclude_paths.add(script_path.parent)

    log_lines = [f"Desktop organization started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
    log_lines.append(f"Desktop path: {desktop}")
    log_lines.append(f"Excluding from move: {[str(p) for p in exclude_paths]}")
    log_lines.append("")

    protected_folder_names = set(CATEGORIES.keys()) | {MISC_FOLDER, FOLDERS_BUCKET}

    log_lines.append("Organizing files:")
    moved_files = organize_files(desktop, protected_folder_names, exclude_paths, log_lines)

    log_lines.append("")
    log_lines.append("Organizing folders:")
    moved_folders = organize_folders(desktop, protected_folder_names, exclude_paths, log_lines)

    # Refresh and sort desktop
    refresh_desktop_icons()

    log_lines.append("")
    log_lines.append(f"Done. Files moved: {moved_files} | Folders moved: {moved_folders}")

    print("\n".join(log_lines))

    try:
        log_path = desktop / "organize_log.txt"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(log_lines) + "\n\n")
    except Exception:
        pass

    # Show completion message
    show_result_messagebox(
        "Desktop Organizer",
        f"Desktop organized!\n\n"
        f"Files moved: {moved_files}\n"
        f"Folders moved: {moved_folders}\n\n"
        f"Log saved to organize_log.txt\n"
        f"The program will delete itself now."
    )

    # Schedule self-deletion (only works for .exe)
    delete_self_later(script_path)


if __name__ == "__main__":
    main()