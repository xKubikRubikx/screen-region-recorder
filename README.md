# 🎬 Screen Region Recorder

> **Screenshot, but for video.** Select any screen area → record to MP4 → save or share. One hotkey, zero bloat.

![Windows](https://img.shields.io/badge/platform-Windows%2010%2F11-blue?logo=windows)
![Python](https://img.shields.io/badge/python-3.11+-yellow?logo=python)
![License](https://img.shields.io/badge/license-MIT-green)
![FFmpeg](https://img.shields.io/badge/powered%20by-FFmpeg-orange?logo=ffmpeg)

⭐ **If you find this useful, please star the repo — it helps others discover it!**

---

## ✨ Features

- **Region selection** — draw a rectangle on your screen to define the capture area
- **MP4 recording** — records directly to MP4 using FFmpeg (H.264 + AAC)
- **System audio capture** — automatically detects Stereo Mix / Virtual Audio Cable
- **Recording indicator** — subtle pulsing red border around the screen while recording (invisible to capture)
- **Save As dialog** — after stopping, pick where to save + copy file/path to clipboard
- **Background operation** — no window, no tray icon, just hotkeys
- **Auto-start with Windows** — configures itself via the Registry on install
- **One-click install/uninstall** — batch scripts handle everything

---

## ⌨️ Hotkeys

| Shortcut | Action |
|---|---|
| `Ctrl+X` | **Cycle**: Select region → Start recording → Stop recording |
| `Ctrl+Shift+R` | Re-select capture region |
| `Ctrl+Shift+Q` | Quit the application |

### How the Ctrl+X cycle works

1. **1st press** → a fullscreen overlay appears, draw your capture rectangle with the mouse  
2. **2nd press** → recording starts (red border pulses around the screen)  
3. **3rd press** → recording stops → Save As dialog → option to copy file to clipboard  

After saving, the cycle resets — press `Ctrl+X` again to start a new recording with the same region, or `Ctrl+Shift+R` to pick a new one.

---

## 📦 Installation

### Quick Start

1. **[Download the latest release](https://github.com/xKubikRubikx/screen-region-recorder/releases/latest)** (.zip)
2. Extract anywhere
3. Run `install.bat`
4. Done! The recorder is now running in the background 🎉

### Prerequisites
- **Windows 10/11**
- **Python 3.11+** (auto-installed via `winget` if missing)
- **FFmpeg** (auto-installed via `winget` if missing)

The installer will:
- Copy files to `%LOCALAPPDATA%\ScreenRegionRecorder`
- Create a Python virtual environment
- Install Python and FFmpeg via `winget` if not found
- Add the app to Windows startup (Registry)
- Launch the recorder immediately

### Uninstall

Run `uninstall.bat` — it will:
- Stop all running recorder processes
- Remove the autorun Registry key  
- Delete all installed files from `%LOCALAPPDATA%\ScreenRegionRecorder`

---

## 🏗️ Project Structure

```
├── region_recorder.py      # Main app — hotkey listener, FFmpeg process manager
├── select_region.py        # Fullscreen overlay for drawing the capture rectangle
├── recording_overlay.py    # Animated red border shown during recording
├── post_save_dialog.py     # Save As dialog + clipboard copy utility
├── requirements.txt        # Python dependencies (none required)
├── install.bat             # One-click installer
└── uninstall.bat           # One-click uninstaller
```

---

## ⚙️ Technical Details

- **Video**: FFmpeg `gdigrab` input → `libx264` (veryfast preset) → MP4
- **Audio**: DirectShow loopback via Stereo Mix / Virtual Audio Cable (optional, auto-detected)
- **FPS**: 30 fps by default (configurable in `region_recorder.py`)
- **Overlay**: Uses `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` so the recording border is invisible in the output
- **Singleton**: WinAPI mutex prevents multiple instances
- **No external Python packages** — uses only `tkinter` (bundled with Python) and `ctypes`

---

## 🤝 Contributing

Feel free to open issues, suggest features, or submit pull requests.

---

## 📄 License

MIT — do whatever you want with it.
