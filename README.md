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
- **High quality** — CRF 18 by default (near-lossless, sharp text & UI)
- **System audio capture** — automatically detects Stereo Mix / Virtual Audio Cable
- **Recording indicator** — subtle pulsing red border around the screen while recording (invisible to capture)
- **Save As dialog** — after stopping, pick where to save + copy file/path to clipboard
- **Customizable hotkeys** — change any shortcut via `config.json`
- **Background operation** — no window, no tray icon, just hotkeys
- **Auto-start with Windows** — configures itself via the Registry on install
- **One-click install/uninstall** — batch scripts handle everything

---

## ⌨️ Hotkeys

All hotkeys are customizable in `config.json`.

| Shortcut | Action |
|---|---|
| `Ctrl+X` | **Cycle**: Select region → Start recording → Stop recording |
| `Ctrl+Shift+R` | Re-select capture region |
| `Ctrl+Shift+Q` | Quit the application |

### How the Ctrl+X cycle works

1. **1st press** → a fullscreen overlay appears, draw your capture rectangle with the mouse  
2. **2nd press** → recording starts (red border pulses around the screen)  
3. **3rd press** → recording stops → Save As dialog → option to copy file to clipboard  

After saving, the cycle resets — press `Ctrl+X` again to select a new area and start a new recording.

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

## ⚙️ Configuration

Edit `config.json` to customize hotkeys and recording quality:

```json
{
  "hotkeys": {
    "toggle": "ctrl+x",
    "reselect": "ctrl+shift+r",
    "quit": "ctrl+shift+q"
  },
  "recording": {
    "fps": 30,
    "crf": 18,
    "preset": "veryfast"
  }
}
```

**Recording quality:**
- `crf` — quality level (0 = lossless, 18 = high quality, 23 = default, 28 = low). Lower = better quality, bigger file.
- `preset` — encoding speed (`ultrafast`, `superfast`, `veryfast`, `faster`, `fast`, `medium`). Faster = less CPU, slightly bigger file.
- `fps` — frames per second (15, 30, 60)

---

## 🏗️ Project Structure

```
├── region_recorder.py      # Main app — hotkey listener, FFmpeg process manager
├── select_region.py        # Fullscreen overlay for drawing the capture rectangle
├── recording_overlay.py    # Animated red border shown during recording
├── post_save_dialog.py     # Save As dialog + clipboard copy utility
├── config.json             # User-configurable hotkeys and quality settings
├── requirements.txt        # Python dependencies (none required)
├── install.bat             # One-click installer
└── uninstall.bat           # One-click uninstaller
```

---

## 🤝 Contributing

Feel free to open issues, suggest features, or submit pull requests.

---

## 📄 License

MIT — do whatever you want with it.
