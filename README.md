🧹 Desktop Organizer – Windows

One‑click desktop cleanup – automatically moves files, folders, and shortcuts into categorized folders, sorts everything by name, and even deletes itself after running (as `.exe`).



Features

- Smart file sorting by extension (Images, Videos, Music, Documents, Code, Shortcuts, etc.)
- Moves all shortcuts to a `Shortcuts` folder (configurable)
- Collects personal folders into a single `Folders` bucket (contents untouched)
- Cleans folder names (removes unwanted characters, extra spaces)
- Auto‑sorts desktop icons by Name and snaps to grid
- Self‑deletion after completion (when compiled as `.exe`)
- Log file saved on desktop for review



How to Use

Run as Python script
```bash
python organize_desktop.py
```

Build standalone EXE (recommended)
```bash
pip install pyinstaller
pyinstaller --onefile --noconsole organize_desktop.py
```
Place the generated `.exe` on your desktop and run it.  
The program will organize everything and then delete itself.



Customization

Edit these variables at the top of the script:

| Variable | Description |
|----------|-------------|
| `CATEGORIES` | Add/remove extensions and folder names |
| `MOVE_SHORTCUTS` | `True` to move `.lnk`/`.url` files |
| `ORGANIZE_FOLDERS` | `True` to collect personal folders |
| `CLEAN_FOLDER_NAMES` | `True` to clean folder names |



Folders Created on Desktop

```
Images/  Videos/  Music/  Documents/  Spreadsheets/  Presentations/
Archives/  Installers/  Code/  Shortcuts/  Others/  Folders/
```



Requirements

- Windows 7+
- Python 3.6+ (only if running the script)
- No extra libraries required (all standard)



License

MIT – free to use and modify.



Contributions

Issues and pull requests are welcome.



## Support

If this tool helps you, please give it a star ⭐ – thank you!
