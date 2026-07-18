# -*- coding: utf-8 -*-
"""
=============================================================================
  Floating Desktop Widgets  —  main.py
  Run:   python main.py
  Deps:  pip install PyQt5 pywin32 pynput watchdog psutil
=============================================================================
"""

import sys
import json
import os
import threading
import winsound
import hashlib
import colorsys
import queue
import ctypes
import time
import winreg
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

# ── Optional heavy dependencies — imported lazily so the app still
# launches even if a package is missing (widgets just show an error label)
try:
    import win32clipboard
    import win32con
    import win32gui
    import win32process
    import win32api
    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False

try:
    from pynput import keyboard as _pynput_kb
    _HAS_PYNPUT = True
except ImportError:
    _HAS_PYNPUT = False

try:
    from watchdog.observers import Observer as _WatchdogObserver
    from watchdog.events import FileSystemEventHandler as _FSHandler
    _HAS_WATCHDOG = True
except ImportError:
    _HAS_WATCHDOG = False

try:
    import psutil as _psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

try:
    from widgets.smartnotes import SmartNotesWidget as _SmartNotesWidget
    _HAS_SMARTNOTES = True
except ImportError as _sn_err:
    _HAS_SMARTNOTES = False
    print(f"[WARN] SmartNotes not loaded: {_sn_err}")

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _requests = None
    _HAS_REQUESTS = False
    print("[WARN] requests not installed — Prayer Times widget will not work. Run: pip install requests")


# ── High-DPI flags MUST be set BEFORE QApplication is created ────────────────
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QSpinBox, QListWidget, QListWidgetItem,
    QDialog, QTextEdit, QFormLayout, QDialogButtonBox,
    QSystemTrayIcon, QMenu, QAction, QFrame, QSizePolicy,
    QCheckBox, QTabWidget, QColorDialog, QComboBox, QGridLayout,
)
from PyQt5.QtCore import (
    QTimer, QPoint, pyqtSignal, QEvent, QSize,
)
from PyQt5.QtGui import (
    QIcon, QColor, QPixmap, QCursor, QPainter, QPen, QBrush, QFont,
    QLinearGradient,
)
from PyQt5.QtWidgets import (
    QProgressBar, QScrollArea, QToolTip, QStackedWidget
)

# ─────────────────────────────────────────────────────────────────────────────
#  Persistence
# ─────────────────────────────────────────────────────────────────────────────

def get_asset_path(filename: str) -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / filename
    return Path(__file__).parent / filename

def get_data_dir() -> Path:
    app_data = os.environ.get('APPDATA')
    base = Path(app_data) if app_data else Path.home()
    dir_path = base / "widjett"
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path

DATA_FILE = get_data_dir() / "data.json"

MONTHS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

def load_data() -> dict:
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"widgets": [], "todos": []}

def save_data(data: dict) -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Could not save: {e}")

# ─────────────────────────────────────────────────────────────────────────────
#  Colour palette & QSS
# ─────────────────────────────────────────────────────────────────────────────

# ── Premium color palette ─────────────────────────────────────────────────────
C_BG          = "rgba(14, 14, 22, 240)"
C_HEADER_BG   = "rgba(24, 24, 38, 248)"
C_BORDER      = "rgba(90, 90, 150, 100)"
C_ACCENT      = "#9d8df5"          # softer violet
C_ACCENT2     = "#5dd6b5"          # teal-mint
C_ACCENT3     = "#f472b6"          # pink accent (new)
C_TEXT        = "#eeeef8"
C_TEXT_DIM    = "#7a7a9a"
C_BTN_HOVER   = "rgba(157, 141, 245, 170)"
C_BTN_DANGER  = "rgba(235, 75, 75, 215)"
C_BTN_SUCCESS = "rgba(93, 214, 181, 190)"

GLOBAL_QSS = f"""
QWidget {{
    font-family: "Inter", "Segoe UI Variable Display", "Segoe UI", "Roboto", sans-serif;
    font-size: 13px;
    color: {C_TEXT};
}}

/* ── card shell ─────────────────────────────── */
#Card {{
    background: {C_BG};
    border: 1px solid {C_BORDER};
    border-radius: 16px;
}}

/* ── title bar ──────────────────────────────── */
#TitleBar {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(30,28,52,245),
        stop:1 rgba(20,20,36,245)
    );
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    border-bottom: 1px solid {C_BORDER};
}}
#TitleLabel {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    color: {C_TEXT_DIM};
    padding-left: 4px;
}}

/* ── generic flat button ────────────────────── */
QPushButton {{
    background: rgba(255,255,255,10);
    color: {C_TEXT};
    border: 1px solid rgba(255,255,255,18);
    border-radius: 9px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton:hover   {{ background: {C_BTN_HOVER};  border-color: {C_ACCENT}; }}
QPushButton:pressed {{ background: rgba(157,141,245,230); }}
QPushButton:disabled {{ color: {C_TEXT_DIM}; background: rgba(255,255,255,4); border-color: rgba(255,255,255,8); }}

/* ── icon buttons (close / pin / hub) ───────── */
#CloseBtn, #PinBtn {{
    background: transparent;
    border: none;
    font-size: 13px;
    color: {C_TEXT_DIM};
    border-radius: 7px;
    min-width: 26px; max-width: 26px;
    min-height: 26px; max-height: 26px;
    padding: 0;
}}
#CloseBtn:hover {{ background: {C_BTN_DANGER}; color: white; }}
#PinBtn:hover   {{ background: rgba(93,214,181,130); color: white; }}
#PinBtn[pinned="true"] {{ color: {C_ACCENT2}; }}

/* ── clock ──────────────────────────────────── */
#ClockDisplay {{
    font-size: 48px;
    font-weight: 800;
    letter-spacing: 3px;
    color: {C_ACCENT};
    qproperty-alignment: AlignCenter;
}}
#DateDisplay {{
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 1px;
    color: {C_TEXT_DIM};
    qproperty-alignment: AlignCenter;
    padding-bottom: 6px;
}}

/* ── timer ──────────────────────────────────── */
#TimerDisplay {{
    font-size: 58px;
    font-weight: 800;
    letter-spacing: 4px;
    color: {C_ACCENT2};
    qproperty-alignment: AlignCenter;
}}
#TimerDisplayAlert {{
    font-size: 58px;
    font-weight: 800;
    letter-spacing: 4px;
    color: #ff4555;
    qproperty-alignment: AlignCenter;
}}

/* ── inputs ─────────────────────────────────── */
QSpinBox, QLineEdit {{
    background: rgba(255,255,255,8);
    border: 1px solid rgba(255,255,255,20);
    border-radius: 8px;
    padding: 5px 10px;
    color: {C_TEXT};
    selection-background-color: {C_ACCENT};
}}
QSpinBox:focus, QLineEdit:focus {{
    border-color: {C_ACCENT};
    background: rgba(157,141,245,15);
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 18px; border: none;
    background: rgba(255,255,255,8);
    border-radius: 4px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {C_BTN_HOVER};
}}

/* ── list widgets ───────────────────────────── */
QListWidget {{
    background: rgba(255,255,255,5);
    border: 1px solid rgba(255,255,255,12);
    border-radius: 10px;
    outline: none;
    padding: 4px;
}}
QListWidget::item {{ border-radius: 7px; padding: 4px 3px; }}
QListWidget::item:selected {{ background: rgba(157,141,245,75); }}
QListWidget::item:hover     {{ background: rgba(255,255,255,9); }}

/* ── scrollbar ──────────────────────────────── */
QScrollBar:vertical {{
    background: transparent; width: 5px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,45);
    border-radius: 3px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{
    background: transparent; height: 5px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: rgba(255,255,255,45);
    border-radius: 3px; min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}

/* ── dialogs ────────────────────────────────── */
#DialogCard {{
    background: rgba(18,18,30,252);
    border: 1px solid {C_BORDER};
    border-radius: 16px;
}}
QTextEdit {{
    background: rgba(255,255,255,8);
    border: 1px solid rgba(255,255,255,18);
    border-radius: 9px;
    padding: 7px;
    color: {C_TEXT};
}}
QDialogButtonBox QPushButton {{ min-width: 84px; }}

/* ── checkbox ───────────────────────────────── */
QCheckBox {{ spacing: 7px; color: {C_TEXT}; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border-radius: 5px;
    border: 1px solid rgba(255,255,255,38);
    background: rgba(255,255,255,7);
}}
QCheckBox::indicator:checked {{
    background: {C_ACCENT}; border-color: {C_ACCENT};
}}

/* ── progress bar ───────────────────────────── */
QProgressBar {{
    background: rgba(255,255,255,8);
    border: none; border-radius: 4px;
}}
QProgressBar::chunk {{
    background: qlineargradient(
        x1:0,y1:0,x2:1,y2:0,
        stop:0 {C_ACCENT}, stop:1 {C_ACCENT2});
    border-radius: 4px;
}}

/* ── launcher ───────────────────────────────── */
#Launcher {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(16,14,30,254),
        stop:0.5 rgba(20,18,38,254),
        stop:1 rgba(24,20,44,254)
    );
    border: 1px solid rgba(110,100,170,120);
    border-radius: 18px;
}}
#LauncherTitle  {{ font-size:16px; font-weight:800; letter-spacing:2.5px; color:{C_TEXT}; }}
#LauncherSub    {{ font-size:10px; color:{C_TEXT_DIM}; letter-spacing:1.5px; }}
#LaunchBtn {{
    background: rgba(255,255,255,6);
    border: 1px solid rgba(255,255,255,14);
    border-radius: 10px;
    padding: 11px 18px;
    font-size: 13px; font-weight:600;
    color: {C_TEXT};
    text-align: left;
}}
#LaunchBtn:hover   {{ background: rgba(157,141,245,150); border-color:{C_ACCENT}; }}
#LaunchBtn:pressed {{ background: rgba(157,141,245,220); }}
#LaunchBtn:disabled {{
    color: {C_TEXT_DIM};
    background: rgba(255,255,255,3);
    border-color: rgba(255,255,255,7);
}}
"""

# ─────────────────────────────────────────────────────────────────────────────
#  Base floating widget
# ─────────────────────────────────────────────────────────────────────────────

class FloatingWidget(QWidget):
    """
    Frameless, translucent, draggable base widget.

    Class-level hub callback: set FloatingWidget.show_hub = <callable> once
    after the Launcher is created so every widget's Hub button can open it.

    KEY DESIGN NOTES:
    - No QGraphicsDropShadowEffect: causes UpdateLayeredWindowIndirect errors
      on Windows when combined with WA_TranslucentBackground.
    - No WindowDoesNotAcceptFocus: that flag prevents keyboard input in child
      fields (QLineEdit, QSpinBox, etc.).
    - After setWindowFlags() we MUST re-apply WA_TranslucentBackground and
      restore the window position, otherwise the widget degrades.
    """

    closed = pyqtSignal(object)

    # Set by Launcher after creation so all widgets can show the hub
    show_hub: object = None

    def __init__(self, title: str, widget_id: str, data_ref: dict,
                 x: int = 200, y: int = 200, parent=None):
        super().__init__(parent,
                         Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self._title      = title
        self._widget_id  = widget_id
        self._data_ref   = data_ref
        self._pinned     = False
        self._drag_pos   = QPoint()
        self._dragging   = False

        self._build_ui()
        self.move(x, y)

    # ── layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Outer layout adds padding so the card doesn't touch window edges
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)

        self._card = QFrame()
        self._card.setObjectName("Card")

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # title bar
        self._title_bar = self._make_title_bar()
        card_layout.addWidget(self._title_bar)

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(14, 12, 14, 14)
        self._content_layout.setSpacing(8)
        card_layout.addWidget(self._content_widget)

        outer.addWidget(self._card)
        self._apply_saved_colors()

    def _apply_saved_colors(self) -> None:
        """Applies saved colors from data_ref to this widget's card and title bar."""
        colors = self._data_ref.get("hub_colors")
        if colors and "header" in colors and "body" in colors:
            hr = colors["header"]
            br = colors["body"]
            
            # Apply to the card body
            self._card.setStyleSheet(
                f"#Card {{"
                f"  background: rgba({br[0]},{br[1]},{br[2]},{br[3]});"
                f"  border: 1px solid rgba(110,100,170,120);"
                f"  border-radius: 16px;"
                f"}}"
            )
            # Apply to the title bar
            self._title_bar.setStyleSheet(
                f"#TitleBar {{"
                f"  background: qlineargradient("
                f"    x1:0, y1:0, x2:1, y2:0,"
                f"    stop:0 rgba({hr[0]},{hr[1]},{hr[2]},{hr[3]}),"
                f"    stop:1 rgba({hr[0]},{hr[1]},{hr[2]}, max(0, {hr[3]} - 30))"
                f"  );"
                f"  border-top-left-radius: 16px;"
                f"  border-top-right-radius: 16px;"
                f"  border-bottom: 1px solid rgba(90, 90, 150, 100);"
                f"}}"
            )
        else:
            # Revert to default by clearing inline stylesheet (relies on GLOBAL_QSS)
            self._card.setStyleSheet("")
            self._title_bar.setStyleSheet("")

    def _make_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("TitleBar")
        bar.setFixedHeight(36)
        bar.setCursor(QCursor(Qt.SizeAllCursor))

        h = QHBoxLayout(bar)
        h.setContentsMargins(10, 0, 6, 0)
        h.setSpacing(4)

        lbl = QLabel(self._title.upper())
        lbl.setObjectName("TitleLabel")
        h.addWidget(lbl)
        h.addStretch()

        # Hub button — opens/raises the Launcher window
        hub_btn = QPushButton("⊞")
        hub_btn.setObjectName("PinBtn")   # reuse same icon-button style
        hub_btn.setToolTip("Open Widget Hub")
        hub_btn.clicked.connect(self._open_hub)
        h.addWidget(hub_btn)

        self._pin_btn = QPushButton("📌")
        self._pin_btn.setObjectName("PinBtn")
        self._pin_btn.setCheckable(True)
        self._pin_btn.setToolTip("Pin — Always on Top")
        self._pin_btn.clicked.connect(self._toggle_pin)
        h.addWidget(self._pin_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self._on_close)
        h.addWidget(close_btn)

        bar.installEventFilter(self)
        return bar

    def _open_hub(self) -> None:
        """Show and raise the Launcher window."""
        if callable(FloatingWidget.show_hub):
            FloatingWidget.show_hub()

    # ── pin / always-on-top ───────────────────────────────────────────────────

    def _toggle_pin(self, checked: bool) -> None:
        self._pinned = checked

        # ── Visual feedback: change title bar background when pinned ──────────
        if checked:
            self._title_bar.setStyleSheet(
                "#TitleBar {"
                "  background: qlineargradient("
                "    x1:0,y1:0,x2:1,y2:0,"
                f"   stop:0 rgba(90,60,180,230), stop:1 rgba(60,100,170,230));"
                "  border-top-left-radius: 12px;"
                "  border-top-right-radius: 12px;"
                f"  border-bottom: 1px solid rgba(130,100,255,120);"
                "}"
            )
            self._pin_btn.setText("📍")   # upright pin = locked/active
            self._pin_btn.setToolTip("Unpin — click to disable Always on Top")
        else:
            self._title_bar.setStyleSheet("")  # revert to global QSS
            self._pin_btn.setText("📌")
            self._pin_btn.setToolTip("Pin — Always on Top")

        # Save position NOW before the flag change resets geometry
        pos = self.pos()

        # Build new flags
        flags = Qt.FramelessWindowHint | Qt.Tool
        if checked:
            flags |= Qt.WindowStaysOnTopHint

        # Apply flags — internally recreates the native window handle
        self.setWindowFlags(flags)

        # WA_TranslucentBackground is cleared on handle recreation — re-apply
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Restore position and reveal
        self.move(pos)
        self.show()
        self._save_position()

    # ── dragging ──────────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self._title_bar:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._dragging = True
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                return True
            elif event.type() == QEvent.MouseMove and self._dragging:
                new_pos = event.globalPos() - self._drag_pos
                
                # Screen snapping logic
                screen = QApplication.screenAt(event.globalPos())
                if not screen:
                    screen = QApplication.primaryScreen()
                
                if screen:
                    geom = screen.availableGeometry()
                    snap_dist = 25  # Snap threshold in pixels
                    
                    # Snap horizontal
                    if abs(new_pos.x() - geom.left()) < snap_dist:
                        new_pos.setX(geom.left())
                    elif abs(new_pos.x() + self.width() - geom.right()) < snap_dist:
                        # +1 to account for right edge coordinate inclusive vs exclusive
                        new_pos.setX(geom.right() - self.width() + 1)
                        
                    # Snap vertical
                    if abs(new_pos.y() - geom.top()) < snap_dist:
                        new_pos.setY(geom.top())
                    elif abs(new_pos.y() + self.height() - geom.bottom()) < snap_dist:
                        new_pos.setY(geom.bottom() - self.height() + 1)
                        
                self.move(new_pos)
                return True
            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._dragging = False
                self._save_position()
                return True
        return super().eventFilter(obj, event)

    # ── persistence ───────────────────────────────────────────────────────────

    def _save_position(self) -> None:
        pos = self.pos()
        for w in self._data_ref["widgets"]:
            if w.get("id") == self._widget_id:
                w["x"], w["y"] = pos.x(), pos.y()
                break
        save_data(self._data_ref)

    # ── close ─────────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        self._save_position()
        self._data_ref["widgets"] = [
            w for w in self._data_ref["widgets"]
            if w.get("id") != self._widget_id
        ]
        save_data(self._data_ref)
        self.closed.emit(self)
        self.close()

    # ── content helpers ───────────────────────────────────────────────────────

    def add_to_content(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def add_layout_to_content(self, layout) -> None:
        self._content_layout.addLayout(layout)


# ─────────────────────────────────────────────────────────────────────────────
#  Clock Widget  (singleton — only one allowed)
# ─────────────────────────────────────────────────────────────────────────────

class ClockWidget(FloatingWidget):
    WIDGET_TYPE = "clock"

    def __init__(self, widget_id: str, data_ref: dict, x: int = 200, y: int = 200):
        super().__init__("🕐  Clock", widget_id, data_ref, x, y)
        self.setFixedWidth(300)
        self._build_clock()

    def _build_clock(self) -> None:
        self._time_lbl = QLabel()
        self._time_lbl.setObjectName("ClockDisplay")
        self._time_lbl.setAlignment(Qt.AlignCenter)

        self._date_lbl = QLabel()
        self._date_lbl.setObjectName("DateDisplay")
        self._date_lbl.setAlignment(Qt.AlignCenter)

        self._content_layout.setContentsMargins(14, 16, 14, 18)
        self.add_to_content(self._time_lbl)
        self.add_to_content(self._date_lbl)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    def _tick(self) -> None:
        now = datetime.now()
        self._time_lbl.setText(now.strftime("%H:%M:%S"))
        self._date_lbl.setText(f"{now.day:02d} {MONTHS[now.month]} {now.year}")


# ─────────────────────────────────────────────────────────────────────────────
#  Timer Widget  (multiple instances allowed)
# ─────────────────────────────────────────────────────────────────────────────

ALARMS_FILE = get_data_dir() / "alarms.json"

def _load_alarms() -> list:
    try:
        if ALARMS_FILE.exists():
            import json
            with open(ALARMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _save_alarms(alarms: list) -> None:
    try:
        import json
        with open(ALARMS_FILE, "w", encoding="utf-8") as f:
            json.dump(alarms, f, indent=2)
    except Exception as e:
        print(f"[Alarm] Save failed: {e}")

class TimerWidget(FloatingWidget):
    """
    Two-tab widget: Timer tab and Alarm tab.
    """
    WIDGET_TYPE = "timer"

    def _apply_saved_colors(self) -> None:
        super()._apply_saved_colors()
        if not hasattr(self, '_tab_widget'):
            return
        colors = self._data_ref.get("hub_colors")
        if colors and "header" in colors and "body" in colors:
            hr = colors["header"]
            br = colors["body"]
            
            self._tab_widget.setStyleSheet(
                f"""
                QTabWidget::pane {{
                    border: 1px solid rgba(255,255,255,40);
                    border-radius: 10px;
                    background: rgba({br[0]},{br[1]},{br[2]}, max(0, {br[3]} - 40));
                }}
                QTabBar::tab {{
                    background: rgba(255,255,255,6);
                    color: {C_TEXT_DIM};
                    border: 1px solid rgba(255,255,255,30);
                    border-bottom: none;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    padding: 6px 18px;
                    font-size: 12px;
                    font-weight: 600;
                    margin-right: 3px;
                }}
                QTabBar::tab:selected {{
                    background: rgba({hr[0]},{hr[1]},{hr[2]}, max(0, {hr[3]} - 30));
                    color: {C_TEXT};
                    border: 1px solid rgba({hr[0]},{hr[1]},{hr[2]}, 200);
                }}
                QTabBar::tab:hover:!selected {{
                    background: rgba(255,255,255,15);
                    color: {C_TEXT};
                }}
                """
            )
        else:
            self._tab_widget.setStyleSheet(getattr(self, '_default_tab_qss', ''))

    @staticmethod
    def _play_alarm_sound(stop_evt: threading.Event) -> None:
        if getattr(sys, 'frozen', False):
            external = Path(sys.executable).parent / "alarm.wav"
            custom = external if external.exists() else get_asset_path("alarm.wav")
        else:
            custom = get_asset_path("alarm.wav")
        if custom.exists():
            try:
                winsound.PlaySound(
                    str(custom),
                    winsound.SND_FILENAME | winsound.SND_NODEFAULT
                    | winsound.SND_ASYNC | winsound.SND_LOOP,
                )
            except Exception:
                pass
            stop_evt.wait()
            try:
                winsound.PlaySound(None, winsound.SND_ASYNC)
            except Exception:
                pass
        else:
            while not stop_evt.is_set():
                for freq, dur in [(880, 180), (1100, 180), (880, 350)]:
                    if stop_evt.is_set():
                        break
                    try:
                        winsound.Beep(freq, dur)
                    except Exception:
                        pass

    def __init__(self, widget_id: str, data_ref: dict, x: int = 200, y: int = 200):
        self._t_remaining   = 0
        self._t_running     = False
        self._t_flash_count = 0
        self._t_alarm_evt   = threading.Event()
        
        self._alarms = _load_alarms()
        self._a_alarm_evt   = threading.Event()
        self._last_fired_alarm_id = None
        self._last_fired_minute = -1
        self._editing_alarm_id = None

        super().__init__("⏱  Timer & Alarm", widget_id, data_ref, x, y)
        self.setFixedWidth(380)

    def _build_ui(self) -> None:
        super()._build_ui()
        self._content_layout.setContentsMargins(8, 8, 8, 10)
        self._content_layout.setSpacing(0)

        self._tab_widget = QTabWidget()
        self._default_tab_qss = f"""
            QTabWidget::pane {{
                border: 1px solid rgba(90,90,150,80);
                border-radius: 10px;
                background: rgba(20,20,36,180);
            }}
            QTabBar::tab {{
                background: rgba(255,255,255,6);
                color: {C_TEXT_DIM};
                border: 1px solid rgba(90,90,150,60);
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 6px 18px;
                font-size: 12px;
                font-weight: 600;
                margin-right: 3px;
            }}
            QTabBar::tab:selected {{
                background: rgba(157,141,245,120);
                color: {C_TEXT};
                border-color: {C_ACCENT};
            }}
            QTabBar::tab:hover:!selected {{
                background: rgba(157,141,245,50);
                color: {C_TEXT};
            }}
            """
        self._tab_widget.setStyleSheet(self._default_tab_qss)
        self._apply_saved_colors()

        # ── Timer tab ─────────────────────────────────────────────────────────
        timer_page = QWidget()
        timer_page.setStyleSheet("background: transparent;")
        t_lay = QVBoxLayout(timer_page)
        t_lay.setContentsMargins(12, 14, 12, 14)
        t_lay.setSpacing(10)

        self._t_display = QLabel("00:00")
        self._t_display.setObjectName("TimerDisplay")
        self._t_display.setAlignment(Qt.AlignCenter)
        t_lay.addWidget(self._t_display)

        spin_row = QHBoxLayout()
        spin_row.setSpacing(6)
        lbl_m = QLabel("Min")
        lbl_m.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        self._t_min_spin = QSpinBox()
        self._t_min_spin.setRange(0, 99)
        self._t_min_spin.setFixedWidth(58)
        self._t_min_spin.setFocusPolicy(Qt.StrongFocus)
        lbl_s = QLabel("Sec")
        lbl_s.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        self._t_sec_spin = QSpinBox()
        self._t_sec_spin.setRange(0, 59)
        self._t_sec_spin.setFixedWidth(58)
        self._t_sec_spin.setFocusPolicy(Qt.StrongFocus)
        spin_row.addStretch()
        spin_row.addWidget(lbl_m)
        spin_row.addWidget(self._t_min_spin)
        spin_row.addWidget(lbl_s)
        spin_row.addWidget(self._t_sec_spin)
        spin_row.addStretch()
        t_lay.addLayout(spin_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._t_start_btn = QPushButton("▶  Start")
        self._t_pause_btn = QPushButton("⏸  Pause")
        self._t_reset_btn = QPushButton("↺  Reset")
        self._t_pause_btn.setEnabled(False)
        self._t_start_btn.clicked.connect(self._t_start)
        self._t_pause_btn.clicked.connect(self._t_pause)
        self._t_reset_btn.clicked.connect(self._t_reset)
        btn_row.addWidget(self._t_start_btn)
        btn_row.addWidget(self._t_pause_btn)
        btn_row.addWidget(self._t_reset_btn)
        t_lay.addLayout(btn_row)

        self._t_stop_alarm_btn = QPushButton("🔕  Stop Alarm")
        self._t_stop_alarm_btn.setStyleSheet(
            "QPushButton{background:rgba(220,60,60,200);border:1px solid rgba(255,100,100,180);"
            "border-radius:7px;font-weight:700;padding:6px;}"
            "QPushButton:hover{background:rgba(255,80,80,230);}"
        )
        self._t_stop_alarm_btn.hide()
        self._t_stop_alarm_btn.clicked.connect(self._t_stop_alarm)
        t_lay.addWidget(self._t_stop_alarm_btn)
        self._tab_widget.addTab(timer_page, "⏱  Timer")

        # ── Alarm tab (Stacked) ───────────────────────────────────────────────
        self._alarm_page = QWidget()
        self._alarm_page.setStyleSheet("background: transparent;")
        a_lay = QVBoxLayout(self._alarm_page)
        a_lay.setContentsMargins(0,0,0,0)

        self._alarm_stack = QStackedWidget()
        a_lay.addWidget(self._alarm_stack)

        self._build_alarm_list_ui()
        self._build_alarm_edit_ui()

        # Stop alarm button (overlay for when alarm rings)
        self._a_stop_btn = QPushButton("🔕  Dismiss Alarm")
        self._a_stop_btn.setStyleSheet(
            "QPushButton{background:rgba(220,60,60,200);border:1px solid rgba(255,100,100,180);"
            "border-radius:7px;font-weight:700;padding:10px;font-size:16px; margin:10px;}"
            "QPushButton:hover{background:rgba(255,80,80,230);}"
        )
        self._a_stop_btn.hide()
        self._a_stop_btn.clicked.connect(self._a_stop)
        a_lay.addWidget(self._a_stop_btn)

        self._tab_widget.addTab(self._alarm_page, "⏰  Alarm")
        self._content_layout.addWidget(self._tab_widget)

        # ── internal QTimers ──────────────────────────────────────────────────
        self._t_tick_timer = QTimer(self)
        self._t_tick_timer.setInterval(1000)
        self._t_tick_timer.timeout.connect(self._t_tick)

        self._t_flash_timer = QTimer(self)
        self._t_flash_timer.setInterval(400)
        self._t_flash_timer.timeout.connect(self._t_flash)

        self._a_poll_timer = QTimer(self)
        self._a_poll_timer.setInterval(1000)
        self._a_poll_timer.timeout.connect(self._a_poll)
        self._a_poll_timer.start()

    def _build_alarm_list_ui(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        # Add button
        top_row = QHBoxLayout()
        top_row.addStretch()
        self._a_add_btn = QPushButton("＋ Add Alarm")
        self._a_add_btn.setStyleSheet(
            f"QPushButton{{background:rgba(157,141,245,180); border:1px solid {{C_ACCENT}};"
            f"border-radius:6px; padding:4px 12px; font-weight:bold;}}"
            f"QPushButton:hover{{background:rgba(157,141,245,220);}}"
        )
        self._a_add_btn.clicked.connect(self._a_new)
        top_row.addWidget(self._a_add_btn)
        lay.addLayout(top_row)

        self._alarm_scroll = QScrollArea()
        self._alarm_scroll.setWidgetResizable(True)
        self._alarm_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._alarm_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        
        self._alarm_list_container = QWidget()
        self._alarm_list_container.setStyleSheet("background:transparent;")
        self._alarm_list_layout = QVBoxLayout(self._alarm_list_container)
        self._alarm_list_layout.setContentsMargins(0,0,0,0)
        self._alarm_list_layout.setSpacing(6)
        self._alarm_list_layout.addStretch()

        self._alarm_scroll.setWidget(self._alarm_list_container)
        lay.addWidget(self._alarm_scroll)

        self._alarm_stack.addWidget(page)
        self._refresh_alarm_list()

    def _build_alarm_edit_ui(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        title = QLabel("Edit Alarm")
        title.setStyleSheet(f"font-size:14px; font-weight:bold; color:{C_TEXT};")
        lay.addWidget(title)

        time_row = QHBoxLayout()
        self._a_hour_spin = QSpinBox()
        self._a_hour_spin.setRange(0, 23)
        self._a_hour_spin.setFixedWidth(60)
        self._a_hour_spin.setStyleSheet("font-size:24px; padding:4px;")
        
        colon = QLabel(":")
        colon.setStyleSheet("font-size:24px; font-weight:bold;")
        
        self._a_min_spin = QSpinBox()
        self._a_min_spin.setRange(0, 59)
        self._a_min_spin.setFixedWidth(60)
        self._a_min_spin.setStyleSheet("font-size:24px; padding:4px;")

        time_row.addStretch()
        time_row.addWidget(self._a_hour_spin)
        time_row.addWidget(colon)
        time_row.addWidget(self._a_min_spin)
        time_row.addStretch()
        lay.addLayout(time_row)

        self._a_label_edit = QLineEdit()
        self._a_label_edit.setPlaceholderText("Alarm Label...")
        lay.addWidget(self._a_label_edit)

        # Days picker
        days_row = QHBoxLayout()
        days_row.setSpacing(4)
        self._day_btns = []
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, d in enumerate(day_names):
            b = QPushButton(d)
            b.setCheckable(True)
            b.setFixedHeight(26)
            b.setStyleSheet(
                "QPushButton{background:rgba(255,255,255,10); border:1px solid rgba(255,255,255,20);"
                " border-radius:4px; color:#eeeef8; font-family:'Segoe UI'; font-size:10px; padding:2px 4px;}"
                f"QPushButton:checked{{background:rgba(157,141,245,200); border:1px solid {C_ACCENT}; font-weight:bold; color:white;}}"
            )
            self._day_btns.append(b)
            days_row.addWidget(b)
        lay.addLayout(days_row)

        # Buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"background:rgba(157,141,245,180); font-weight:bold; padding:6px;")
        save_btn.clicked.connect(self._a_save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(lambda: self._alarm_stack.setCurrentIndex(0))
        
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        lay.addLayout(btn_row)
        
        lay.addStretch()
        self._alarm_stack.addWidget(page)

    def _refresh_alarm_list(self) -> None:
        # clear existing
        while self._alarm_list_layout.count() > 1:
            item = self._alarm_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for alarm in self._alarms:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame{{background:rgba(255,255,255,8); border:1px solid rgba(255,255,255,15); border-radius:8px;}}"
            )
            c_lay = QHBoxLayout(card)
            c_lay.setContentsMargins(12, 8, 12, 8)
            
            # Left side: Time, Label, Days
            l_lay = QVBoxLayout()
            l_lay.setSpacing(2)
            time_lbl = QLabel(f"{alarm['hour']:02d}:{alarm['minute']:02d}")
            time_lbl.setStyleSheet(f"font-size:20px; font-weight:bold; border:none; background:transparent;")
            
            lbl_text = alarm.get('label', '')
            if not lbl_text:
                lbl_text = "Alarm"
            
            days = alarm.get('days', [])
            if not days:
                days_text = "Once"
            elif len(days) == 7:
                days_text = "Every day"
            else:
                day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                days_text = ", ".join([day_names[d] for d in days])
                
            sub_lbl = QLabel(f"{lbl_text} • {days_text}")
            sub_lbl.setStyleSheet(f"font-size:11px; color:{C_TEXT_DIM}; border:none; background:transparent;")
            sub_lbl.setWordWrap(True)
            
            l_lay.addWidget(time_lbl)
            l_lay.addWidget(sub_lbl)
            c_lay.addLayout(l_lay)
            c_lay.addStretch()
            
            # Right side: Edit, Delete, Toggle
            _card_font = QFont("Segoe UI", 9)
            edit_btn = QPushButton("Edit")
            edit_btn.setFixedHeight(26)
            edit_btn.setFont(_card_font)
            edit_btn.setStyleSheet(f"QPushButton{{background:rgba(255,255,255,15); border:none; border-radius:4px; color:{C_TEXT}; padding: 0 10px;}}")
            edit_btn.clicked.connect(lambda checked, aid=alarm['id']: self._a_edit(aid))
            
            del_btn = QPushButton("Del")
            del_btn.setFixedHeight(26)
            del_btn.setFont(_card_font)
            del_btn.setStyleSheet("QPushButton{background:rgba(235,75,75,180); border:none; border-radius:4px; color:white; padding: 0 10px;}")
            del_btn.clicked.connect(lambda checked, aid=alarm['id']: self._a_delete(aid))
            
            toggle_cb = QCheckBox()
            toggle_cb.setChecked(alarm.get('active', True))
            toggle_cb.setStyleSheet(
                "QCheckBox::indicator { width: 34px; height: 18px; }"
                "QCheckBox::indicator:unchecked { image: none; border-radius: 9px; background: rgba(255,255,255,30); border: 1px solid rgba(255,255,255,40); }"
                "QCheckBox::indicator:checked { image: none; border-radius: 9px; background: rgba(93,214,181,180); border: 1px solid rgba(93,214,181,255); }"
            )
            toggle_cb.toggled.connect(lambda checked, aid=alarm['id']: self._a_toggle(aid, checked))
            
            c_lay.addWidget(edit_btn)
            c_lay.addWidget(del_btn)
            c_lay.addWidget(toggle_cb)
            
            self._alarm_list_layout.insertWidget(self._alarm_list_layout.count() - 1, card)

    def _a_new(self) -> None:
        self._editing_alarm_id = None
        now = datetime.now()
        self._a_hour_spin.setValue(now.hour)
        self._a_min_spin.setValue((now.minute + 1) % 60)
        self._a_label_edit.setText("")
        for btn in self._day_btns:
            btn.setChecked(False)
        self._alarm_stack.setCurrentIndex(1)

    def _a_edit(self, aid: str) -> None:
        alarm = next((a for a in self._alarms if a['id'] == aid), None)
        if not alarm: return
        self._editing_alarm_id = aid
        self._a_hour_spin.setValue(alarm.get('hour', 0))
        self._a_min_spin.setValue(alarm.get('minute', 0))
        self._a_label_edit.setText(alarm.get('label', ''))
        days = alarm.get('days', [])
        for i, btn in enumerate(self._day_btns):
            btn.setChecked(i in days)
        self._alarm_stack.setCurrentIndex(1)

    def _a_delete(self, aid: str) -> None:
        self._alarms = [a for a in self._alarms if a['id'] != aid]
        _save_alarms(self._alarms)
        self._refresh_alarm_list()

    def _a_toggle(self, aid: str, active: bool) -> None:
        for a in self._alarms:
            if a['id'] == aid:
                a['active'] = active
        _save_alarms(self._alarms)

    def _a_save(self) -> None:
        days = [i for i, btn in enumerate(self._day_btns) if btn.isChecked()]
        if self._editing_alarm_id:
            # Edit existing
            for a in self._alarms:
                if a['id'] == self._editing_alarm_id:
                    a['hour'] = self._a_hour_spin.value()
                    a['minute'] = self._a_min_spin.value()
                    a['label'] = self._a_label_edit.text().strip()
                    a['days'] = days
                    a['active'] = True
        else:
            # New alarm
            import uuid
            self._alarms.append({
                'id': str(uuid.uuid4()),
                'hour': self._a_hour_spin.value(),
                'minute': self._a_min_spin.value(),
                'label': self._a_label_edit.text().strip(),
                'days': days,
                'active': True
            })
        
        # Sort by hour, then minute
        self._alarms.sort(key=lambda a: (a['hour'], a['minute']))
        _save_alarms(self._alarms)
        self._alarm_stack.setCurrentIndex(0)
        self._refresh_alarm_list()

    def _a_poll(self) -> None:
        now = datetime.now()
        cur_h = now.hour
        cur_m = now.minute
        cur_w = now.weekday()

        for a in self._alarms:
            if not a.get('active', False):
                continue
            if a['hour'] == cur_h and a['minute'] == cur_m:
                days = a.get('days', [])
                if not days or cur_w in days:
                    # Time and day match
                    if self._last_fired_alarm_id == a['id'] and self._last_fired_minute == cur_m:
                        continue # Already fired this minute
                    
                    self._last_fired_alarm_id = a['id']
                    self._last_fired_minute = cur_m
                    self._a_fire_alarm(a)
                    
                    if not days:
                        # One time alarm, turn off
                        a['active'] = False
                        _save_alarms(self._alarms)
                        self._refresh_alarm_list()

    def _a_fire_alarm(self, alarm: dict) -> None:
        self._a_alarm_evt.clear()
        self._alarm_scroll.hide()
        self._a_add_btn.hide()
        self._a_stop_btn.setText(f"🔕  Dismiss\n\n{alarm['hour']:02d}:{alarm['minute']:02d} - {alarm.get('label', 'Alarm')}")
        self._a_stop_btn.show()
        
        threading.Thread(
            target=self._play_alarm_sound,
            args=(self._a_alarm_evt,),
            daemon=True,
        ).start()

    def _a_stop(self) -> None:
        self._a_alarm_evt.set()
        try:
            winsound.PlaySound(None, winsound.SND_ASYNC)
        except Exception:
            pass
        self._a_stop_btn.hide()
        self._alarm_scroll.show()
        self._a_add_btn.show()

    # ══════════════════════════════════════════════════════════════════════════
    #  TIMER TAB LOGIC (unchanged)
    # ══════════════════════════════════════════════════════════════════════════

    def _t_start(self) -> None:
        if self._t_remaining == 0:
            total = self._t_min_spin.value() * 60 + self._t_sec_spin.value()
            if total == 0:
                return
            self._t_remaining = total
        self._t_running = True
        self._t_start_btn.setEnabled(False)
        self._t_pause_btn.setEnabled(True)
        self._t_tick_timer.start()
        self._t_update_display()

    def _t_pause(self) -> None:
        self._t_running = False
        self._t_tick_timer.stop()
        self._t_start_btn.setEnabled(True)
        self._t_pause_btn.setEnabled(False)

    def _t_reset(self) -> None:
        self._t_stop_alarm()
        self._t_tick_timer.stop()
        self._t_flash_timer.stop()
        self._t_running     = False
        self._t_remaining   = 0
        self._t_flash_count = 0
        self._t_set_display_normal()
        self._t_display.setText("00:00")
        self._t_start_btn.setEnabled(True)
        self._t_pause_btn.setEnabled(False)

    def _t_tick(self) -> None:
        if self._t_remaining > 0:
            self._t_remaining -= 1
            self._t_update_display()
        if self._t_remaining == 0:
            self._t_tick_timer.stop()
            self._t_running = False
            self._t_start_btn.setEnabled(True)
            self._t_pause_btn.setEnabled(False)
            self._t_alert()

    def _t_update_display(self) -> None:
        m, s = divmod(self._t_remaining, 60)
        self._t_display.setText(f"{m:02d}:{s:02d}")

    def _t_alert(self) -> None:
        self._t_alarm_evt.clear()
        self._t_stop_alarm_btn.show()
        self._t_flash_count = 0
        self._t_flash_timer.start()
        threading.Thread(
            target=self._play_alarm_sound,
            args=(self._t_alarm_evt,),
            daemon=True,
        ).start()

    def _t_stop_alarm(self) -> None:
        self._t_alarm_evt.set()
        try:
            winsound.PlaySound(None, winsound.SND_ASYNC)
        except Exception:
            pass
        self._t_flash_timer.stop()
        self._t_set_display_normal()
        self._t_display.setText("00:00")
        self._t_stop_alarm_btn.hide()
        self._t_start_btn.setEnabled(True)
        self._t_pause_btn.setEnabled(False)

    def _t_flash(self) -> None:
        if self._t_flash_count >= 6:
            self._t_flash_timer.stop()
            self._t_set_display_normal()
            return
        if self._t_flash_count % 2 == 0:
            self._t_display.setObjectName("TimerDisplayAlert")
        else:
            self._t_set_display_normal()
        self._t_display.style().unpolish(self._t_display)
        self._t_display.style().polish(self._t_display)
        self._t_flash_count += 1

    def _t_set_display_normal(self) -> None:
        self._t_display.setObjectName("TimerDisplay")
        self._t_display.style().unpolish(self._t_display)
        self._t_display.style().polish(self._t_display)

    def _on_close(self) -> None:
        self._t_stop_alarm()
        self._a_stop()
        self._a_poll_timer.stop()
        super()._on_close()


# ─────────────────────────────────────────────────────────────────────────────
#  Edit Task Dialog
# ─────────────────────────────────────────────────────────────────────────────

class EditTaskDialog(QDialog):
    def __init__(self, title: str = "", description: str = "", parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumWidth(380)
        self._build_ui(title, description)

    def _build_ui(self, title: str, description: str) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        card = QFrame()
        card.setObjectName("DialogCard")
        vlay = QVBoxLayout(card)
        vlay.setContentsMargins(16, 14, 16, 14)
        vlay.setSpacing(10)

        hdr = QLabel("✏️  Edit Task")
        hdr.setStyleSheet(f"font-size:14px; font-weight:700; color:{C_TEXT};")
        vlay.addWidget(hdr)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)

        self._title_edit = QLineEdit(title)
        self._title_edit.setPlaceholderText("Task title…")
        self._title_edit.setFocusPolicy(Qt.StrongFocus)
        form.addRow("Title:", self._title_edit)

        self._desc_edit = QTextEdit(description)
        self._desc_edit.setPlaceholderText("Optional description…")
        self._desc_edit.setFixedHeight(88)
        self._desc_edit.setFocusPolicy(Qt.StrongFocus)
        form.addRow("Desc:", self._desc_edit)
        vlay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        vlay.addWidget(btns)

        outer.addWidget(card)

    def get_values(self):
        return (self._title_edit.text().strip(),
                self._desc_edit.toPlainText().strip())


# ─────────────────────────────────────────────────────────────────────────────
#  Todo Widget  (singleton — only one allowed)
# ─────────────────────────────────────────────────────────────────────────────

class TodoItemWidget(QWidget):
    toggled        = pyqtSignal(int, bool)
    edit_requested = pyqtSignal(int)
    del_requested  = pyqtSignal(int)

    def __init__(self, index: int, task: dict, parent=None):
        super().__init__(parent)
        self._index = index
        self._task  = task
        self._build()

    def _build(self) -> None:
        h = QHBoxLayout(self)
        h.setContentsMargins(6, 3, 6, 3)
        h.setSpacing(6)

        self._chk = QCheckBox()
        self._chk.setChecked(self._task.get("done", False))
        self._chk.stateChanged.connect(self._on_toggle)
        h.addWidget(self._chk)

        self._lbl = QLabel(self._task.get("title", ""))
        self._lbl.setWordWrap(True)
        self._lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._refresh_style()
        h.addWidget(self._lbl)

        # Use short ASCII-safe text for buttons so they render on all fonts
        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(38, 26)
        edit_btn.setToolTip("Edit task")
        edit_btn.setStyleSheet(
            f"QPushButton{{ font-size:10px; padding:0 4px; }}"
            f"QPushButton:hover{{ background:{C_BTN_HOVER}; }}"
        )
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self._index))
        h.addWidget(edit_btn)

        del_btn = QPushButton("Del")
        del_btn.setFixedSize(34, 26)
        del_btn.setToolTip("Delete task")
        del_btn.setStyleSheet(
            f"QPushButton{{ font-size:10px; padding:0 4px; }}"
            f"QPushButton:hover{{ background:{C_BTN_DANGER}; }}"
        )
        del_btn.clicked.connect(lambda: self.del_requested.emit(self._index))
        h.addWidget(del_btn)

    def _refresh_style(self) -> None:
        done   = self._task.get("done", False)
        color  = C_TEXT_DIM if done else C_TEXT
        strike = "line-through" if done else "none"
        self._lbl.setStyleSheet(
            f"color:{color}; text-decoration:{strike}; font-size:12px;")

    def _on_toggle(self, state: int) -> None:
        self.toggled.emit(self._index, bool(state))


class TodoWidget(FloatingWidget):
    WIDGET_TYPE = "todo"

    def __init__(self, widget_id: str, data_ref: dict, x: int = 200, y: int = 200):
        super().__init__("📝  To-Do", widget_id, data_ref, x, y)
        self.setMinimumWidth(360)
        self.setMaximumWidth(460)
        self._build_todo_ui()

    def _build_todo_ui(self) -> None:
        self._content_layout.setSpacing(8)

        # ── input row ──
        row = QHBoxLayout()
        row.setSpacing(6)
        self._input = QLineEdit()
        self._input.setPlaceholderText("New task title…")
        self._input.setFocusPolicy(Qt.StrongFocus)
        self._input.returnPressed.connect(self._add_task)
        add_btn = QPushButton("＋ Add")
        add_btn.setStyleSheet(f"QPushButton:hover{{background:{C_BTN_SUCCESS};}}")
        add_btn.clicked.connect(self._add_task)
        row.addWidget(self._input)
        row.addWidget(add_btn)
        self.add_layout_to_content(row)

        # ── list ──
        self._list = QListWidget()
        self._list.setSpacing(1)
        self._list.setMinimumHeight(180)
        self._list.setMaximumHeight(380)
        # Uniform row height ensures buttons are never clipped
        self._list.setUniformItemSizes(False)
        self.add_to_content(self._list)
        self._refresh_list()

    def _refresh_list(self) -> None:
        self._list.clear()
        todos = self._data_ref.setdefault("todos", [])
        todos.sort(key=lambda t: t.get("done", False))
        for i, task in enumerate(todos):
            item = QListWidgetItem(self._list)
            row  = TodoItemWidget(i, task)
            row.toggled.connect(self._on_toggle)
            row.edit_requested.connect(self._on_edit)
            row.del_requested.connect(self._on_delete)
            # Add a small fixed height buffer so buttons are never clipped
            hint = row.sizeHint()
            from PyQt5.QtCore import QSize
            item.setSizeHint(QSize(hint.width(), max(hint.height(), 36)))
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

    def _add_task(self) -> None:
        title = self._input.text().strip()
        if not title:
            return
        self._data_ref.setdefault("todos", []).append(
            {"title": title, "description": "", "done": False}
        )
        self._input.clear()
        save_data(self._data_ref)
        self._refresh_list()

    def _on_toggle(self, index: int, done: bool) -> None:
        self._data_ref["todos"][index]["done"] = done
        save_data(self._data_ref)
        self._refresh_list()

    def _on_edit(self, index: int) -> None:
        task = self._data_ref["todos"][index]
        dlg  = EditTaskDialog(task["title"], task["description"], self)
        if dlg.exec_() == QDialog.Accepted:
            title, desc = dlg.get_values()
            if title:
                task["title"]       = title
                task["description"] = desc
                save_data(self._data_ref)
                self._refresh_list()

    def _on_delete(self, index: int) -> None:
        del self._data_ref["todos"][index]
        save_data(self._data_ref)
        self._refresh_list()


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE-LEVEL STATE — shared between Pomodoro and Interruption Radar
# ─────────────────────────────────────────────────────────────────────────────

# Radar checks this flag before applying the "punishment".
# PomodoroWidget sets it to True when running, False when paused/stopped.
_pomodoro_running: bool = False


# ─────────────────────────────────────────────────────────────────────────────
#  Widget 1 — Clipboard History
# ─────────────────────────────────────────────────────────────────────────────

CLIPBOARD_HISTORY_FILE = get_data_dir() / "clipboard_history.json"


class ClipboardArchiveDialog(QDialog):
    def __init__(self, clipboard_widget, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumWidth(420)
        self.setMinimumHeight(480)
        self._clipboard_widget = clipboard_widget
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        card = QFrame()
        card.setObjectName("DialogCard")
        vlay = QVBoxLayout(card)
        vlay.setContentsMargins(16, 14, 16, 14)
        vlay.setSpacing(10)

        # Title bar
        hdr_lay = QHBoxLayout()
        hdr = QLabel("📋  All Copied Items")
        hdr.setStyleSheet(f"font-size:14px; font-weight:700; color:{C_TEXT};")
        hdr_lay.addWidget(hdr)
        hdr_lay.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.reject)
        hdr_lay.addWidget(close_btn)
        vlay.addLayout(hdr_lay)

        # List
        self._list = QListWidget()
        self._list.setMinimumHeight(300)
        self._list.itemDoubleClicked.connect(self._restore_item)
        vlay.addWidget(self._list)

        # Buttons
        btn_lay = QHBoxLayout()
        clear_btn = QPushButton("Clear Everything")
        clear_btn.setStyleSheet(f"QPushButton:hover {{ background: {C_BTN_DANGER}; }}")
        clear_btn.clicked.connect(self._clear_everything)

        close_dialog_btn = QPushButton("Close")
        close_dialog_btn.clicked.connect(self.reject)

        btn_lay.addWidget(clear_btn)
        btn_lay.addStretch()
        btn_lay.addWidget(close_dialog_btn)
        vlay.addLayout(btn_lay)

        outer.addWidget(card)
        self._refresh_list()

    def _refresh_list(self) -> None:
        self._list.clear()
        history = self._clipboard_widget._history
        if not history:
            item = QListWidgetItem("No history found")
            item.setFlags(Qt.NoItemFlags)
            self._list.addItem(item)
            return

        sorted_history = sorted(history, key=lambda x: x.get("timestamp", 0), reverse=True)

        grouped = {}
        for entry in sorted_history:
            t = entry.get("timestamp", 0)
            dt = datetime.fromtimestamp(t)
            date_str = dt.strftime("%A, %B %d, %Y")
            grouped.setdefault(date_str, []).append(entry)

        for date_str, entries in grouped.items():
            header_item = QListWidgetItem(f"📅  {date_str}")
            header_item.setFlags(Qt.NoItemFlags)
            header_item.setFont(QFont("Segoe UI", 11, QFont.Bold))
            header_item.setForeground(QColor(C_ACCENT2))
            self._list.addItem(header_item)

            for entry in entries:
                text = entry.get("text", "")
                preview = text[:60].replace("\n", " ").replace("\r", "")
                if len(text) > 60:
                    preview += "…"
                time_str = datetime.fromtimestamp(entry.get("timestamp", 0)).strftime("%H:%M:%S")
                item = QListWidgetItem(f"  {time_str}  -  {preview}")
                item.setData(Qt.UserRole, text)
                item.setToolTip(text[:400])
                self._list.addItem(item)

    def _restore_item(self, item: QListWidgetItem) -> None:
        full = item.data(Qt.UserRole)
        if full:
            self._clipboard_widget._restore_text(full)
            self.accept()

    def _clear_everything(self) -> None:
        self._clipboard_widget._clear_history()
        self._refresh_list()


class ClipboardWidget(FloatingWidget):
    """
    Polls the Windows clipboard every 500 ms, keeps a persistent history of copied items,
    and displays today's copies. Older items can be viewed in an archive dialog.
    """
    WIDGET_TYPE = "clipboard"

    def __init__(self, widget_id: str, data_ref: dict,
                 x: int = 200, y: int = 200):
        super().__init__("📋  Clipboard History", widget_id, data_ref, x, y)
        self.setFixedWidth(340)
        self._history: list[dict] = self._load_history()
        self._last_hash: str = ""
        self._build_clipboard_ui()

    def _load_history(self) -> list[dict]:
        if CLIPBOARD_HISTORY_FILE.exists():
            try:
                with open(CLIPBOARD_HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_history(self, history: list[dict]) -> None:
        try:
            with open(CLIPBOARD_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ClipboardWidget] Save failed: {e}")

    def _is_today(self, timestamp: float) -> bool:
        dt = datetime.fromtimestamp(timestamp)
        now = datetime.now()
        return dt.date() == now.date()

    def _build_clipboard_ui(self) -> None:
        self._content_layout.setSpacing(8)

        # Header row: label + clear button
        hrow = QHBoxLayout()
        lbl = QLabel("Today's Copies")
        lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(70)
        clear_btn.clicked.connect(self._clear_history)
        hrow.addWidget(lbl)
        hrow.addStretch()
        hrow.addWidget(clear_btn)
        self.add_layout_to_content(hrow)

        # Scrollable list
        self._list = QListWidget()
        self._list.setMinimumHeight(170)
        self._list.setMaximumHeight(280)
        self._list.setToolTip("Double-click to restore item to clipboard")
        self._list.itemDoubleClicked.connect(self._restore_item)
        self.add_to_content(self._list)

        # Archive / Show Old Items button
        self._archive_btn = QPushButton("📜  Show Older Copies")
        self._archive_btn.clicked.connect(self._show_archive)
        self.add_to_content(self._archive_btn)

        hint = QLabel("⤶ Double-click to restore")
        hint.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px;")
        hint.setAlignment(Qt.AlignCenter)
        self.add_to_content(hint)

        # Poll timer — runs on the GUI thread, reads clipboard safely
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._poll_clipboard)
        self._poll_timer.start()

        # Initial refresh
        self._refresh_list()

    # ── clipboard polling ─────────────────────────────────────────────────────

    def _poll_clipboard(self) -> None:
        """Called every 500 ms on the GUI thread.
        win32clipboard is not thread-safe, so we keep this on the main thread.
        """
        if not _HAS_WIN32:
            return
        try:
            win32clipboard.OpenClipboard(0)
            try:
                text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            # Another app may hold the clipboard — silently skip this tick
            return

        if not isinstance(text, str) or not text.strip():
            return

        # Only act if content actually changed
        h = hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()
        if h == self._last_hash:
            return
        self._last_hash = h

        # Deduplicate: remove existing occurrence of same text
        self._history = [t for t in self._history if t.get("text") != text]
        # Prepend new item and save
        self._history.insert(0, {"text": text, "timestamp": time.time()})
        self._save_history(self._history)
        self._refresh_list()

    def _refresh_list(self) -> None:
        self._list.clear()
        today_items = [t for t in self._history if self._is_today(t.get("timestamp", 0))]
        for entry in today_items:
            text = entry.get("text", "")
            preview = text[:60].replace("\n", " ").replace("\r", "")
            if len(text) > 60:
                preview += "…"
            item = QListWidgetItem(preview)
            item.setData(Qt.UserRole, text)   # store full text
            item.setToolTip(text[:200])
            self._list.addItem(item)

    def _restore_item(self, item: QListWidgetItem) -> None:
        """Copy the full stored text back to the clipboard."""
        full = item.data(Qt.UserRole)
        if not full:
            return
        self._restore_text(full)

    def _restore_text(self, text: str) -> None:
        if not _HAS_WIN32:
            return
        try:
            win32clipboard.OpenClipboard(0)
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            # Update hash so we don't re-detect this as a new item
            self._last_hash = hashlib.md5(
                text.encode("utf-8", errors="replace")
            ).hexdigest()
        except Exception as e:
            print(f"[ClipboardWidget] Restore failed: {e}")

    def _show_archive(self) -> None:
        dlg = ClipboardArchiveDialog(self, self)
        dlg.exec_()

    def _clear_history(self) -> None:
        self._history.clear()
        self._last_hash = ""
        self._list.clear()
        self._save_history(self._history)

    def _on_close(self) -> None:
        self._poll_timer.stop()
        super()._on_close()


# ─────────────────────────────────────────────────────────────────────────────
#  Widget 2 — Pomodoro Tracker
# ─────────────────────────────────────────────────────────────────────────────

POMODORO_FILE = get_data_dir() / "pomodoro.json"

def _load_pomodoro_sessions() -> int:
    try:
        with open(POMODORO_FILE, "r", encoding="utf-8") as f:
            return int(json.load(f).get("sessions", 0))
    except Exception:
        return 0

def _save_pomodoro_sessions(n: int) -> None:
    try:
        with open(POMODORO_FILE, "w", encoding="utf-8") as f:
            json.dump({"sessions": n}, f)
    except Exception as e:
        print(f"[PomodoroWidget] Save failed: {e}")


class PomodoroWidget(FloatingWidget):
    """
    25-minute work / 5-minute break Pomodoro timer.
    Uses QTimer (never time.sleep) to tick every second.
    Persists session count to pomodoro.json.
    """
    WIDGET_TYPE = "pomodoro"

    _WORK_SECS  = 25 * 60
    _BREAK_SECS =  5 * 60

    def __init__(self, widget_id: str, data_ref: dict,
                 x: int = 200, y: int = 200):
        super().__init__("🍅  Pomodoro", widget_id, data_ref, x, y)
        self.setFixedWidth(330)
        self._state    = "WORK"           # "WORK" | "BREAK"
        self._running  = False
        self._remaining = self._WORK_SECS
        self._sessions = _load_pomodoro_sessions()
        self._build_pomodoro_ui()

    def _build_pomodoro_ui(self) -> None:
        cl = self._content_layout
        cl.setSpacing(10)
        cl.setContentsMargins(14, 12, 14, 14)

        # State label (WORK / BREAK)
        self._state_lbl = QLabel("WORK SESSION")
        self._state_lbl.setAlignment(Qt.AlignCenter)
        self._state_lbl.setStyleSheet(
            f"font-size:12px; font-weight:700; letter-spacing:2px;"
            f"color:{C_ACCENT};"
        )
        self.add_to_content(self._state_lbl)

        # Big MM:SS display
        self._time_lbl = QLabel()
        self._time_lbl.setObjectName("TimerDisplay")
        self._time_lbl.setAlignment(Qt.AlignCenter)
        self.add_to_content(self._time_lbl)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(8)
        self._progress.setStyleSheet(
            f"QProgressBar{{"
            f"  background: rgba(255,255,255,10);"
            f"  border: none; border-radius: 4px;"
            f"}}"
            f"QProgressBar::chunk{{"
            f"  background: qlineargradient("
            f"    x1:0,y1:0,x2:1,y2:0,"
            f"    stop:0 {C_ACCENT}, stop:1 {C_ACCENT2});"
            f"  border-radius: 4px;"
            f"}}"
        )
        self.add_to_content(self._progress)

        # Start/Pause toggle
        self._toggle_btn = QPushButton("▶  Start")
        self._toggle_btn.clicked.connect(self._toggle)
        self.add_to_content(self._toggle_btn)

        # Reset button
        reset_btn = QPushButton("↺  Reset")
        reset_btn.clicked.connect(self._reset)
        self.add_to_content(reset_btn)

        # Sessions label
        self._session_lbl = QLabel()
        self._session_lbl.setAlignment(Qt.AlignCenter)
        self._session_lbl.setStyleSheet(f"color:{C_ACCENT2}; font-size:12px; font-weight:600;")
        self.add_to_content(self._session_lbl)

        # Tick timer — 1-second intervals, GUI-thread safe
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._tick)

        self._update_display()

    # ── controls ──────────────────────────────────────────────────────────────

    def _toggle(self) -> None:
        global _pomodoro_running
        if self._running:
            self._running = False
            _pomodoro_running = False
            self._tick_timer.stop()
            self._toggle_btn.setText("▶  Resume")
        else:
            self._running = True
            _pomodoro_running = True
            self._tick_timer.start()
            self._toggle_btn.setText("⏸  Pause")

    def _reset(self) -> None:
        global _pomodoro_running
        self._running = False
        _pomodoro_running = False
        self._tick_timer.stop()
        self._state     = "WORK"
        self._remaining = self._WORK_SECS
        self._toggle_btn.setText("▶  Start")
        self._update_display()

    def _tick(self) -> None:
        if self._remaining > 0:
            self._remaining -= 1
            self._update_display()
        if self._remaining == 0:
            self._tick_timer.stop()
            self._running = False
            global _pomodoro_running
            _pomodoro_running = False
            self._on_phase_end()

    def _on_phase_end(self) -> None:
        """Switch phases; increment session counter if WORK just ended."""
        # Set your sound file path here (use a full or relative path)
        sound_file = "pomo.wav"   # <-- change this to your file
        if self._state == "WORK":
            self._sessions += 1
            _save_pomodoro_sessions(self._sessions)
            # Play the sound file asynchronously
            winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
            self._state     = "BREAK"
            self._remaining = self._BREAK_SECS
        else:
            # Play the same sound when going from BREAK to WORK
            winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
            self._state     = "WORK"
            self._remaining = self._WORK_SECS
            
        self._update_display()
        # Auto-start the next phase
        self._toggle()

    def _update_display(self) -> None:
        m, s = divmod(self._remaining, 60)
        self._time_lbl.setText(f"{m:02d}:{s:02d}")

        total = self._WORK_SECS if self._state == "WORK" else self._BREAK_SECS
        elapsed = total - self._remaining
        pct = int(elapsed / total * 100)
        self._progress.setValue(pct)

        if self._state == "WORK":
            self._state_lbl.setText("WORK SESSION")
            self._state_lbl.setStyleSheet(
                f"font-size:12px;font-weight:700;letter-spacing:2px;color:{C_ACCENT};"
            )
            self._time_lbl.setObjectName("TimerDisplay")
        else:
            self._state_lbl.setText("☕  BREAK")
            self._state_lbl.setStyleSheet(
                f"font-size:12px;font-weight:700;letter-spacing:2px;color:{C_ACCENT2};"
            )
            self._time_lbl.setObjectName("TimerDisplay")

        self._time_lbl.style().unpolish(self._time_lbl)
        self._time_lbl.style().polish(self._time_lbl)
        self._session_lbl.setText(f"Sessions completed: {self._sessions}")

    def _on_close(self) -> None:
        global _pomodoro_running
        self._tick_timer.stop()
        self._running = False
        _pomodoro_running = False
        super()._on_close()


# ─────────────────────────────────────────────────────────────────────────────
#  Widget 3 — Interruption Radar
# ─────────────────────────────────────────────────────────────────────────────

# Default whitelist — window title OR exe name contains one of these (case-insensitive)
_RADAR_DEFAULT_WHITELIST = [
    "code", "visual studio", "chrome", "firefox",
    "todoist", "notepad", "word", "excel", "pycharm",
    "terminal", "powershell", "cmd", "widjett", "python", "antigravity ide", 
    "whatsapp", "discord", "yasb", "task switching", "search", "calculator", "notepad++",
    "settings", "task manager",
       
]


class InterruptionRadarWidget(FloatingWidget):
    """
    Monitors the foreground window every second (daemon thread).
    When the active app is NOT in the whitelist while a Pomodoro is running,
    it darkens the wallpaper and plays a chime as a "punishment".
    Tracks distraction count and shows a compact log of the last 3 events.
    """
    WIDGET_TYPE = "radar"

    # Signal carries (window_title, exe_basename)
    _focus_changed = pyqtSignal(str, str)

    def __init__(self, widget_id: str, data_ref: dict,
                 x: int = 200, y: int = 200):
        super().__init__("🎯  Interruption Radar", widget_id, data_ref, x, y)
        self.setFixedWidth(360)

        self._whitelist         = list(_RADAR_DEFAULT_WHITELIST)
        self._distraction_count = 0
        self._distraction_log: list[str] = []   # last N event strings
        self._start_time        = datetime.now()
        self._wallpaper_changed = False
        self._original_wallpaper: str = ""
        self._last_was_distraction = False
        self._stop_monitor = threading.Event()

        self._build_radar_ui()
        self._focus_changed.connect(self._on_focus_changed)
        self._start_monitor_thread()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_radar_ui(self) -> None:
        cl = self._content_layout
        cl.setSpacing(8)

        # Status row
        self._status_lbl = QLabel("👀  Monitoring…")
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setStyleSheet(f"color:{C_ACCENT2}; font-weight:600;")
        self.add_to_content(self._status_lbl)

        # Metrics row
        metrics = QHBoxLayout()
        self._count_lbl = QLabel("Distractions: 0")
        self._count_lbl.setStyleSheet(f"color:{C_TEXT}; font-size:12px;")
        self._rate_lbl  = QLabel("Rate: 0/hr")
        self._rate_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        metrics.addWidget(self._count_lbl)
        metrics.addStretch()
        metrics.addWidget(self._rate_lbl)
        self.add_layout_to_content(metrics)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{C_BORDER}; border:none; max-height:1px;")
        self.add_to_content(sep)

        # Last 3 events log
        log_lbl = QLabel("Recent distractions:")
        log_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px;")
        self.add_to_content(log_lbl)

        self._log_list = QListWidget()
        self._log_list.setMaximumHeight(80)
        self._log_list.setFocusPolicy(Qt.NoFocus)
        self.add_to_content(self._log_list)

        # Whitelist editor — add row
        wl_hdr = QLabel("Whitelist  (double-click to remove)")
        wl_hdr.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px; letter-spacing:0.5px;")
        self.add_to_content(wl_hdr)

        wl_row = QHBoxLayout()
        self._wl_input = QLineEdit()
        self._wl_input.setPlaceholderText("Add app name…")
        add_btn = QPushButton("＋ Add")
        add_btn.setFixedWidth(58)
        add_btn.clicked.connect(self._add_to_whitelist)
        self._wl_input.returnPressed.connect(self._add_to_whitelist)
        wl_row.addWidget(self._wl_input)
        wl_row.addWidget(add_btn)
        self.add_layout_to_content(wl_row)

        # Scrollable whitelist view with remove-on-double-click
        self._wl_list = QListWidget()
        self._wl_list.setMaximumHeight(72)
        self._wl_list.setFocusPolicy(Qt.NoFocus)
        self._wl_list.setToolTip("Double-click an entry to remove it from the whitelist")
        self._wl_list.itemDoubleClicked.connect(self._remove_from_whitelist)
        self.add_to_content(self._wl_list)
        self._refresh_wl_list()

    # ── background monitor thread ──────────────────────────────────────────────

    def _start_monitor_thread(self) -> None:
        t = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
        )
        t.start()

    def _monitor_loop(self) -> None:
        """Background thread: polls foreground window every 1 second."""
        while not self._stop_monitor.is_set():
            if _HAS_WIN32:
                try:
                    hwnd  = win32gui.GetForegroundWindow()
                    title = win32gui.GetWindowText(hwnd)
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    handle = win32api.OpenProcess(
                        0x0400 | 0x0010, False, pid)   # PROCESS_QUERY_INFO | VM_READ
                    exe = win32process.GetModuleFileNameEx(handle, 0)
                    win32api.CloseHandle(handle)
                    exe_base = os.path.basename(exe).lower()
                except Exception:
                    title, exe_base = "", ""
            else:
                title, exe_base = "", ""

            # Emit signal to update GUI safely from the background thread
            self._focus_changed.emit(title, exe_base)
            time.sleep(1)

    def _on_focus_changed(self, title: str, exe_base: str) -> None:
        """Called on the GUI thread via signal-slot."""
        combined = (title + " " + exe_base).lower()
        is_distraction = not any(
            kw.lower() in combined for kw in self._whitelist
        ) and bool(combined.strip())

        if is_distraction and _pomodoro_running:
            if not self._last_was_distraction:
                # First tick of a new distraction
                self._distraction_count += 1
                ts = datetime.now().strftime("%H:%M")
                app_name = title[:30] or exe_base or "Unknown"
                event_str = f"Switched to {app_name!r} at {ts}"
                self._distraction_log.insert(0, event_str)
                self._distraction_log = self._distraction_log[:3]
                self._apply_punishment()
            self._last_was_distraction = True
            self._status_lbl.setText("🚨  DISTRACTED!")
            self._status_lbl.setStyleSheet(
                f"color:#ff4444; font-weight:700; font-size:12px;"
            )
        else:
            if self._last_was_distraction:
                self._restore_wallpaper()
            self._last_was_distraction = False
            self._status_lbl.setText("✅  Focused" if _pomodoro_running else "👀  Monitoring…")
            self._status_lbl.setStyleSheet(
                f"color:{C_ACCENT2}; font-weight:600;"
            )

        self._update_metrics()

    def _update_metrics(self) -> None:
        self._count_lbl.setText(f"Distractions: {self._distraction_count}")
        elapsed_h = max(
            (datetime.now() - self._start_time).total_seconds() / 3600, 0.001
        )
        rate = self._distraction_count / elapsed_h
        self._rate_lbl.setText(f"Rate: {rate:.1f}/hr")

        self._log_list.clear()
        for ev in self._distraction_log:
            self._log_list.addItem(ev)

    # ── wallpaper punishment ──────────────────────────────────────────────────

    def _apply_punishment(self) -> None:
        """Darken the desktop wallpaper and play a chime."""
        if not self._wallpaper_changed:
            # Save current wallpaper path
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.user32.SystemParametersInfoW(
                0x0073,  # SPI_GETDESKWALLPAPER
                len(buf), buf, 0
            )
            self._original_wallpaper = buf.value

            # Set a solid dark-gray BMP as the new wallpaper
            gray_bmp = get_data_dir() / "_distraction_bg.bmp"
            if not gray_bmp.exists():
                self._create_gray_bmp(gray_bmp)

            ctypes.windll.user32.SystemParametersInfoW(
                0x0014,  # SPI_SETDESKWALLPAPER
                0, str(gray_bmp),
                0x0001 | 0x0002  # SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
            )
            self._wallpaper_changed = True

        # Play chime on a background thread to avoid blocking GUI
        threading.Thread(
            target=lambda: winsound.MessageBeep(winsound.MB_ICONHAND),
            daemon=True,
        ).start()

    def _restore_wallpaper(self) -> None:
        """Restore the original wallpaper."""
        if self._wallpaper_changed and self._original_wallpaper:
            ctypes.windll.user32.SystemParametersInfoW(
                0x0014, 0, self._original_wallpaper,
                0x0001 | 0x0002
            )
            self._wallpaper_changed = False

    @staticmethod
    def _create_gray_bmp(path: Path) -> None:
        """Create a tiny solid dark-gray BMP for the distraction wallpaper."""
        import struct
        w, h = 4, 4
        # BMP header + pixel data (BGR, 24-bit, dark gray = 0x2a2a2a)
        row_size = ((w * 3 + 3) & ~3)  # padded to 4-byte boundary
        pixel_data = bytes([0x2a, 0x2a, 0x2a] * w + [0] * (row_size - w * 3)) * h
        file_size  = 54 + len(pixel_data)
        header = struct.pack(
            '<2sIHHIIiIHHIIiiII',
            b'BM', file_size, 0, 0, 54,
            40, w, h, 1, 24, 0,
            len(pixel_data), 2835, 2835, 0, 0
        )
        try:
            with open(path, 'wb') as f:
                f.write(header + pixel_data)
        except Exception as e:
            print(f"[RadarWidget] BMP write failed: {e}")

    # ── whitelist management ───────────────────────────────────────────────────

    def _refresh_wl_list(self) -> None:
        self._wl_list.clear()
        for kw in self._whitelist:
            item = QListWidgetItem(f"  {kw}")
            item.setData(Qt.UserRole, kw)
            self._wl_list.addItem(item)

    def _add_to_whitelist(self) -> None:
        kw = self._wl_input.text().strip().lower()
        if kw and kw not in self._whitelist:
            self._whitelist.append(kw)
            self._refresh_wl_list()
        self._wl_input.clear()

    def _remove_from_whitelist(self, item: QListWidgetItem) -> None:
        kw = item.data(Qt.UserRole)
        if kw and kw in self._whitelist:
            self._whitelist.remove(kw)
            self._refresh_wl_list()

    def _on_close(self) -> None:
        self._stop_monitor.set()
        self._restore_wallpaper()
        super()._on_close()


# ─────────────────────────────────────────────────────────────────────────────
#  Widget 4 — Digital Anthropologist (Keystroke Bio-rhythm)
# ─────────────────────────────────────────────────────────────────────────────

class _WpmCanvas(QWidget):
    """Custom widget that draws a simple heartbeat WPM line graph."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(70)
        self._points: list[int] = []   # WPM history (up to 30 points)

    def update_points(self, pts: list[int]) -> None:
        self._points = pts[-30:]        # keep last 30
        self.update()                   # schedule a repaint

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        # Background
        painter.fillRect(self.rect(), QColor(30, 30, 50, 180))

        pts = self._points
        if len(pts) < 2:
            # Draw a flat zero line while waiting for data
            painter.setPen(QPen(QColor(100, 100, 180, 100), 1))
            painter.drawLine(0, h // 2, w, h // 2)
            painter.end()
            return

        max_wpm = max(max(pts), 1)
        x_step  = w / (len(pts) - 1)
        margin  = 6

        # Gradient fill under the line
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(124, 106, 247, 120))
        grad.setColorAt(1.0, QColor(124, 106, 247,   0))

        from PyQt5.QtGui import QPainterPath
        path = QPainterPath()
        for i, wpm in enumerate(pts):
            x = i * x_step
            y = h - margin - (wpm / max_wpm) * (h - margin * 2)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        # Fill path (close to bottom)
        fill_path = QPainterPath(path)
        fill_path.lineTo((len(pts) - 1) * x_step, h)
        fill_path.lineTo(0, h)
        fill_path.closeSubpath()
        painter.fillPath(fill_path, QBrush(grad))

        # Stroke the line
        painter.setPen(QPen(QColor(124, 106, 247), 2))
        painter.drawPath(path)
        painter.end()


class KeystrokeWidget(FloatingWidget):
    """
    Global keyboard listener (pynput) that tracks WPM and backspace ratio.
    Draws a 30-point heartbeat graph of WPM history.
    Warns about brain-fog if backspace ratio > 40% for 3+ consecutive minutes.
    """
    WIDGET_TYPE = "keystrokes"

    _UPDATE_INTERVAL_MS = 2000    # refresh graph every 2 seconds
    _WINDOW_SECS        = 60      # sliding window duration
    _BRAIN_FOG_THRESH   = 40.0    # % backspaces to trigger warning
    _BRAIN_FOG_MINUTES  = 3       # consecutive minutes above threshold

    def __init__(self, widget_id: str, data_ref: dict,
                 x: int = 200, y: int = 200):
        super().__init__("⌨️  Keystroke Rhythm", widget_id, data_ref, x, y)
        self.setFixedWidth(340)

        # Thread-safe event queue: each item is (timestamp, is_backspace)
        self._key_queue: queue.Queue = queue.Queue()
        # Sliding window: deque of (timestamp, is_backspace)
        self._events: deque = deque()
        # WPM history for graph (30 points max)
        self._wpm_history: list[int] = []
        # Brain-fog tracking: number of consecutive ticks above threshold
        self._fog_ticks: int = 0
        self._listener = None
        self._stop_listener = threading.Event()

        self._build_keystroke_ui()
        self._start_listener()

    def _build_keystroke_ui(self) -> None:
        cl = self._content_layout
        cl.setSpacing(8)

        # WPM + backspace row
        stat_row = QHBoxLayout()
        wpm_box = QVBoxLayout()
        self._wpm_lbl = QLabel("0")
        self._wpm_lbl.setStyleSheet(
            f"font-size:38px; font-weight:700;"
            f"color:{C_ACCENT}; qproperty-alignment:AlignCenter;"
        )
        wpm_sub = QLabel("WPM")
        wpm_sub.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px; qproperty-alignment:AlignCenter;")
        wpm_box.addWidget(self._wpm_lbl)
        wpm_box.addWidget(wpm_sub)

        bs_box = QVBoxLayout()
        self._bs_lbl = QLabel("0%")
        self._bs_lbl.setStyleSheet(
            f"font-size:28px; font-weight:700;"
            f"color:{C_ACCENT2}; qproperty-alignment:AlignCenter;"
        )
        bs_sub = QLabel("Backspace")
        bs_sub.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px; qproperty-alignment:AlignCenter;")
        bs_box.addWidget(self._bs_lbl)
        bs_box.addWidget(bs_sub)

        stat_row.addLayout(wpm_box)
        stat_row.addStretch()
        stat_row.addLayout(bs_box)
        self.add_layout_to_content(stat_row)

        # Heartbeat canvas
        self._canvas = _WpmCanvas()
        self.add_to_content(self._canvas)

        # pynput unavailable — show persistent notice
        if not _HAS_PYNPUT:
            no_pynput = QLabel("⚠  pynput not installed.\nRun: pip install pynput")
            no_pynput.setWordWrap(True)
            no_pynput.setAlignment(Qt.AlignCenter)
            no_pynput.setStyleSheet(
                "background: rgba(200,160,30,160); border-radius:8px;"
                "color:#1a1a00; font-weight:700; padding:8px; font-size:11px;"
            )
            self.add_to_content(no_pynput)

        # Brain-fog warning (hidden by default)
        self._fog_lbl = QLabel("🧠 Brain fog detected. Stand up for 60 seconds.")
        self._fog_lbl.setWordWrap(True)
        self._fog_lbl.setAlignment(Qt.AlignCenter)
        self._fog_lbl.setStyleSheet(
            "background: rgba(235,75,75,190); border-radius:9px;"
            f"color:white; font-weight:700; padding:7px; font-size:11px;"
        )
        self._fog_lbl.hide()
        self.add_to_content(self._fog_lbl)

        # Update timer — drains key_queue and refreshes display every 2 s
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(self._UPDATE_INTERVAL_MS)
        self._update_timer.timeout.connect(self._update_stats)
        self._update_timer.start()

    # ── keyboard listener ─────────────────────────────────────────────────────

    def _start_listener(self) -> None:
        if not _HAS_PYNPUT:
            return
        # pynput listener runs in its own daemon thread automatically
        self._listener = _pynput_kb.Listener(
            on_press=self._on_key_press,
            daemon=True,
        )
        self._listener.start()

    def _on_key_press(self, key) -> None:
        """Called from pynput's background thread — only enqueue, never touch GUI."""
        is_bs = (key == _pynput_kb.Key.backspace)
        self._key_queue.put((time.time(), is_bs))

    # ── stats refresh (GUI thread, every 2 s) ─────────────────────────────────

    def _update_stats(self) -> None:
        # Drain the queue
        while not self._key_queue.empty():
            try:
                self._events.append(self._key_queue.get_nowait())
            except queue.Empty:
                break

        # Trim events older than 60 seconds
        cutoff = time.time() - self._WINDOW_SECS
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

        total   = len(self._events)
        backsp  = sum(1 for _, is_bs in self._events if is_bs)
        chars   = total - backsp

        # Net WPM = chars / 5 (standard word length) over 60-second window
        wpm     = int((chars / 5) * (60 / self._WINDOW_SECS))
        bs_pct  = (backsp / total * 100) if total > 0 else 0.0

        self._wpm_history.append(wpm)
        self._wpm_history = self._wpm_history[-30:]

        self._wpm_lbl.setText(str(wpm))
        self._bs_lbl.setText(f"{bs_pct:.0f}%")
        self._canvas.update_points(self._wpm_history)

        # Brain-fog: count consecutive ticks over threshold
        # Each tick is 2 s → 3 min = 90 s = 45 ticks
        ticks_per_min = 60 / (self._UPDATE_INTERVAL_MS / 1000)
        threshold_ticks = int(self._BRAIN_FOG_MINUTES * ticks_per_min)

        if bs_pct > self._BRAIN_FOG_THRESH:
            self._fog_ticks += 1
        else:
            self._fog_ticks = 0

        self._fog_lbl.setVisible(self._fog_ticks >= threshold_ticks)

    def _on_close(self) -> None:
        self._update_timer.stop()
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
        super()._on_close()


# ─────────────────────────────────────────────────────────────────────────────
#  Widget 5 — Desktop Topography (File-System Radar)
# ─────────────────────────────────────────────────────────────────────────────

class _FolderEventHandler(_FSHandler if _HAS_WATCHDOG else object):
    """Watchdog event handler — puts a sentinel into a queue on any FS event."""
    def __init__(self, q: queue.Queue):
        if _HAS_WATCHDOG:
            super().__init__()
        self._q = q

    def on_any_event(self, event) -> None:  # noqa: N802
        self._q.put(1)  # just a wake-up signal


class TopographyWidget(FloatingWidget):
    """
    Monitors Downloads and Desktop folders for file changes.
    Shows total file counts, clutter scores, and a "Run Vacuum" button that
    renames files older than 7 days with a YYYY-MM-DD_ prefix.
    """
    WIDGET_TYPE = "topography"

    _STALE_DAYS = 7

    def __init__(self, widget_id: str, data_ref: dict,
                 x: int = 200, y: int = 200):
        super().__init__("🗂️  Desktop Topography", widget_id, data_ref, x, y)
        self.setFixedWidth(360)

        user_home = Path.home()
        self._folders = {
            "Downloads": user_home / "Downloads",
            "Desktop":   user_home / "Desktop",
        }

        self._fs_queue: queue.Queue = queue.Queue()
        self._observer = None
        self._activity_log: list[str] = []

        self._build_topography_ui()
        self._start_watchdog()

        # Refresh timer — polls queue and updates counts every 2 seconds
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(2000)
        self._refresh_timer.timeout.connect(self._maybe_refresh)
        self._refresh_timer.start()
        self._refresh_stats()  # initial population

    def _build_topography_ui(self) -> None:
        cl = self._content_layout
        cl.setSpacing(8)

        # Per-folder rows
        self._folder_labels: dict[str, QLabel] = {}
        self._clutter_labels: dict[str, QLabel] = {}

        for name in self._folders:
            row = QHBoxLayout()
            name_lbl = QLabel(f"📁 {name}")
            name_lbl.setStyleSheet(f"font-weight:600; color:{C_TEXT};")
            count_lbl = QLabel("— files")
            count_lbl.setStyleSheet(f"color:{C_ACCENT}; font-weight:700;")
            clutter_lbl = QLabel("Clutter: —")
            clutter_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
            row.addWidget(name_lbl)
            row.addStretch()
            row.addWidget(count_lbl)
            self.add_layout_to_content(row)

            clutter_row = QHBoxLayout()
            clutter_row.addSpacing(16)
            clutter_row.addWidget(clutter_lbl)
            self.add_layout_to_content(clutter_row)

            self._folder_labels[name]  = count_lbl
            self._clutter_labels[name] = clutter_lbl

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{C_BORDER}; border:none; max-height:1px;")
        self.add_to_content(sep)

        # Vacuum button
        self._vacuum_btn = QPushButton("🧹 Run Vacuum")
        self._vacuum_btn.setStyleSheet(
            f"QPushButton{{background:rgba(124,106,247,140);border-color:{C_ACCENT};}}"
            f"QPushButton:hover{{background:rgba(124,106,247,220);}}"
        )
        self._vacuum_btn.clicked.connect(self._run_vacuum)
        self.add_to_content(self._vacuum_btn)

        # Activity log
        log_lbl = QLabel("Activity:")
        log_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px;")
        self.add_to_content(log_lbl)

        self._log_list = QListWidget()
        self._log_list.setMaximumHeight(72)
        self._log_list.setFocusPolicy(Qt.NoFocus)
        self.add_to_content(self._log_list)

    # ── watchdog setup ────────────────────────────────────────────────────────

    def _start_watchdog(self) -> None:
        if not _HAS_WATCHDOG:
            return
        handler  = _FolderEventHandler(self._fs_queue)
        self._observer = _WatchdogObserver()
        for folder in self._folders.values():
            if folder.exists():
                self._observer.schedule(handler, str(folder), recursive=False)
        self._observer.start()

    # ── stats ─────────────────────────────────────────────────────────────────

    def _maybe_refresh(self) -> None:
        """Drain the FS event queue; only refresh stats if something changed."""
        changed = False
        while not self._fs_queue.empty():
            try:
                self._fs_queue.get_nowait()
                changed = True
            except queue.Empty:
                break
        if changed:
            self._refresh_stats()

    def _refresh_stats(self) -> None:
        cutoff = datetime.now() - timedelta(days=self._STALE_DAYS)
        for name, folder in self._folders.items():
            if not folder.exists():
                self._folder_labels[name].setText("Not found")
                self._clutter_labels[name].setText("Clutter: N/A")
                continue

            try:
                files = [f for f in folder.iterdir() if f.is_file()]
            except PermissionError:
                files = []

            total = len(files)
            stale = sum(
                1 for f in files
                if datetime.fromtimestamp(f.stat().st_mtime) < cutoff
            )
            score = int(stale / total * 100) if total > 0 else 0

            self._folder_labels[name].setText(f"{total} files")
            color = "#ff6b6b" if score > 50 else C_ACCENT2 if score > 20 else C_TEXT_DIM
            self._clutter_labels[name].setText(
                f"Clutter Score: {score}%"
            )
            self._clutter_labels[name].setStyleSheet(
                f"color:{color}; font-size:11px;"
            )

    # ── vacuum ────────────────────────────────────────────────────────────────

    def _run_vacuum(self) -> None:
        """Spawn a background thread to rename stale files."""
        self._vacuum_btn.setEnabled(False)
        self._vacuum_btn.setText("🔄 Running…")
        threading.Thread(target=self._vacuum_worker, daemon=True).start()

    def _vacuum_worker(self) -> None:
        renamed = 0
        cutoff = datetime.now() - timedelta(days=self._STALE_DAYS)
        for folder in self._folders.values():
            if not folder.exists():
                continue
            try:
                files = [f for f in folder.iterdir() if f.is_file()]
            except PermissionError:
                continue
            for f in files:
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if mtime < cutoff:
                        prefix = mtime.strftime("%Y-%m-%d")
                        new_name = folder / f"{prefix}_{f.name}"
                        if not new_name.exists():   # don't overwrite
                            f.rename(new_name)
                            renamed += 1
                except Exception as e:
                    print(f"[TopographyWidget] Rename error: {e}")

        # Check CPU; if idle, suggest a task in tasks.txt
        idle_note = ""
        if _HAS_PSUTIL:
            try:
                cpu = _psutil.cpu_percent(interval=0.5)
                if cpu < 10 and renamed > 0:
                    tasks_path = get_data_dir() / "tasks.txt"
                    note = (
                        f"{datetime.now():%Y-%m-%d %H:%M}  "
                        f"Sort {renamed} old files from Downloads/Desktop\n"
                    )
                    with open(tasks_path, "a", encoding="utf-8") as fp:
                        fp.write(note)
                    idle_note = " (task logged)"
            except Exception:
                pass

        # Update GUI from background thread via QTimer.singleShot
        msg = f"Vacuum: renamed {renamed} files{idle_note}"
        QTimer.singleShot(0, lambda: self._vacuum_done(msg))

    def _vacuum_done(self, msg: str) -> None:
        self._vacuum_btn.setEnabled(True)
        self._vacuum_btn.setText("🧹 Run Vacuum")
        ts = datetime.now().strftime("%H:%M")
        self._activity_log.insert(0, f"[{ts}] {msg}")
        self._activity_log = self._activity_log[:5]
        self._log_list.clear()
        for entry in self._activity_log:
            self._log_list.addItem(entry)
        self._refresh_stats()

    def _on_close(self) -> None:
        self._refresh_timer.stop()
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass
        super()._on_close()


# ─────────────────────────────────────────────────────────────────────────────
#  Widget 6 — Mood Mosaic (Time-Adaptive Color Clock)
# ─────────────────────────────────────────────────────────────────────────────

# Word-of-the-day by time period
_MOOD_WORDS = {
    "morning":   "Wake-Up",
    "afternoon": "Work",
    "evening":   "Relax",
    "night":     "Work",
}


def _hour_to_hsl(hour: int, minute: int = 0) -> tuple[float, float, float]:
    """
    Map the current hour (0–23) to an HSL colour (h∈[0,360], s∈[0,1], l∈[0,1]).
    Returns (hue_deg, saturation, lightness).
    """
    frac = minute / 60.0
    t    = hour + frac  # fractional hour 0..24

    if 6 <= t < 12:           # Morning: Peach/Orange → Bright Yellow
        s = (t - 6) / 6.0
        hue = 30 + s * (55 - 30)
        return hue, 0.85, 0.60

    elif 12 <= t < 18:        # Afternoon: Crisp Blue → Teal
        s = (t - 12) / 6.0
        hue = 195 - s * (195 - 180)
        return hue, 0.75, 0.55

    elif 18 <= t < 24:        # Evening: Sunset Orange → Midnight Purple
        s = (t - 18) / 6.0
        hue = 25 - s * (25 - (-80))   # wraps: 25 → -80 → equals 280
        hue = hue % 360
        return hue, 0.80, 0.45

    else:                     # Night (0–6): Deep dark indigo
        return 260, 0.60, 0.15


def _hsl_to_qt_color(h: float, s: float, l: float) -> QColor:
    """Convert HSL (h∈[0,360], s∈[0,1], l∈[0,1]) → QColor."""
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l, s)  # colorsys uses HLS order
    return QColor(int(r * 255), int(g * 255), int(b * 255))


class MoodMosaicWidget(FloatingWidget):
    """
    A large gradient tile that changes colour based on the time of day.
    Hovering shows a tooltip with the exact time and a word of the day.
    """
    WIDGET_TYPE = "moodmosaic"

    def __init__(self, widget_id: str, data_ref: dict,
                 x: int = 250, y: int = 100):
        # Pre-initialise before super().__init__() so eventFilter (which is
        # wired to the title bar inside FloatingWidget.__init__) never sees a
        # missing attribute if a mouse event arrives before _build_mosaic_ui.
        self._tile             = None
        self._current_time_str = ""
        self._current_period   = "morning"
        super().__init__("🎨  Mood Mosaic", widget_id, data_ref, x, y)
        self.setFixedWidth(280)
        self._build_mosaic_ui()

    def _build_mosaic_ui(self) -> None:
        cl = self._content_layout
        cl.setSpacing(0)
        cl.setContentsMargins(0, 0, 0, 0)

        # The colour tile — a QLabel we paint manually
        self._tile = QLabel()
        self._tile.setFixedSize(252, 210)
        self._tile.setAlignment(Qt.AlignCenter)
        self._tile.setCursor(QCursor(Qt.PointingHandCursor))

        # Enable mouse tracking for hover tooltip
        self._tile.setMouseTracking(True)
        self._tile.installEventFilter(self)

        self.add_to_content(self._tile)

        # Mood word label at the bottom of the tile
        self._mood_lbl = QLabel()
        self._mood_lbl.setAlignment(Qt.AlignCenter)
        self._mood_lbl.setStyleSheet(
            "font-size:11px; font-weight:700; letter-spacing:2px; "
            "color:rgba(255,255,255,180);"
        )
        self.add_to_content(self._mood_lbl)

        # Tick every second
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start()
        self._tick()

    def _tick(self) -> None:
        now  = datetime.now()
        h, s, l = _hour_to_hsl(now.hour, now.minute)

        # Compute the second colour (slightly shifted hue for gradient effect)
        h2 = (h + 20) % 360
        c1 = _hsl_to_qt_color(h, s, l)
        c2 = _hsl_to_qt_color(h2, s * 0.9, min(l + 0.12, 1.0))

        # Build gradient stylesheet for the tile
        self._tile.setStyleSheet(
            f"background: qlineargradient("
            f"  x1:0, y1:0, x2:1, y2:1,"
            f"  stop:0 {c1.name()}, stop:1 {c2.name()}"
            f");"
            f"border-radius: 8px;"
        )

        # Determine time period for mood word
        hour = now.hour
        if 6 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 18:
            period = "afternoon"
        elif 18 <= hour < 24:
            period = "evening"
        else:
            period = "night"

        self._mood_lbl.setText(_MOOD_WORDS[period].upper())
        self._mood_lbl.setStyleSheet(
            f"font-size:11px; font-weight:700; letter-spacing:3px;"
            f"color:rgba(255,255,255,{180 if l > 0.3 else 220});"
        )

        # Store for tooltip
        self._current_time_str = now.strftime("%H:%M:%S")
        self._current_period   = period

    def eventFilter(self, obj, event):
        """Show a tooltip when hovering over the colour tile.
        Guard: _tile may be None while FloatingWidget.__init__ is still
        running (title-bar events can arrive before _build_mosaic_ui).
        """
        if self._tile is not None and obj is self._tile:
            if event.type() == QEvent.Enter or event.type() == QEvent.MouseMove:
                word = _MOOD_WORDS.get(self._current_period, "")
                tip  = f"{self._current_time_str}  •  {word}"
                QToolTip.showText(QCursor.pos(), tip, self._tile)
                return False  # let normal processing continue
        return super().eventFilter(obj, event)

    def _on_close(self) -> None:
        self._tick_timer.stop()
        super()._on_close()


# ─────────────────────────────────────────────────────────────────────────────
#  Smart Notes Floating Widget  (singleton)
# ─────────────────────────────────────────────────────────────────────────────

class SmartNotesFloatingWidget(FloatingWidget):
    """
    Thin FloatingWidget shell that hosts the SmartNotesWidget panel.
    Singleton — only one instance allowed at a time.
    """
    WIDGET_TYPE = "smartnotes"

    def __init__(self, widget_id: str, data_ref: dict,
                 x: int = 200, y: int = 200):
        super().__init__("📒  Smart Notes", widget_id, data_ref, x, y)
        self.setMinimumWidth(560)
        self.setMinimumHeight(500)
        self.resize(560, 580)
        self._build_notes_ui()

    def _build_notes_ui(self) -> None:
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)

        if _HAS_SMARTNOTES:
            self._notes_panel = _SmartNotesWidget(self._content_widget)
            self._notes_panel.setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Expanding
            )
            self.add_to_content(self._notes_panel)
        else:
            err = QLabel(
                "⚠️  SmartNotesWidget could not be loaded.\n"
                "Check that widgets/smartnotes.py is present."
            )
            err.setAlignment(Qt.AlignCenter)
            err.setStyleSheet(f"color: {C_ACCENT3}; font-size: 12px;")
            self.add_to_content(err)

    def _apply_saved_colors(self) -> None:
        super()._apply_saved_colors()
        if hasattr(self, '_notes_panel') and hasattr(self._notes_panel, 'apply_theme'):
            colors = self._data_ref.get("hub_colors")
            if colors and "header" in colors and "body" in colors:
                self._notes_panel.apply_theme(colors["header"], colors["body"])
            else:
                self._notes_panel.apply_theme(None, None)


# ─────────────────────────────────────────────────────────────────────────────
#  General Settings Dialog
# ─────────────────────────────────────────────────────────────────────────────

def _apply_global_font(font_name: str) -> None:
    """Updates the GLOBAL_QSS with the new font and re-applies to the QApplication."""
    global GLOBAL_QSS
    import re
    family = next((f for n, f in _FONT_OPTIONS if n == font_name), _FONT_OPTIONS[0][1])
    # Replace the existing font-family declaration in QWidget { ... }
    GLOBAL_QSS = re.sub(
        r'font-family:\s*[^;]+;',
        f'font-family: {family};',
        GLOBAL_QSS
    )
    app = QApplication.instance()
    if app:
        app.setStyleSheet(GLOBAL_QSS)


# Curated font list: (display name, font-family CSS string)
_FONT_OPTIONS = [
    ("Inter (Default)",    '"Inter", "Segoe UI Variable Display", "Segoe UI", "Roboto", sans-serif'),
    ("Segoe UI Variable",  '"Segoe UI Variable Display", "Segoe UI", sans-serif'),
    ("Roboto",             '"Roboto", "Segoe UI", sans-serif'),
    ("Poppins",            '"Poppins", "Segoe UI", sans-serif'),
    ("Outfit",             '"Outfit", "Segoe UI", sans-serif'),
    ("JetBrains Mono",     '"JetBrains Mono", "Consolas", "Courier New", monospace'),
    ("Courier New",        '"Courier New", monospace'),
]


class _GeneralSettingsDialog(QDialog):
    """
    General Settings panel with two tabs:
      • Appearance — widget color theme + font selection
      • Startup    — toggle Windows auto-launch on login
    All changes are persisted to data.json.
    """

    def __init__(self, card: QFrame, data_ref: dict, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._card     = card
        self._data_ref = data_ref

        # Colors (copied so we don't mutate data_ref until Apply)
        colors = self._data_ref.get("hub_colors", {})
        self._header_rgba = list(colors.get("header", [24, 24, 38, 248]))
        self._body_rgba   = list(colors.get("body",   [14, 14, 22, 240]))

        # Font
        saved_font_name = self._data_ref.get("hub_font", "Inter (Default)")
        self._selected_font_name = saved_font_name

        self._drag_pos = QPoint()
        self._dragging = False
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        card = QFrame()
        card.setObjectName("DialogCard")
        card.installEventFilter(self)

        # Apply hub theme colors to the dialog card
        colors = self._data_ref.get("hub_colors", {})
        hr = colors.get("header", [24, 24, 38, 248])
        br = colors.get("body",   [14, 14, 22, 240])
        card.setStyleSheet(
            f"#DialogCard {{"
            f"  background: qlineargradient("
            f"    x1:0, y1:0, x2:0, y2:1,"
            f"    stop:0 rgba({hr[0]},{hr[1]},{hr[2]},{min(hr[3], 252)}),"
            f"    stop:0.3 rgba({br[0]},{br[1]},{br[2]},{min(br[3], 252)})"
            f"  );"
            f"  border: 1px solid rgba({hr[0]},{hr[1]},{hr[2]},120);"
            f"  border-radius: 16px;"
            f"}}"
        )
        self._dialog_card = card
        vlay = QVBoxLayout(card)
        vlay.setContentsMargins(20, 16, 20, 18)
        vlay.setSpacing(12)

        # ── dialog header ─────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        hdr = QLabel("⚙️  General Settings")
        hdr.setStyleSheet(f"font-size:15px; font-weight:800; color:{C_TEXT};")
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()
        x_btn = QPushButton("✕")
        x_btn.setObjectName("CloseBtn")
        x_btn.setFixedSize(26, 26)
        x_btn.clicked.connect(self.reject)
        hdr_row.addWidget(x_btn)
        vlay.addLayout(hdr_row)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{C_BORDER}; border:none; max-height:1px;")
        vlay.addWidget(sep)

        # ── tab widget ────────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid rgba(255,255,255,18);
                border-radius: 10px;
                background: rgba(255,255,255,4);
                margin-top: -1px;
            }}
            QTabBar::tab {{
                background: rgba(255,255,255,6);
                color: {C_TEXT_DIM};
                border: 1px solid rgba(255,255,255,20);
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 7px 20px;
                font-size: 12px;
                font-weight: 600;
                margin-right: 3px;
            }}
            QTabBar::tab:selected {{
                background: rgba(157,141,245,130);
                color: {C_TEXT};
                border-color: {C_ACCENT};
            }}
            QTabBar::tab:hover:!selected {{
                background: rgba(157,141,245,50);
                color: {C_TEXT};
            }}
        """)
        vlay.addWidget(tabs)

        tabs.addTab(self._build_appearance_tab(), "🎨  Appearance")
        tabs.addTab(self._build_startup_tab(),    "⚙️  Startup")

        # ── bottom action buttons ─────────────────────────────────────────────
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"background:{C_BORDER}; border:none; max-height:1px;")
        vlay.addWidget(sep2)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        reset_btn = QPushButton("↺  Reset Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        apply_btn = QPushButton("✓  Apply")
        apply_btn.setStyleSheet(
            f"QPushButton {{background:rgba(157,141,245,200);"
            f"border:1px solid {C_ACCENT};border-radius:9px;"
            f"padding:6px 18px;color:white;font-weight:700;}}"
            f"QPushButton:hover {{background:rgba(157,141,245,255);}}"
        )
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(apply_btn)
        vlay.addLayout(btn_row)

        outer.addWidget(card)
        self.setMinimumWidth(420)

    # ── Appearance tab ────────────────────────────────────────────────────────

    def _build_appearance_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)

        # ── Colors section ────────────────────────────────────────────────────
        lay.addWidget(self._make_section_label("Widget Colors"))

        # Header color row
        lay.addWidget(self._make_subsection_label("Header Background"))
        self._header_preview = self._make_color_preview(self._header_rgba)
        self._header_alpha   = self._make_alpha_spinbox(self._header_rgba[3])
        self._header_alpha.valueChanged.connect(
            lambda v: self._update_preview(self._header_preview, self._header_rgba, self._header_alpha)
        )
        row_h = QHBoxLayout(); row_h.setSpacing(8)
        pick_h = QPushButton("Pick Color")
        pick_h.setFixedWidth(90)
        pick_h.clicked.connect(self._pick_header_color)
        row_h.addWidget(self._header_preview)
        row_h.addWidget(pick_h)
        row_h.addWidget(QLabel("Alpha:"))
        row_h.addWidget(self._header_alpha)
        row_h.addStretch()
        lay.addLayout(row_h)

        # Body color row
        lay.addWidget(self._make_subsection_label("Body Background"))
        self._body_preview = self._make_color_preview(self._body_rgba)
        self._body_alpha   = self._make_alpha_spinbox(self._body_rgba[3])
        self._body_alpha.valueChanged.connect(
            lambda v: self._update_preview(self._body_preview, self._body_rgba, self._body_alpha)
        )
        row_b = QHBoxLayout(); row_b.setSpacing(8)
        pick_b = QPushButton("Pick Color")
        pick_b.setFixedWidth(90)
        pick_b.clicked.connect(self._pick_body_color)
        row_b.addWidget(self._body_preview)
        row_b.addWidget(pick_b)
        row_b.addWidget(QLabel("Alpha:"))
        row_b.addWidget(self._body_alpha)
        row_b.addStretch()
        lay.addLayout(row_b)

        tip = QLabel("Set alpha to 0 for a fully transparent background.")
        tip.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px;")
        lay.addWidget(tip)

        # separator
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{C_BORDER}; border:none; max-height:1px; margin:4px 0;")
        lay.addWidget(sep)

        # ── Font section ──────────────────────────────────────────────────────
        lay.addWidget(self._make_section_label("App Font"))

        font_row = QHBoxLayout(); font_row.setSpacing(10)

        self._font_combo = QComboBox()
        self._font_combo.setFixedHeight(32)
        self._font_combo.setStyleSheet(f"""
            QComboBox {{
                background: rgba(255,255,255,8);
                border: 1px solid rgba(255,255,255,22);
                border-radius: 8px;
                padding: 4px 10px;
                color: {C_TEXT};
                font-size: 12px;
            }}
            QComboBox:focus {{
                border-color: {C_ACCENT};
                background: rgba(157,141,245,15);
            }}
            QComboBox::drop-down {{
                border: none;
                width: 28px;
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 0;
            }}
            QComboBox QAbstractItemView {{
                background: rgba(28,28,42,248);
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                color: {C_TEXT};
                selection-background-color: rgba(157,141,245,130);
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 12px;
                border-radius: 5px;
            }}
        """)

        # Populate and pre-select
        for name, _ in _FONT_OPTIONS:
            self._font_combo.addItem(name)
        saved = self._data_ref.get("hub_font", "Inter (Default)")
        idx = next((i for i, (n, _) in enumerate(_FONT_OPTIONS) if n == saved), 0)
        self._font_combo.setCurrentIndex(idx)
        self._font_combo.currentIndexChanged.connect(self._on_font_changed)

        font_row.addWidget(self._font_combo, 1)
        lay.addLayout(font_row)

        # Live preview label
        self._font_preview = QLabel("The quick brown fox jumps over the lazy dog  0123456789")
        self._font_preview.setWordWrap(True)
        self._font_preview.setStyleSheet(
            f"color:{C_TEXT}; font-size:12px;"
            f"background:rgba(255,255,255,5); border:1px solid rgba(255,255,255,12);"
            f"border-radius:8px; padding:8px 10px;"
        )
        self._update_font_preview()
        lay.addWidget(self._font_preview)

        lay.addStretch()
        return page

    # ── Startup tab ───────────────────────────────────────────────────────────

    def _build_startup_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(14, 18, 14, 14)
        lay.setSpacing(14)

        lay.addWidget(self._make_section_label("Windows Startup"))

        # Toggle row
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(12)

        self._startup_check = QCheckBox("Launch Widjett when Windows starts")
        self._startup_check.setStyleSheet(f"""
            QCheckBox {{
                font-size: 13px;
                color: {C_TEXT};
                spacing: 10px;
            }}
            QCheckBox::indicator {{
                width: 20px; height: 20px; border-radius: 6px;
                border: 1px solid rgba(255,255,255,40);
                background: rgba(255,255,255,7);
            }}
            QCheckBox::indicator:checked {{
                background: {C_ACCENT};
                border-color: {C_ACCENT};
            }}
            QCheckBox::indicator:hover {{
                border-color: {C_ACCENT};
            }}
        """)

        is_frozen = getattr(sys, 'frozen', False)
        if is_frozen:
            self._startup_check.setChecked(_is_startup_registered())
            self._startup_check.setEnabled(True)
            self._startup_check.stateChanged.connect(self._on_startup_toggled)
        else:
            self._startup_check.setChecked(False)
            self._startup_check.setEnabled(False)

        toggle_row.addWidget(self._startup_check)
        toggle_row.addStretch()
        lay.addLayout(toggle_row)

        # Info / status label
        if is_frozen:
            info_text = (
                "When enabled, Widjett will automatically start in the system tray\n"
                "every time you log into Windows. You can disable this at any time."
            )
        else:
            info_text = (
                "ℹ️  Startup control is only available in the packaged EXE.\n"
                "Run the installed version of Widjett to manage this setting."
            )
        info_lbl = QLabel(info_text)
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet(
            f"color:{C_TEXT_DIM}; font-size:11px;"
            f"background:rgba(255,255,255,5); border:1px solid rgba(255,255,255,10);"
            f"border-radius:8px; padding:10px 12px;"
        )
        lay.addWidget(info_lbl)

        lay.addStretch()
        return page

    # ── helpers ───────────────────────────────────────────────────────────────

    def _make_section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{C_TEXT}; font-size:13px; font-weight:800; letter-spacing:0.5px;"
            f"padding-bottom:2px;"
        )
        return lbl

    def _make_subsection_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px; font-weight:600;")
        return lbl

    def _make_color_preview(self, rgba: list) -> QLabel:
        lbl = QLabel()
        lbl.setFixedSize(36, 28)
        lbl.setStyleSheet(
            f"background: rgba({rgba[0]},{rgba[1]},{rgba[2]},{rgba[3]});"
            "border: 1px solid rgba(255,255,255,40); border-radius: 6px;"
        )
        return lbl

    def _make_alpha_spinbox(self, value: int) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(0, 255)
        sp.setValue(value)
        sp.setFixedWidth(64)
        sp.setFocusPolicy(Qt.StrongFocus)
        return sp

    def _update_preview(self, preview: QLabel, rgba: list, alpha_spin: QSpinBox):
        rgba[3] = alpha_spin.value()
        preview.setStyleSheet(
            f"background: rgba({rgba[0]},{rgba[1]},{rgba[2]},{rgba[3]});"
            "border: 1px solid rgba(255,255,255,40); border-radius: 6px;"
        )

    # ── font helpers ──────────────────────────────────────────────────────────

    def _on_font_changed(self, index: int) -> None:
        self._selected_font_name = _FONT_OPTIONS[index][0]
        self._update_font_preview()

    def _update_font_preview(self) -> None:
        name = self._selected_font_name
        family = next((f for n, f in _FONT_OPTIONS if n == name), _FONT_OPTIONS[0][1])
        self._font_preview.setStyleSheet(
            f"font-family: {family}; font-size:12px; color:{C_TEXT};"
            f"background:rgba(255,255,255,5); border:1px solid rgba(255,255,255,12);"
            f"border-radius:8px; padding:8px 10px;"
        )

    # ── startup toggle ────────────────────────────────────────────────────────

    def _on_startup_toggled(self, state: int) -> None:
        """Immediately write/remove the registry key on toggle."""
        if state == Qt.Checked:
            register_startup()
        else:
            unregister_startup()

    # ── color pickers ─────────────────────────────────────────────────────────

    def _get_color(self, title: str, init_rgba: list) -> QColor:
        dlg = QColorDialog(QColor(init_rgba[0], init_rgba[1], init_rgba[2], init_rgba[3]), self)
        dlg.setWindowTitle(title)
        dlg.setOption(QColorDialog.ShowAlphaChannel)
        dlg.setStyleSheet("""
            QColorDialog { background: #1c1c2a; }
            QLabel { color: #eeeef8; background: transparent; }
            QPushButton {
                background: #2b2b3b; color: #eeeef8;
                border: 1px solid rgba(255,255,255,40);
                padding: 4px 12px; border-radius: 4px;
            }
            QPushButton:hover { background: #3b3b4b; }
            QSpinBox { background: rgba(255,255,255,10); color: #eeeef8; border: 1px solid rgba(255,255,255,30); }
            QLineEdit { background: rgba(255,255,255,10); color: #eeeef8; }
        """)
        if dlg.exec_() == QDialog.Accepted:
            return dlg.currentColor()
        return QColor()

    def _pick_header_color(self) -> None:
        col = self._get_color("Header Background Color", self._header_rgba)
        if col.isValid():
            self._header_rgba = [col.red(), col.green(), col.blue(), col.alpha()]
            self._header_alpha.setValue(col.alpha())
            self._update_preview(self._header_preview, self._header_rgba, self._header_alpha)

    def _pick_body_color(self) -> None:
        col = self._get_color("Body Background Color", self._body_rgba)
        if col.isValid():
            self._body_rgba = [col.red(), col.green(), col.blue(), col.alpha()]
            self._body_alpha.setValue(col.alpha())
            self._update_preview(self._body_preview, self._body_rgba, self._body_alpha)

    # ── apply / reset ─────────────────────────────────────────────────────────

    def _apply(self) -> None:
        # Sync alpha spinboxes
        self._header_rgba[3] = self._header_alpha.value()
        self._body_rgba[3]   = self._body_alpha.value()

        # Save colors
        self._data_ref["hub_colors"] = {
            "header": list(self._header_rgba),
            "body":   list(self._body_rgba),
        }

        # Save font
        self._data_ref["hub_font"] = self._selected_font_name
        save_data(self._data_ref)

        # Trigger global color update on the Launcher
        parent = self.parent()
        if hasattr(parent, "_apply_saved_hub_colors"):
            parent._apply_saved_hub_colors()

        # Apply font app-wide immediately
        _apply_global_font(self._selected_font_name)

        self.accept()

    def _reset_defaults(self) -> None:
        # Reset colors
        self._header_rgba = [24, 24, 38, 248]
        self._body_rgba   = [14, 14, 22, 240]
        self._update_preview(self._header_preview, self._header_rgba, self._header_alpha)
        self._header_alpha.setValue(248)
        self._update_preview(self._body_preview, self._body_rgba, self._body_alpha)
        self._body_alpha.setValue(240)

        # Reset font combo to default
        self._font_combo.setCurrentIndex(0)
        self._selected_font_name = _FONT_OPTIONS[0][0]
        self._update_font_preview()

        # Persist reset
        self._data_ref.pop("hub_colors", None)
        self._data_ref.pop("hub_font", None)
        save_data(self._data_ref)

        # Propagate
        parent = self.parent()
        if hasattr(parent, "_apply_saved_hub_colors"):
            parent._apply_saved_hub_colors()

        _apply_global_font(_FONT_OPTIONS[0][0])

    # ── drag to move dialog ───────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            return True
        elif event.type() == QEvent.MouseMove and self._dragging:
            self.move(event.globalPos() - self._drag_pos)
            return True
        elif event.type() == QEvent.MouseButtonRelease:
            self._dragging = False
            return True
        return super().eventFilter(obj, event)


# ─────────────────────────────────────────────────────────────────────────────
#  Launcher
# ─────────────────────────────────────────────────────────────────────────────


import calendar
import requests
import threading

# ─────────────────────────────────────────────────────────────────────────────
#  Calendar Widget
# ─────────────────────────────────────────────────────────────────────────────
class CalendarWidget(FloatingWidget):
    WIDGET_TYPE = "calendar"

    def __init__(self, widget_id: str, data_ref: dict, x: int = 200, y: int = 200):
        self._data_file = get_data_dir() / "calendar_events.json"
        self._events = self._load_events()
        
        self.current_date = datetime.now().date()
        self.display_year = self.current_date.year
        self.display_month = self.current_date.month
        
        self._day_labels = []

        super().__init__("📅  Calendar", widget_id, data_ref, x, y)
        self.setFixedWidth(380)

    def _load_events(self) -> dict:
        try:
            if self._data_file.exists():
                with open(self._data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_events(self) -> None:
        try:
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(self._events, f, indent=2)
        except Exception as e:
            print(f"[Calendar] Save failed: {e}")

    def _build_ui(self) -> None:
        super()._build_ui()
        self._content_layout.setContentsMargins(12, 12, 12, 12)
        self._content_layout.setSpacing(10)

        # Header
        h_row = QHBoxLayout()
        self._prev_btn = QPushButton("<")
        self._prev_btn.setFixedSize(30, 30)
        self._prev_btn.setStyleSheet(f"background:rgba(255,255,255,10); border:none; border-radius:15px; color:{C_TEXT}; font-weight:bold; font-size:16px; padding:0; margin:0;")
        self._prev_btn.clicked.connect(self._prev_month)
        
        self._month_btn = QPushButton()
        self._month_btn.setCursor(Qt.PointingHandCursor)
        self._month_btn.setStyleSheet(f"background:transparent; border:none; font-size:16px; font-weight:bold; color:{C_TEXT}; padding:0; margin:0;")
        self._month_btn.clicked.connect(self._select_month_year)
        
        self._next_btn = QPushButton(">")
        self._next_btn.setFixedSize(30, 30)
        self._next_btn.setStyleSheet(f"background:rgba(255,255,255,10); border:none; border-radius:15px; color:{C_TEXT}; font-weight:bold; font-size:16px; padding:0; margin:0;")
        self._next_btn.clicked.connect(self._next_month)
        
        h_row.addWidget(self._prev_btn)
        h_row.addWidget(self._month_btn, 1)
        h_row.addWidget(self._next_btn)
        self._content_layout.addLayout(h_row)

        # Days of week header
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        d_row = QHBoxLayout()
        d_row.setSpacing(4)
        for d in days:
            lbl = QLabel(d)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"font-size:11px; font-weight:bold; color:{C_TEXT_DIM};")
            d_row.addWidget(lbl)
        self._content_layout.addLayout(d_row)

        # Grid for days
        self._grid = QGridLayout()
        self._grid.setSpacing(4)
        self._content_layout.addLayout(self._grid)
        
        self._update_calendar()

    def _prev_month(self):
        if self.display_month == 1:
            self.display_month = 12
            self.display_year -= 1
        else:
            self.display_month -= 1
        self._update_calendar()

    def _next_month(self):
        if self.display_month == 12:
            self.display_month = 1
            self.display_year += 1
        else:
            self.display_month += 1
        self._update_calendar()

    def _update_calendar(self):
        # Clear grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        month_name = calendar.month_name[self.display_month]
        self._month_btn.setText(f"{month_name} {self.display_year}")

        cal = calendar.monthcalendar(self.display_year, self.display_month)
        
        for row, week in enumerate(cal):
            for col, day in enumerate(week):
                if day == 0:
                    continue
                    
                date_str = f"{self.display_year}-{self.display_month:02d}-{day:02d}"
                is_today = (self.display_year == self.current_date.year and 
                            self.display_month == self.current_date.month and 
                            day == self.current_date.day)
                            
                btn = QPushButton(str(day))
                btn.setFixedSize(40, 40)
                
                has_event = date_str in self._events and self._events[date_str].strip()
                
                # Styles
                bg = f"rgba({C_ACCENT}, 200)" if is_today else "rgba(255,255,255,10)"
                fg = "white" if is_today else C_TEXT
                border = f"1px solid {C_ACCENT}" if has_event else "1px solid transparent"
                font_weight = "bold" if is_today else "normal"
                
                btn.setStyleSheet(
                    f"QPushButton{{"
                    f"background:{bg}; "
                    f"border:{border}; "
                    f"border-radius:20px; "
                    f"color:{fg}; "
                    f"font-weight:{font_weight}; "
                    f"font-size:14px; "
                    f"padding:0px; "
                    f"margin:0px; "
                    f"outline:none;"
                    f"}}"
                    f"QPushButton:hover{{background:rgba(255,255,255,30);}}"
                )
                
                btn.clicked.connect(lambda checked, d=date_str: self._on_day_click(d))
                self._grid.addWidget(btn, row, col)

    def _select_month_year(self):
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        dlg.setAttribute(Qt.WA_TranslucentBackground, True)
        dlg.setFixedSize(260, 200)
        
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0,0,0,0)
        
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{C_BG}; border:1px solid rgba(255,255,255,30); border-radius:10px;}}")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(15, 15, 15, 15)
        
        title = QLabel("Jump to Date")
        title.setStyleSheet(f"font-size:14px; font-weight:bold; color:{C_TEXT}; border:none;")
        c_lay.addWidget(title)
        
        h_lay = QHBoxLayout()
        month_cb = QComboBox()
        month_cb.addItems(list(calendar.month_name)[1:])
        month_cb.setCurrentIndex(self.display_month - 1)
        month_cb.setStyleSheet(f"background:rgba(255,255,255,10); color:{C_TEXT}; border:1px solid rgba(255,255,255,20); border-radius:4px; padding:4px;")
        
        year_sb = QSpinBox()
        year_sb.setRange(1900, 2100)
        year_sb.setValue(self.display_year)
        year_sb.setStyleSheet(f"background:rgba(255,255,255,10); color:{C_TEXT}; border:1px solid rgba(255,255,255,20); border-radius:4px; padding:4px;")
        
        h_lay.addWidget(month_cb, 1)
        h_lay.addWidget(year_sb, 1)
        c_lay.addLayout(h_lay)
        
        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Go")
        ok_btn.setStyleSheet(f"background:rgba({C_ACCENT}, 180); font-weight:bold; padding:6px; border-radius:6px; color:white;")
        ok_btn.clicked.connect(dlg.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"background:rgba(255,255,255,20); padding:6px; border-radius:6px; color:{C_TEXT};")
        cancel_btn.clicked.connect(dlg.reject)
        
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        c_lay.addLayout(btn_row)
        
        lay.addWidget(card)
        
        if dlg.exec_() == QDialog.Accepted:
            self.display_month = month_cb.currentIndex() + 1
            self.display_year = year_sb.value()
            self._update_calendar()


    def _on_day_click(self, date_str: str):
        existing = self._events.get(date_str, "")
        
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dlg.setAttribute(Qt.WA_TranslucentBackground, True)
        dlg.setFixedSize(300, 300)
        
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0,0,0,0)
        
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{C_BG}; border:1px solid rgba(255,255,255,30); border-radius:10px;}}")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(15, 15, 15, 15)
        
        title = QLabel(f"Events for {date_str}")
        title.setStyleSheet(f"font-size:14px; font-weight:bold; color:{C_TEXT}; border:none;")
        c_lay.addWidget(title)
        
        text_edit = QTextEdit()
        text_edit.setPlainText(existing)
        text_edit.setStyleSheet(f"background:rgba(255,255,255,10); color:{C_TEXT}; border:1px solid rgba(255,255,255,20); border-radius:6px; padding:6px;")
        c_lay.addWidget(text_edit)
        
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"background:rgba({C_ACCENT}, 180); font-weight:bold; padding:6px; border-radius:6px;")
        save_btn.clicked.connect(dlg.accept)
        
        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet(f"background:rgba(235,75,75,180); font-weight:bold; padding:6px; border-radius:6px;")
        del_btn.clicked.connect(dlg.reject)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"background:rgba(255,255,255,20); padding:6px; border-radius:6px;")
        cancel_btn.clicked.connect(lambda: dlg.done(2))
        
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        c_lay.addLayout(btn_row)
        
        lay.addWidget(card)
        
        res = dlg.exec_()
        if res == QDialog.Accepted:
            val = text_edit.toPlainText().strip()
            if val:
                self._events[date_str] = val
            elif date_str in self._events:
                del self._events[date_str]
            self._save_events()
            self._update_calendar()
        elif res == QDialog.Rejected:
            if date_str in self._events:
                del self._events[date_str]
                self._save_events()
                self._update_calendar()

class LocationDialog(QDialog):
    def __init__(self, current_city: str, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.city = current_city
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        
        card = QFrame()
        card.setObjectName("DialogCard")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(20, 20, 20, 20)
        c_lay.setSpacing(12)
        
        lbl = QLabel("Location Settings")
        lbl.setStyleSheet(f"font-size:16px; font-weight:bold; color:{C_TEXT};")
        c_lay.addWidget(lbl)
        
        sub = QLabel("Enter City (e.g., 'London, UK' or 'New York, USA')")
        sub.setStyleSheet(f"font-size:12px; color:{C_TEXT_DIM};")
        c_lay.addWidget(sub)
        
        self.input_field = QLineEdit(self.city)
        self.input_field.setPlaceholderText("City, Country")
        self.input_field.setStyleSheet(f"background:rgba(255,255,255,10); color:{C_TEXT}; padding:8px; border-radius:4px;")
        c_lay.addWidget(self.input_field)
        
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"background:{C_ACCENT}; color:white;")
        save_btn.clicked.connect(self.accept)
        
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        c_lay.addLayout(btn_row)
        
        lay.addWidget(card)

# ─────────────────────────────────────────────────────────────────────────────
#  Prayer Times Widget
# ─────────────────────────────────────────────────────────────────────────────
class PrayerTimesWidget(FloatingWidget):
    WIDGET_TYPE = "prayer"

    def __init__(self, widget_id: str, data_ref: dict, x: int = 200, y: int = 200):
        self._data_file = get_data_dir() / "prayer_settings.json"
        self._settings = self._load_settings()
        
        self.prayer_times = {}
        self.current_prayer = None
        self.next_prayer = None
        self.last_fetch_date = None
        
        self.prayer_names = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        self._prayer_cards = {}
        
        super().__init__("🕌  Prayer Times", widget_id, data_ref, x, y)
        self.setFixedWidth(340)
        
        # Thread-safe queue for results from background fetch thread
        self._fetch_queue: queue.Queue = queue.Queue()
        
        if self._settings.get("city"):
            self._fetch_times()
            
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._tick)
        self._update_timer.start(1000)

    def _load_settings(self) -> dict:
        try:
            if self._data_file.exists():
                with open(self._data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {"city": "London, UK"}

    def _save_settings(self) -> None:
        try:
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            print(f"[Prayer] Save failed: {e}")

    def _build_ui(self) -> None:
        super()._build_ui()
        self._content_layout.setContentsMargins(12, 12, 12, 12)
        self._content_layout.setSpacing(10)
        
        h_row = QHBoxLayout()
        self._city_lbl = QLabel(self._settings.get("city", "City not set"))
        self._city_lbl.setStyleSheet(f"font-size:14px; font-weight:bold; color:{C_TEXT};")
        
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(28, 28)
        settings_btn.setToolTip("Location Settings")
        settings_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,12); border: 1px solid rgba(255,255,255,20);"
            f" border-radius: 7px; font-size: 14px; color: {C_TEXT}; padding: 0; }}"
            f"QPushButton:hover {{ background: rgba(157,141,245,160); border-color: {C_ACCENT}; }}"
        )
        settings_btn.clicked.connect(self._open_settings)
        
        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setToolTip("Refresh prayer times")
        refresh_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,12); border: 1px solid rgba(255,255,255,20);"
            f" border-radius: 7px; font-size: 16px; color: {C_TEXT}; padding: 0; }}"
            f"QPushButton:hover {{ background: rgba(93,214,181,160); border-color: {C_ACCENT2}; }}"
        )
        refresh_btn.clicked.connect(self._fetch_times)
        
        h_row.addWidget(self._city_lbl, 1)
        h_row.addWidget(settings_btn)
        h_row.addWidget(refresh_btn)
        self._content_layout.addLayout(h_row)
        
        self._countdown_lbl = QLabel("Fetching times...")
        self._countdown_lbl.setAlignment(Qt.AlignCenter)
        self._countdown_lbl.setStyleSheet(f"font-size:12px; font-style:italic; color:{C_ACCENT2};")
        self._content_layout.addWidget(self._countdown_lbl)
        
        for prayer in self.prayer_names:
            card = QFrame()
            card.setStyleSheet("QFrame{background:rgba(255,255,255,8); border-radius:8px;}")
            c_lay = QHBoxLayout(card)
            c_lay.setContentsMargins(16, 12, 16, 12)
            
            n_lbl = QLabel(prayer)
            n_lbl.setStyleSheet("font-size:14px; background:transparent; border:none;")
            
            t_lbl = QLabel("--:--")
            t_lbl.setStyleSheet("font-size:14px; font-weight:bold; background:transparent; border:none;")
            
            c_lay.addWidget(n_lbl)
            c_lay.addStretch()
            c_lay.addWidget(t_lbl)
            
            self._content_layout.addWidget(card)
            self._prayer_cards[prayer] = {"card": card, "name": n_lbl, "time": t_lbl}
            
    def _open_settings(self):
        dlg = LocationDialog(self._settings.get("city", ""), self)
        
        if dlg.exec_():
            new_city = dlg.input_field.text().strip()
            if new_city:
                self._settings["city"] = new_city
                self._city_lbl.setText(new_city)
                self._save_settings()
                self._fetch_times()

    def _fetch_times(self):
        city = self._settings.get("city")
        if not city:
            return
        if not _HAS_REQUESTS:
            self._countdown_lbl.setText("\u274c 'requests' not installed")
            return
        self._countdown_lbl.setText("Fetching prayer times...")

        def run_fetch():
            import urllib.parse
            encoded_city = urllib.parse.quote(city)
            url = f"http://api.aladhan.com/v1/timingsByAddress?address={encoded_city}"
            try:
                resp = _requests.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 200:
                    t = data["data"]["timings"]
                    res = {p: t.get(p) for p in self.prayer_names}
                    self._fetch_queue.put(("ok", res))
                else:
                    msg = str(data.get("data", "Location not found"))[:40]
                    self._fetch_queue.put(("err", f"\u274c {msg}"))
            except Exception as e:
                err = str(e)
                print(f"[Prayer] Fetch error: {err}")
                self._fetch_queue.put(("err", f"\u274c Network error: {err[:30]}"))

        threading.Thread(target=run_fetch, daemon=True).start()

    def _tick(self):
        """Called every second — drains the fetch queue then updates the countdown."""
        while not self._fetch_queue.empty():
            try:
                kind, payload = self._fetch_queue.get_nowait()
                if kind == "ok":
                    self._on_fetch_success(payload)
                else:
                    self._countdown_lbl.setText(payload)
            except queue.Empty:
                break
        # Daily re-fetch
        if self.last_fetch_date and self.last_fetch_date != datetime.now().date():
            self._fetch_times()
        self._update_countdown()


    def _on_fetch_success(self, res: dict):
        self.prayer_times = res
        self.last_fetch_date = datetime.now().date()
        for p, t in self.prayer_times.items():
            if t:
                self._prayer_cards[p]["time"].setText(t)
        self._calc_next()

    def _calc_next(self):
        if not self.prayer_times:
            return
            
        now = datetime.now()
        
        self.next_prayer = None
        self.current_prayer = None
        
        pts = []
        for p in self.prayer_names:
            t_str = self.prayer_times.get(p)
            if t_str:
                h, m = map(int, t_str.split(':'))
                dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                pts.append((p, dt))
                
        pts.sort(key=lambda x: x[1])
        
        for i, (p, dt) in enumerate(pts):
            if dt > now:
                self.next_prayer = (p, dt)
                if i > 0:
                    self.current_prayer = pts[i-1][0]
                else:
                    self.current_prayer = "Isha"
                break
                
        if not self.next_prayer and pts:
            tomorrow_fajr = pts[0][1] + timedelta(days=1)
            self.next_prayer = (pts[0][0], tomorrow_fajr)
            self.current_prayer = "Isha"
            
        for p in self.prayer_names:
            c = self._prayer_cards[p]
            if p == self.current_prayer:
                c["card"].setStyleSheet(f"QFrame{{background:rgba({C_ACCENT}, 150); border-radius:8px;}}")
                c["name"].setStyleSheet(f"font-size:14px; font-weight:bold; color:white; background:transparent; border:none;")
                c["time"].setStyleSheet(f"font-size:14px; font-weight:bold; color:white; background:transparent; border:none;")
            else:
                c["card"].setStyleSheet("QFrame{background:rgba(255,255,255,8); border-radius:8px;}")
                c["name"].setStyleSheet(f"font-size:14px; color:{C_TEXT}; background:transparent; border:none;")
                c["time"].setStyleSheet(f"font-size:14px; font-weight:bold; color:{C_TEXT}; background:transparent; border:none;")

    def _update_countdown(self):
        if self.next_prayer:
            now = datetime.now()
            nxt_name, nxt_dt = self.next_prayer

            diff = (nxt_dt - now).total_seconds()
            if diff <= 0:
                self._calc_next()
            else:
                h, rem = divmod(int(diff), 3600)
                m, s = divmod(rem, 60)
                t_str = f"{h}h {m}m {s}s" if h > 0 else f"{m}m {s}s"
                self._countdown_lbl.setText(f"Next: {nxt_name} in {t_str}")


class Launcher(QWidget):
    def __init__(self, data_ref: dict):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._data_ref  = data_ref
        self._widgets: list[FloatingWidget] = []
        self._next_id   = 1
        self._drag_pos  = QPoint()
        self._dragging  = False

        # Singleton tracking
        self._clock_widget:     ClockWidget              | None = None
        self._todo_widget:      TodoWidget               | None = None
        self._clipboard_widget: ClipboardWidget          | None = None
        self._pomodoro_widget:  PomodoroWidget           | None = None
        self._radar_widget:     InterruptionRadarWidget  | None = None
        self._keystroke_widget: KeystrokeWidget          | None = None
        self._topography_widget:TopographyWidget         | None = None
        self._notes_widget:     SmartNotesFloatingWidget | None = None
        self._calendar_widget:  CalendarWidget           | None = None
        self._prayer_widget:    PrayerTimesWidget        | None = None

        self._build_ui()
        self._build_tray()
        self._restore_widgets()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        self._card = QFrame()
        self._card.setObjectName("Launcher")
        cv = QVBoxLayout(self._card)
        cv.setContentsMargins(20, 18, 20, 20)
        cv.setSpacing(10)

        # header row
        hrow = QHBoxLayout()
        ico = QLabel()
        pixmap = QPixmap(str(get_asset_path("logo.png"))).scaled(
            32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        ico.setPixmap(pixmap)
        hrow.addWidget(ico)
        tcol = QVBoxLayout()
        t = QLabel("WIDJETT")
        t.setObjectName("LauncherTitle")
        s = QLabel("Desktop Widgets Manager")
        s.setObjectName("LauncherSub")
        tcol.addWidget(t)
        tcol.addWidget(s)
        hrow.addLayout(tcol)
        hrow.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setToolTip("Minimize to tray")
        close_btn.clicked.connect(self.hide)
        hrow.addWidget(close_btn)
        cv.addLayout(hrow)

        # ── spawn buttons (keep: clock, timer, todo, clipboard, notes) ─────────
        self._btn_clock = self._make_launch_btn(
            "🕐  Add Clock Widget",  self._spawn_clock,     "#7c6af7")
        self._btn_timer = self._make_launch_btn(
            "⏱  Add Timer & Alarm", self._spawn_timer,     "#56cfb2")
        self._btn_todo  = self._make_launch_btn(
            "📝  Add To-Do Widget",  self._spawn_todo,      "#f79c6a")
        self._btn_clipboard = self._make_launch_btn(
            "📋  Clipboard History", self._spawn_clipboard, "#a78bfa")
        self._btn_notes = self._make_launch_btn(
            "📒  Smart Notes",       self._spawn_notes,     "#9d8df5")
        self._btn_calendar = self._make_launch_btn(
            "📅  Calendar",           self._spawn_calendar,   "#3b82f6")
        self._btn_prayer = self._make_launch_btn(
            "🕌  Prayer Times",       self._spawn_prayer,     "#10b981")


        # Keep hidden button attrs for close-map compatibility
        self._btn_pomodoro   = None
        self._btn_radar      = None
        self._btn_keystroke  = None
        self._btn_topography = None

        cv.addWidget(self._btn_clock)
        cv.addWidget(self._btn_timer)
        cv.addWidget(self._btn_todo)
        cv.addWidget(self._btn_clipboard)
        cv.addWidget(self._btn_notes)
        cv.addWidget(self._btn_calendar)
        cv.addWidget(self._btn_prayer)

        # separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{C_BORDER}; border:none; max-height:1px; margin:2px 0;")
        cv.addWidget(sep)

        # Customize button
        self._btn_customize = QPushButton("⚙️  General Settings")
        self._btn_customize.setObjectName("LaunchBtn")
        self._btn_customize.setStyleSheet(
            "#LaunchBtn { text-align: left; }"
            "#LaunchBtn:hover { border-left: 3px solid #f472b6; }"
        )
        self._btn_customize.clicked.connect(self._open_customize)
        cv.addWidget(self._btn_customize)

        outer.addWidget(self._card)
        self.setFixedWidth(330)

        self._card.installEventFilter(self)
        
        # Apply custom colors if they were saved previously
        self._apply_saved_hub_colors()


    def _make_launch_btn(self, label: str, slot, color: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("LaunchBtn")
        btn.clicked.connect(slot)
        # left accent stripe on hover
        base = btn.styleSheet()
        btn.setStyleSheet(
            base + f"\n#LaunchBtn:hover{{border-left:3px solid {color};}}"
        )
        return btn

    # ── tray ──────────────────────────────────────────────────────────────────

    def _build_tray(self) -> None:
        self._tray = QSystemTrayIcon(QApplication.instance().windowIcon(), self)
        self._tray.setToolTip("Widjett")

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: rgba(28,28,42,248);
                color: {C_TEXT};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{ padding: 6px 20px; border-radius:4px; }}
            QMenu::item:selected {{ background: rgba(124,106,247,160); }}
        """)
        show_act = QAction("Show Launcher", self)
        show_act.triggered.connect(lambda: (self.show(), self.raise_(), self.activateWindow()))
        quit_act = QAction("Quit", self)
        quit_act.triggered.connect(self._quit)
        menu.addAction(show_act)
        menu.addSeparator()
        menu.addAction(quit_act)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()

    def _quit(self) -> None:
        save_data(self._data_ref)
        QApplication.quit()

    # ── dragging (entire launcher card) ──────────────────────────────────────

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            return True
        elif event.type() == QEvent.MouseMove and self._dragging:
            self.move(event.globalPos() - self._drag_pos)
            return True
        elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self._dragging = False
            return True
        return super().eventFilter(obj, event)

    # ── close → tray ─────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()

    # ── widget spawning ───────────────────────────────────────────────────────

    def _next_widget_id(self) -> str:
        _id = f"w{self._next_id}"
        self._next_id += 1
        return _id

    def _default_pos(self) -> tuple[int, int]:
        screen = QApplication.primaryScreen().availableGeometry()
        offset = len(self._widgets) * 28
        return screen.x() + 80 + offset, screen.y() + 80 + offset

    def _register(self, w: FloatingWidget, wtype: str,
                   x: int, y: int) -> None:
        """Connect signals and save to persistence."""
        w.closed.connect(self._on_widget_closed)
        w.show()
        w.raise_()
        w.activateWindow()
        self._widgets.append(w)
        if not any(e.get("id") == w._widget_id for e in self._data_ref["widgets"]):
            self._data_ref["widgets"].append(
                {"id": w._widget_id, "type": wtype, "x": x, "y": y}
            )
            save_data(self._data_ref)

    def _spawn_clock(self) -> None:
        if self._clock_widget is not None:
            # Bring existing one to front
            self._clock_widget.raise_()
            self._clock_widget.activateWindow()
            return
        x, y = self._default_pos()
        w = ClockWidget(self._next_widget_id(), self._data_ref, x, y)
        self._clock_widget = w
        self._btn_clock.setEnabled(False)
        self._btn_clock.setToolTip("Clock is already open")
        self._register(w, "clock", x, y)

    def _spawn_timer(self) -> None:
        x, y = self._default_pos()
        w = TimerWidget(self._next_widget_id(), self._data_ref, x, y)
        self._register(w, "timer", x, y)

    def _spawn_todo(self) -> None:
        if self._todo_widget is not None:
            self._todo_widget.raise_()
            self._todo_widget.activateWindow()
            return
        x, y = self._default_pos()
        w = TodoWidget(self._next_widget_id(), self._data_ref, x, y)
        self._todo_widget = w
        self._btn_todo.setEnabled(False)
        self._btn_todo.setToolTip("To-Do list is already open")
        self._register(w, "todo", x, y)

    # ── New widget spawners ───────────────────────────────────────────────────

    def _spawn_singleton(self, attr: str, cls, btn_attr: str,
                          label: str, type_key: str) -> None:
        """Generic singleton spawn helper used by all new widgets."""
        existing = getattr(self, attr)
        if existing is not None:
            existing.raise_()
            existing.activateWindow()
            return
        x, y = self._default_pos()
        w = cls(self._next_widget_id(), self._data_ref, x, y)
        setattr(self, attr, w)
        btn = getattr(self, btn_attr, None)
        if btn is not None:
            btn.setEnabled(False)
            btn.setToolTip(f"{label} is already open")
        self._register(w, type_key, x, y)


    def _spawn_calendar(self)      -> None:
        self._spawn_singleton(
            "_calendar_widget", CalendarWidget,
            "_btn_calendar", "Calendar", "calendar")

    def _spawn_prayer(self)        -> None:
        self._spawn_singleton(
            "_prayer_widget", PrayerTimesWidget,
            "_btn_prayer", "Prayer Times", "prayer")

    def _spawn_clipboard(self)  -> None:
        self._spawn_singleton(
            "_clipboard_widget", ClipboardWidget,
            "_btn_clipboard", "Clipboard History", "clipboard")

    def _spawn_pomodoro(self)   -> None:
        self._spawn_singleton(
            "_pomodoro_widget", PomodoroWidget,
            "_btn_pomodoro", "Pomodoro", "pomodoro")

    def _spawn_radar(self)      -> None:
        self._spawn_singleton(
            "_radar_widget", InterruptionRadarWidget,
            "_btn_radar", "Interruption Radar", "radar")

    def _spawn_keystroke(self)  -> None:
        self._spawn_singleton(
            "_keystroke_widget", KeystrokeWidget,
            "_btn_keystroke", "Keystroke Rhythm", "keystrokes")

    def _spawn_topography(self) -> None:
        self._spawn_singleton(
            "_topography_widget", TopographyWidget,
            "_btn_topography", "Desktop Topography", "topography")

    def _spawn_notes(self)      -> None:
        self._spawn_singleton(
            "_notes_widget", SmartNotesFloatingWidget,
            "_btn_notes", "Smart Notes", "smartnotes")

    # ── hub customization ─────────────────────────────────────────────────────

    def _open_customize(self) -> None:
        """Open the General Settings dialog."""
        dlg = _GeneralSettingsDialog(self._card, self._data_ref, self)
        dlg.exec_()

    def _apply_saved_hub_colors(self) -> None:
        """Applies saved colors to the Launcher hub card and propagates to all open widgets."""
        colors = self._data_ref.get("hub_colors")
        if colors and "header" in colors and "body" in colors:
            hr = colors["header"]
            br = colors["body"]
            self._card.setStyleSheet(
                f"#Launcher {{"
                f"  background: qlineargradient("
                f"    x1:0, y1:0, x2:0, y2:0.25,"
                f"    stop:0 rgba({hr[0]},{hr[1]},{hr[2]},{hr[3]}),"
                f"    stop:0.25 rgba({br[0]},{br[1]},{br[2]},{br[3]})"
                f"  );"
                f"  border: 1px solid rgba(110,100,170,120);"
                f"  border-radius: 18px;"
                f"}}"
            )
        else:
            self._card.setStyleSheet("")
            
        # Propagate to all open widgets
        for w in self._widgets:
            if hasattr(w, "_apply_saved_colors"):
                w._apply_saved_colors()

    def _on_widget_closed(self, w: FloatingWidget) -> None:
        if w in self._widgets:
            self._widgets.remove(w)

        # Map widget class → (attr name, button attr name)
        _close_map = [
            (ClockWidget,                "_clock_widget",      "_btn_clock"),
            (TodoWidget,                 "_todo_widget",       "_btn_todo"),
            (ClipboardWidget,            "_clipboard_widget",  "_btn_clipboard"),
            (PomodoroWidget,             "_pomodoro_widget",   "_btn_pomodoro"),
            (InterruptionRadarWidget,    "_radar_widget",      "_btn_radar"),
            (KeystrokeWidget,            "_keystroke_widget",  "_btn_keystroke"),
            (TopographyWidget,           "_topography_widget", "_btn_topography"),
            (SmartNotesFloatingWidget,   "_notes_widget",      "_btn_notes"),
            (CalendarWidget,             "_calendar_widget",   "_btn_calendar"),
            (PrayerTimesWidget,          "_prayer_widget",     "_btn_prayer"),
        ]
        for cls, attr, btn_attr in _close_map:
            if isinstance(w, cls):
                setattr(self, attr, None)
                btn = getattr(self, btn_attr)
                if btn is not None:
                    btn.setEnabled(True)
                    btn.setToolTip("")
                break

    # ── restore saved widgets ─────────────────────────────────────────────────

    def _restore_widgets(self) -> None:
        TYPE_MAP = {
            "clock":      ClockWidget,
            "timer":      TimerWidget,
            "todo":       TodoWidget,
            "clipboard":  ClipboardWidget,
            "pomodoro":   PomodoroWidget,
            "radar":      InterruptionRadarWidget,
            "keystrokes": KeystrokeWidget,
            "topography": TopographyWidget,
            "smartnotes": SmartNotesFloatingWidget,
        }
        for entry in list(self._data_ref.get("widgets", [])):
            cls = TYPE_MAP.get(entry.get("type"))
            if cls is None:
                continue

            # Singleton enforcement during restore
            if cls is ClockWidget and self._clock_widget is not None:
                continue
            if cls is TodoWidget and self._todo_widget is not None:
                continue

            wid = entry.get("id", self._next_widget_id())
            try:
                n = int(wid.lstrip("w"))
                if n >= self._next_id:
                    self._next_id = n + 1
            except Exception:
                pass

            x, y = entry.get("x", 200), entry.get("y", 200)
            w = cls(wid, self._data_ref, x, y)
            w.closed.connect(self._on_widget_closed)
            w.show()
            w.raise_()
            w.activateWindow()
            self._widgets.append(w)

            # Update singleton references and disable launch buttons
            _restore_map = [
                (ClockWidget,                "_clock_widget",      "_btn_clock",      "Clock"),
                (TodoWidget,                 "_todo_widget",       "_btn_todo",       "To-Do"),
                (ClipboardWidget,            "_clipboard_widget",  "_btn_clipboard",  "Clipboard History"),
                (PomodoroWidget,             "_pomodoro_widget",   "_btn_pomodoro",   "Pomodoro"),
                (InterruptionRadarWidget,    "_radar_widget",      "_btn_radar",      "Interruption Radar"),
                (KeystrokeWidget,            "_keystroke_widget",  "_btn_keystroke",  "Keystroke Rhythm"),
                (TopographyWidget,           "_topography_widget", "_btn_topography", "Desktop Topography"),
                (SmartNotesFloatingWidget,   "_notes_widget",      "_btn_notes",      "Smart Notes"),
            ]
            for rcls, attr, btn_attr, label in _restore_map:
                if cls is rcls:
                    setattr(self, attr, w)
                    btn = getattr(self, btn_attr)
                    if btn is not None:
                        btn.setEnabled(False)
                        btn.setToolTip(f"{label} is already open")
                    break


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
#  Single-instance guard
# ─────────────────────────────────────────────────────────────────────────────

def _acquire_single_instance_mutex() -> object:
    """
    Creates a named Windows mutex.  Returns the handle on success.
    If the mutex already exists another instance is running — we exit.
    Only active when frozen (EXE); ignored in dev mode so you can run
    multiple terminals without locking yourself out.
    """
    if not getattr(sys, 'frozen', False):
        return None
    try:
        handle = ctypes.windll.kernel32.CreateMutexW(None, True, "WidjettSingleInstanceMutex")
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            sys.exit(0)   # already running — silently exit
        return handle
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Windows startup registration  (HKCU — no admin required)
# ─────────────────────────────────────────────────────────────────────────────

_STARTUP_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
_STARTUP_NAME = "Widjett"


def _is_startup_registered() -> bool:
    """Return True if our Run entry already exists and matches the current EXE path."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_KEY) as key:
            val, _ = winreg.QueryValueEx(key, _STARTUP_NAME)
            return val == f'"{sys.executable}"'
    except FileNotFoundError:
        return False
    except Exception:
        return False


def register_startup() -> None:
    """
    Write the current EXE into the HKCU Run key so Windows launches
    Widjett automatically on every login.  Called once on first run;
    subsequent launches skip the check after confirming it is already set.
    Only runs when frozen (i.e. packaged as an EXE).
    """
    if not getattr(sys, 'frozen', False):
        return  # dev mode — do nothing

    if _is_startup_registered():
        return  # already set up

    exe_path = f'"{sys.executable}"'
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _STARTUP_KEY,
            0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, _STARTUP_NAME, 0, winreg.REG_SZ, exe_path)
        print(f"[INFO] Widjett registered for startup: {exe_path}")
    except Exception as e:
        print(f"[WARN] Could not register startup entry: {e}")


def unregister_startup() -> None:
    """Remove Widjett from the HKCU Run key (disable auto-launch on login)."""
    if not getattr(sys, 'frozen', False):
        return  # dev mode — do nothing
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _STARTUP_KEY,
            0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _STARTUP_NAME)
        print("[INFO] Widjett removed from startup.")
    except FileNotFoundError:
        pass  # wasn't registered — fine
    except Exception as e:
        print(f"[WARN] Could not remove startup entry: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── Single-instance guard (EXE only) ─────────────────────────────────────
    _mutex = _acquire_single_instance_mutex()

    # ── Register as a Windows startup app on first run ────────────────────────
    register_startup()

    # ── Set AppUserModelID so Windows taskbar groups and shows the right icon ─
    if os.name == 'nt':
        myappid = 'viewsonic.widjett.app.1'
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(GLOBAL_QSS)

    app_icon = QIcon(str(get_asset_path("logo.png")))
    app.setWindowIcon(app_icon)

    data     = load_data()
    
    # Load and apply custom font if set
    saved_font = data.get("hub_font")
    if saved_font:
        _apply_global_font(saved_font)
        
    launcher = Launcher(data)
    FloatingWidget.show_hub = lambda: (launcher.show(), launcher.raise_(), launcher.activateWindow())
    launcher.show()
    launcher.raise_()
    launcher.activateWindow()

    # Centre launcher
    screen = QApplication.primaryScreen().availableGeometry()
    launcher.move(
        screen.center().x() - launcher.width()  // 2,
        screen.center().y() - launcher.height() // 2,
    )

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
