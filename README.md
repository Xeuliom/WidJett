<div align="center">

# 🪟 WidJett
### Floating Desktop Widgets for Windows

**A lightweight, always-on-desktop widget engine built with PyQt5.**  
Glassmorphic UI · Customizable themes · Windows-native integration

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15%2B-green?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D4?style=flat-square&logo=windows)
![License](https://img.shields.io/badge/License-MIT-purple?style=flat-square)

</div>

---

## ✨ Features

| Widget | Description |
|---|---|
| 🕐 **Clock** | Live digital clock with date display |
| 📅 **Calendar** | Monthly calendar grid with persistent custom events |
| ⏱️ **Timer & Alarm** | Countdown timer + multi-alarm system (repeating days, editing, toggles) |
| ✅ **Todo** | Task list with priorities, autosaved to disk |
| 📋 **Clipboard** | Tracks last 12 clipboard entries across apps |
| 📒 **Smart Notes** | Full note-taking panel with search and tagging |
| 🎨 **Mood Mosaic** | Ambient colour tile driven by time of day |
| 🕌 **Prayer Times** | *(Coming Soon)* Live API integration with background countdowns |

**Hub features:**
- 🎨 Fully customizable widget theme (header + body RGBA)
- 🖋️ Global custom font selection 
- 📌 Pin (Always on Top) per widget
- 🚀 Optional Windows startup integration toggle
- 💾 All data persisted in `%APPDATA%\widjett\`

---

## 🛠️ Installation

> **Requires Python 3.8+ and Windows 10/11**

### 1. Clone the repo

```bash
git clone https://github.com/youruser/widjett.git
cd widjett
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
python main.py
```

---

## 📦 Build Standalone EXE

```bash
python -m PyInstaller --clean widjett.spec
```

Output: `dist/widjett.exe` — single-file, no Python installation required.

---

## 📁 Project Structure

```
widjett/
├── main.py               # Entry point & all core widgets
├── widgets/
│   └── smartnotes.py     # Smart Notes widget module
├── alarm.wav             # Alarm sound (bundled into exe)
├── logo.png              # App icon (bundled into exe)
├── widjett.spec          # PyInstaller build spec
├── requirements.txt      # pip dependencies
└── data.json             # Runtime data (auto-generated)
```

---

## ⚙️ Data & Persistence

All user data is stored in:

```
%APPDATA%\widjett\
├── data.json              # Widget positions, todos, theme colors, global fonts
├── notes.json             # Smart Notes content
├── calendar_events.json   # Calendar widget events
└── prayer_settings.json   # Prayer Times location settings
```

These files are created automatically on first run.

---

## 🔑 Dependencies

| Package | Use |
|---|---|
| `PyQt5` | UI framework (widgets, layouts, painting) |
| `requests` | Live API polling (Prayer Times) |
| `pywin32` | Windows clipboard, process, registry APIs |
| `pynput` | Global hotkey listener |
| `watchdog` | File system watcher for Smart Notes live reload |
| `psutil` | CPU / RAM / disk metrics for Radar widget |

---

## 🔄 Changelog

### v1.1.0 - Recent Updates
- **Hub UI Overhaul**: Replaced "Customize Colors" with a unified "General Settings" menu. Added the ability to select a global custom font and toggle Run on Windows Startup.
- **New Widget**: Added the `Calendar` widget featuring an interactive grid, current-day highlighting, and a persistent daily events editor.
- **Alarm Widget Rework**: Completely rebuilt from a single timer into a fully-fledged multi-alarm system (like a smartphone). Features include repeating days ("Mon", "Tue"), individual on/off toggles, and edit/delete capabilities with proper UI formatting.
- **Smart Notes**: Fixed a bug where hitting "Enter" for newlines would get mangled upon saving/reopening.
- **Clipboard**: Widened the "Clear" button for correct rendering and themed the horizontal scrollbar to match the rest of the app's glassmorphic design.
- **Prayer Times (Beta)**: Merged the backend logic for a new Aladhan API widget (currently disabled in UI pending final polish).
- **Build Spec**: Updated `widjett.spec` to correctly bundle `requests`, `urllib3`, and `email` for seamless `.exe` generation.

---

## 📜 License

MIT — free to use, modify, and distribute.
