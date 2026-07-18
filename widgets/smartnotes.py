# -*- coding: utf-8 -*-
"""
SmartNotesWidget — Google Keep-style sticky notes
=================================================
Features
--------
* Create / edit / delete notes (title + body)
* 12-colour palette per note
* Pinned notes float to the top of the grid
* Real-time search bar filters by title or body
* Double-click a card to open a full edit dialog
* Auto-saves to  <APPDATA>/widjett/notes.json  with a 600 ms debounce
  (saves happen on a background thread so the UI never freezes)
* Single Python class: SmartNotesWidget(parent_frame)
  — can be embedded in any QFrame / QWidget as a child
"""

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import (
    Qt, QTimer, QPoint, QEvent, pyqtSignal, QSize, QPropertyAnimation,
    QEasingCurve,
)
from PyQt5.QtGui import (
    QColor, QFont, QPainter, QBrush, QPen, QLinearGradient, QIcon,
    QPixmap, QPainterPath,
)
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QTextEdit, QScrollArea, QFrame, QSizePolicy,
    QGridLayout, QDialog, QApplication, QToolButton, QSpacerItem,
)

# ──────────────────────────────────────────────────────────────────────────────
#  Persistence helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_notes_file() -> Path:
    app_data = os.environ.get("APPDATA")
    base = Path(app_data) if app_data else Path.home()
    data_dir = base / "widjett"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "notes.json"


NOTES_FILE = _get_notes_file()


def _load_notes() -> list:
    if NOTES_FILE.exists():
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def _save_notes_sync(notes: list) -> None:
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[SmartNotes] Save error: {e}")


# ──────────────────────────────────────────────────────────────────────────────
#  Design tokens
# ──────────────────────────────────────────────────────────────────────────────

# Note colour palette — (background hex, text-on-that-bg hex)
NOTE_PALETTE = [
    ("#1e1e2e", "#eeeef8"),  # Midnight (default dark)
    ("#1a1a2a", "#c9c9f0"),  # Deep navy
    ("#1e2a1e", "#b6f0b6"),  # Forest
    ("#2a1e1e", "#f0b6b6"),  # Rose dark
    ("#2a2610", "#f0e6a0"),  # Amber dark
    ("#1e2a2a", "#a0e6f0"),  # Teal dark
    ("#2a1a2a", "#e0a0f0"),  # Plum
    ("#1e1a2a", "#b0c0ff"),  # Indigo
    ("#2a1e10", "#f0c080"),  # Warm amber
    ("#101e2a", "#80c8f0"),  # Ocean
    ("#1e2416", "#9de88a"),  # Sage
    ("#241016", "#f08aaa"),  # Berry
]

# Swatches shown in the colour picker row
SWATCH_COLORS = [p[0] for p in NOTE_PALETTE]

# Accent for the widget chrome
_ACCENT      = "#9d8df5"
_ACCENT2     = "#5dd6b5"
_BG          = "rgba(14, 14, 22, 240)"
_BORDER      = "rgba(90, 90, 150, 100)"
_TEXT        = "#eeeef8"
_TEXT_DIM    = "#7a7a9a"
_BTN_HOVER   = "rgba(157, 141, 245, 170)"
_BTN_DANGER  = "rgba(235, 75, 75, 215)"


def _hex_to_qcolor(h: str) -> QColor:
    return QColor(h)


# ──────────────────────────────────────────────────────────────────────────────
#  NoteCard  —  the individual card shown in the grid
# ──────────────────────────────────────────────────────────────────────────────

class NoteCard(QFrame):
    """
    A rounded, coloured card that displays one note.
    Emits `double_clicked` when the user double-clicks it.
    """
    double_clicked = pyqtSignal(str)   # emits note['id']

    _CARD_RADIUS = 14

    def __init__(self, note: dict, parent=None):
        super().__init__(parent)
        self._note = note
        self._hovered = False
        self.setFixedSize(160, 140)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self._build()

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        bg_hex  = self._note.get("color", NOTE_PALETTE[0][0])
        bg_col  = _hex_to_qcolor(bg_hex)
        border_col = QColor(255, 255, 255, 30 if not self._hovered else 70)

        path = QPainterPath()
        path.addRoundedRect(2, 2, self.width() - 4, self.height() - 4,
                            self._CARD_RADIUS, self._CARD_RADIUS)

        # subtle gradient fill
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, bg_col.lighter(115))
        grad.setColorAt(1, bg_col)
        painter.fillPath(path, QBrush(grad))

        # border
        pen = QPen(border_col, 1.5)
        painter.setPen(pen)
        painter.drawPath(path)

        # hover glow
        if self._hovered:
            glow = QColor(_ACCENT)
            glow.setAlpha(60)
            pen2 = QPen(glow, 2)
            painter.setPen(pen2)
            painter.drawPath(path)

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        note = self._note
        fg_hex = self._color_text()

        # pin indicator
        if note.get("pinned"):
            pin_lbl = QLabel("📌")
            pin_lbl.setStyleSheet("font-size: 10px; background: transparent;")
            pin_lbl.setFixedHeight(14)
            lay.addWidget(pin_lbl)

        # title
        title = note.get("title", "").strip()
        if title:
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet(
                f"color: {fg_hex}; font-size: 12px; font-weight: 700;"
                " background: transparent;"
            )
            t_lbl.setWordWrap(True)
            t_lbl.setMaximumHeight(42)
            lay.addWidget(t_lbl)

        # body
        body = note.get("body", "").strip()
        if body:
            b_lbl = QLabel(body)
            b_lbl.setStyleSheet(
                f"color: {fg_hex}; font-size: 11px; opacity: 0.85;"
                " background: transparent;"
            )
            b_lbl.setWordWrap(True)
            b_lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            lay.addWidget(b_lbl, 1)

        if not title and not body:
            empty = QLabel("(empty note)")
            empty.setStyleSheet(
                f"color: {fg_hex}; font-size: 11px; font-style: italic;"
                " background: transparent; opacity: 0.5;"
            )
            lay.addWidget(empty, 1)

        lay.addStretch()

    def _color_text(self) -> str:
        bg = self._note.get("color", NOTE_PALETTE[0][0])
        for bg_hex, fg_hex in NOTE_PALETTE:
            if bg_hex == bg:
                return fg_hex
        return _TEXT

    # ── hover ─────────────────────────────────────────────────────────────────

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    # ── double-click ──────────────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self._note["id"])


# ──────────────────────────────────────────────────────────────────────────────
#  NoteEditDialog  —  full-screen edit / create dialog
# ──────────────────────────────────────────────────────────────────────────────

class NoteEditDialog(QDialog):
    """
    Frameless dialog for creating/editing a note.
    Returns via .exec_() == QDialog.Accepted.
    Call .get_note() to retrieve the updated note dict.
    """

    def __init__(self, note: dict | None = None, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumWidth(420)
        self.setMinimumHeight(380)

        # work on a copy
        if note is None:
            self._note = {
                "id":      str(uuid.uuid4()),
                "title":   "",
                "body":    "",
                "color":   NOTE_PALETTE[0][0],
                "pinned":  False,
                "created": datetime.now().isoformat(),
                "updated": datetime.now().isoformat(),
            }
            self._is_new = True
        else:
            self._note   = dict(note)
            self._is_new = False

        self._drag_pos  = QPoint()
        self._dragging  = False
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        self._card = QFrame()
        self._card.setObjectName("NoteDialogCard")
        self._card.setStyleSheet(
            "#NoteDialogCard {"
            f"  background: rgba(18, 18, 30, 252);"
            f"  border: 1px solid {_BORDER};"
            "  border-radius: 18px;"
            "}"
        )
        self._card.installEventFilter(self)

        vlay = QVBoxLayout(self._card)
        vlay.setContentsMargins(20, 16, 20, 18)
        vlay.setSpacing(12)

        # ── header row ───────────────────────────────────────────────────────
        hrow = QHBoxLayout()

        hdr_lbl = QLabel("✏️  Edit Note" if not self._is_new else "✨  New Note")
        hdr_lbl.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_TEXT}; background: transparent;"
        )
        hrow.addWidget(hdr_lbl)
        hrow.addStretch()

        # pin toggle button
        self._pin_btn = QPushButton("📌 Pin")
        self._pin_btn.setCheckable(True)
        self._pin_btn.setChecked(self._note.get("pinned", False))
        self._pin_btn.setFixedHeight(28)
        self._pin_btn.setStyleSheet(self._pin_btn_style(self._note.get("pinned", False)))
        self._pin_btn.toggled.connect(self._on_pin_toggled)
        hrow.addWidget(self._pin_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("NoteCloseBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none;"
            f"  color: {_TEXT_DIM}; border-radius: 7px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {_BTN_DANGER}; color: white; }}"
        )
        close_btn.clicked.connect(self.reject)
        hrow.addWidget(close_btn)

        vlay.addLayout(hrow)

        # ── title input ──────────────────────────────────────────────────────
        self._title_edit = QLineEdit(self._note.get("title", ""))
        self._title_edit.setPlaceholderText("Title")
        self._title_edit.setStyleSheet(
            f"QLineEdit {{"
            f"  background: rgba(255,255,255,8);"
            f"  border: 1px solid rgba(255,255,255,18);"
            f"  border-radius: 10px; padding: 8px 12px;"
            f"  color: {_TEXT}; font-size: 14px; font-weight: 600;"
            f"}}"
            f"QLineEdit:focus {{"
            f"  border-color: {_ACCENT}; background: rgba(157,141,245,12);"
            f"}}"
        )
        vlay.addWidget(self._title_edit)

        # ── body input ───────────────────────────────────────────────────────
        self._body_edit = QTextEdit()
        self._body_edit.setPlainText(self._note.get("body", ""))
        self._body_edit.setPlaceholderText("Take a note…")
        self._body_edit.setMinimumHeight(140)
        self._body_edit.setStyleSheet(
            f"QTextEdit {{"
            f"  background: rgba(255,255,255,6);"
            f"  border: 1px solid rgba(255,255,255,15);"
            f"  border-radius: 10px; padding: 10px;"
            f"  color: {_TEXT}; font-size: 13px;"
            f"}}"
            f"QTextEdit:focus {{"
            f"  border-color: {_ACCENT}; background: rgba(157,141,245,10);"
            f"}}"
        )
        vlay.addWidget(self._body_edit, 1)

        # ── colour palette ───────────────────────────────────────────────────
        vlay.addWidget(self._build_palette())

        # ── action buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        if not self._is_new:
            del_btn = QPushButton("🗑  Delete")
            del_btn.setStyleSheet(
                f"QPushButton {{ background: rgba(200,50,50,180); border: 1px solid rgba(255,80,80,120);"
                f"  border-radius: 9px; padding: 6px 14px; color: white; font-weight: 600; }}"
                f"QPushButton:hover {{ background: rgba(235,70,70,220); }}"
            )
            del_btn.clicked.connect(self._on_delete)
            btn_row.addWidget(del_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("💾  Save")
        save_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(157,141,245,200);"
            f"  border: 1px solid {_ACCENT}; border-radius: 9px;"
            f"  padding: 6px 18px; color: white; font-weight: 700; }}"
            f"QPushButton:hover {{ background: rgba(157,141,245,255); }}"
        )
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        vlay.addLayout(btn_row)

        outer.addWidget(self._card)

    def _build_palette(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        lbl = QLabel("Color:")
        lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;")
        h.addWidget(lbl)

        self._swatch_btns = []
        for hex_col in SWATCH_COLORS:
            btn = QPushButton()
            btn.setFixedSize(20, 20)
            btn.setToolTip(hex_col)
            active = (hex_col == self._note.get("color", NOTE_PALETTE[0][0]))
            btn.setStyleSheet(self._swatch_style(hex_col, active))
            btn.clicked.connect(lambda checked, c=hex_col: self._pick_color(c))
            self._swatch_btns.append((hex_col, btn))
            h.addWidget(btn)

        h.addStretch()
        return container

    def _swatch_style(self, hex_col: str, active: bool) -> str:
        border = f"2px solid white" if active else f"1px solid rgba(255,255,255,30)"
        return (
            f"QPushButton {{ background: {hex_col}; border: {border};"
            f"  border-radius: 10px; }}"
            f"QPushButton:hover {{ border: 2px solid {_ACCENT}; }}"
        )

    def _pin_btn_style(self, pinned: bool) -> str:
        if pinned:
            return (
                f"QPushButton {{ background: rgba(93,214,181,140);"
                f"  border: 1px solid {_ACCENT2}; border-radius: 8px;"
                f"  padding: 0 10px; color: white; font-size: 11px; font-weight: 600; }}"
                f"QPushButton:hover {{ background: rgba(93,214,181,200); }}"
            )
        else:
            return (
                f"QPushButton {{ background: rgba(255,255,255,8);"
                f"  border: 1px solid rgba(255,255,255,20); border-radius: 8px;"
                f"  padding: 0 10px; color: {_TEXT_DIM}; font-size: 11px; }}"
                f"QPushButton:hover {{ background: {_BTN_HOVER}; color: white; }}"
            )

    # ── event handlers ────────────────────────────────────────────────────────

    def _pick_color(self, hex_col: str):
        self._note["color"] = hex_col
        for c, btn in self._swatch_btns:
            btn.setStyleSheet(self._swatch_style(c, c == hex_col))

    def _on_pin_toggled(self, checked: bool):
        self._note["pinned"] = checked
        self._pin_btn.setStyleSheet(self._pin_btn_style(checked))
        self._pin_btn.setText("📌 Pinned" if checked else "📌 Pin")

    def _on_save(self):
        self._note["title"]   = self._title_edit.text().strip()
        self._note["body"]    = self._body_edit.toPlainText().strip()
        self._note["updated"] = datetime.now().isoformat()
        self.accept()

    def _on_delete(self):
        self._note["_deleted"] = True
        self.accept()

    def get_note(self) -> dict:
        return self._note

    # ── dragging the dialog ───────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self._card:
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


# ──────────────────────────────────────────────────────────────────────────────
#  SmartNotesWidget  —  the embeddable main widget
# ──────────────────────────────────────────────────────────────────────────────

class SmartNotesWidget(QWidget):
    """
    Google Keep-style sticky-notes panel.

    Usage
    -----
        parent_frame = QFrame(...)
        notes_widget = SmartNotesWidget(parent_frame)

    All notes are auto-saved to <APPDATA>/widjett/notes.json.
    No external dependencies — uses only PyQt5 + stdlib.
    """

    # ── constants ─────────────────────────────────────────────────────────────

    _AUTOSAVE_DELAY_MS  = 600   # debounce: save 600 ms after last change
    _CARD_WIDTH         = 160
    _CARD_HEIGHT        = 140
    _GRID_SPACING       = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notes: list[dict] = _load_notes()
        self._save_timer        = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save)
        self._save_lock         = threading.Lock()
        self._pending_save      = False

        self._build_ui()
        self._refresh_grid()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(
            "SmartNotesWidget {"
            f"  background: transparent;"
            "}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── top bar ──────────────────────────────────────────────────────────
        self._topbar = QWidget()
        self._topbar.setFixedHeight(52)
        self._default_topbar_qss = (
            "background: transparent;"
            f"border-bottom: 1px solid {_BORDER};"
        )
        self._topbar.setStyleSheet(self._default_topbar_qss)
        tb_lay = QHBoxLayout(self._topbar)
        tb_lay.setContentsMargins(14, 8, 14, 8)
        tb_lay.setSpacing(10)

        # Search bar
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("🔍  Search notes…")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.setFixedHeight(30)
        self._default_search_qss = (
            f"QLineEdit {{"
            f"  background: rgba(255,255,255,8);"
            f"  border: 1px solid rgba(255,255,255,20);"
            f"  border-radius: 15px; padding: 2px 12px;"
            f"  color: {_TEXT}; font-size: 12px;"
            f"}}"
            f"QLineEdit:focus {{"
            f"  border-color: {_ACCENT}; background: rgba(157,141,245,12);"
            f"}}"
        )
        self._search_box.setStyleSheet(self._default_search_qss)
        self._search_box.textChanged.connect(self._on_search_changed)
        tb_lay.addWidget(self._search_box, 1)

        # Add button
        self._add_btn = QPushButton("＋")
        self._add_btn.setFixedSize(32, 32)
        self._add_btn.setToolTip("New note  (Ctrl+N)")
        self._default_add_btn_qss = (
            f"QPushButton {{"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"    stop:0 {_ACCENT}, stop:1 #7c6af7);"
            f"  border: none; border-radius: 16px;"
            f"  color: white; font-size: 20px; font-weight: 700;"
            f"  padding: 0; line-height: 1;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"    stop:0 #b39dff, stop:1 {_ACCENT});"
            f"}}"
            f"QPushButton:pressed {{ background: #7c6af7; }}"
        )
        self._add_btn.setStyleSheet(self._default_add_btn_qss)
        self._add_btn.clicked.connect(self._new_note)
        tb_lay.addWidget(self._add_btn)

        root.addWidget(self._topbar)

        # ── scroll area for the note grid ────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical {"
            "  background: transparent; width: 5px; margin: 0;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(255,255,255,45);"
            "  border-radius: 3px; min-height: 20px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: transparent;")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setContentsMargins(14, 14, 14, 14)
        self._grid_layout.setSpacing(self._GRID_SPACING)

        self._scroll.setWidget(self._grid_container)
        root.addWidget(self._scroll, 1)

        # ── empty-state label ─────────────────────────────────────────────────
        self._empty_lbl = QLabel(
            "📝  No notes yet.\n\nPress  ＋  to create your first note."
        )
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {_TEXT_DIM}; font-size: 13px; line-height: 1.8;"
            " background: transparent;"
        )
        self._empty_lbl.hide()
        root.addWidget(self._empty_lbl)

        # ── status bar ────────────────────────────────────────────────────────
        self._status_lbl = QLabel("")
        self._status_lbl.setFixedHeight(20)
        self._status_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._status_lbl.setStyleSheet(
            f"color: {_TEXT_DIM}; font-size: 10px; padding-right: 10px;"
            " background: transparent;"
        )
        root.addWidget(self._status_lbl)

        # keyboard shortcut
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence
        sc = QShortcut(QKeySequence("Ctrl+N"), self)
        sc.activated.connect(self._new_note)

    # ── grid management ───────────────────────────────────────────────────────

    def _visible_notes(self) -> list[dict]:
        q = self._search_box.text().strip().lower()
        notes = list(self._notes)
        # pinned first
        pinned   = [n for n in notes if n.get("pinned")]
        unpinned = [n for n in notes if not n.get("pinned")]
        ordered  = pinned + unpinned

        if not q:
            return ordered
        return [
            n for n in ordered
            if q in n.get("title", "").lower()
            or q in n.get("body", "").lower()
        ]

    def _refresh_grid(self):
        # clear existing cards
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        visible = self._visible_notes()

        if not visible:
            self._scroll.hide()
            self._empty_lbl.show()
            self._status_lbl.setText("")
            return

        self._empty_lbl.hide()
        self._scroll.show()

        # calculate columns based on available width
        cols = max(1, (self.width() - 28) // (self._CARD_WIDTH + self._GRID_SPACING))

        # add section label for pinned notes
        has_pinned   = any(n.get("pinned") for n in visible)
        has_unpinned = any(not n.get("pinned") for n in visible)

        row = 0
        col = 0

        def _section_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color: {_TEXT_DIM}; font-size: 10px; font-weight: 700;"
                f" letter-spacing: 1.5px; background: transparent; padding-left: 2px;"
            )
            return lbl

        pinned_drawn   = False
        unpinned_drawn = False

        for note in visible:
            is_pinned = note.get("pinned", False)

            # section headers
            if is_pinned and not pinned_drawn and has_pinned:
                lbl = _section_label("📌  PINNED")
                self._grid_layout.addWidget(lbl, row, 0, 1, cols)
                row += 1
                col  = 0
                pinned_drawn = True

            if not is_pinned and not unpinned_drawn and has_unpinned:
                if col != 0:
                    row += 1
                    col  = 0
                if has_pinned:
                    lbl = _section_label("OTHER NOTES")
                    self._grid_layout.addWidget(lbl, row, 0, 1, cols)
                    row += 1
                unpinned_drawn = True

            card = NoteCard(note)
            card.double_clicked.connect(self._open_edit_dialog)
            self._grid_layout.addWidget(card, row, col, Qt.AlignTop | Qt.AlignLeft)
            col += 1
            if col >= cols:
                col = 0
                row += 1

        # Add stretch to the row below the notes
        self._grid_layout.setRowStretch(row + 1, 1)
        
        # Reset column stretches first
        for i in range(self._grid_layout.columnCount()):
            self._grid_layout.setColumnStretch(i, 0)
        # Add a stretch column at the end so cards pack to the left instead of spreading out
        self._grid_layout.setColumnStretch(cols, 1)

        total = len(self._notes)
        shown = len(visible)
        q     = self._search_box.text().strip()
        if q:
            self._status_lbl.setText(f"{shown} of {total} notes")
        else:
            s = "note" if total == 1 else "notes"
            self._status_lbl.setText(f"{total} {s}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_grid()

    # ── search ────────────────────────────────────────────────────────────────

    def _on_search_changed(self, text: str):
        self._refresh_grid()

    # ── note CRUD ─────────────────────────────────────────────────────────────

    def _new_note(self):
        dlg = NoteEditDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            note = dlg.get_note()
            if not note.get("_deleted"):
                self._notes.append(note)
                self._schedule_save()
                self._refresh_grid()

    def _open_edit_dialog(self, note_id: str):
        note = next((n for n in self._notes if n["id"] == note_id), None)
        if note is None:
            return

        dlg = NoteEditDialog(note=note, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            updated = dlg.get_note()
            if updated.get("_deleted"):
                self._notes = [n for n in self._notes if n["id"] != note_id]
            else:
                for i, n in enumerate(self._notes):
                    if n["id"] == note_id:
                        self._notes[i] = updated
                        break
            self._schedule_save()
            self._refresh_grid()

    # ── auto-save (debounced + threaded) ──────────────────────────────────────

    def _schedule_save(self):
        """Restart the debounce timer — called after every mutation."""
        self._save_timer.start(self._AUTOSAVE_DELAY_MS)

    def _do_save(self):
        """Called by the QTimer on the main thread; delegates I/O to a worker."""
        snapshot = list(self._notes)   # cheap copy of list refs
        threading.Thread(
            target=_save_notes_sync,
            args=(snapshot,),
            daemon=True,
        ).start()
        self._show_save_flash()

    def _show_save_flash(self):
        """Briefly show a 'Saved' indicator in the status bar."""
        self._status_lbl.setStyleSheet(
            f"color: {_ACCENT2}; font-size: 10px; padding-right: 10px;"
            " background: transparent;"
        )
        self._status_lbl.setText("✓ Saved")
        QTimer.singleShot(1800, self._reset_status_style)

    def _reset_status_style(self):
        self._status_lbl.setStyleSheet(
            f"color: {_TEXT_DIM}; font-size: 10px; padding-right: 10px;"
            " background: transparent;"
        )
        # re-render count
        total = len(self._notes)
        s = "note" if total == 1 else "notes"
        q = self._search_box.text().strip()
        if q:
            shown = len(self._visible_notes())
            self._status_lbl.setText(f"{shown} of {total} notes")
        else:
            self._status_lbl.setText(f"{total} {s}")

    def apply_theme(self, header_rgba, body_rgba) -> None:
        if header_rgba and body_rgba:
            hr = header_rgba
            # Keep topbar transparent so it inherits the card body color
            self._topbar.setStyleSheet(
                "background: transparent;"
                f"border-bottom: 1px solid rgba({hr[0]}, {hr[1]}, {hr[2]}, 80);"
            )
            self._search_box.setStyleSheet(
                f"QLineEdit {{"
                f"  background: rgba(255,255,255,8);"
                f"  border: 1px solid rgba({hr[0]}, {hr[1]}, {hr[2]}, 160);"
                f"  border-radius: 15px; padding: 2px 12px;"
                f"  color: {_TEXT}; font-size: 12px;"
                f"}}"
                f"QLineEdit:focus {{"
                f"  border-color: rgba({hr[0]}, {hr[1]}, {hr[2]}, 255);"
                f"  background: rgba(255,255,255,12);"
                f"}}"
            )
            self._add_btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: rgba({hr[0]}, {hr[1]}, {hr[2]}, 220);"
                f"  border: none; border-radius: 16px;"
                f"  color: white; font-size: 20px; font-weight: 700;"
                f"  padding: 0; line-height: 1;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background: rgba({hr[0]}, {hr[1]}, {hr[2]}, 180);"
                f"}}"
                f"QPushButton:pressed {{ background: rgba({hr[0]}, {hr[1]}, {hr[2]}, 130); }}"
            )
        else:
            self._topbar.setStyleSheet(getattr(self, '_default_topbar_qss', ''))
            self._search_box.setStyleSheet(getattr(self, '_default_search_qss', ''))
            self._add_btn.setStyleSheet(getattr(self, '_default_add_btn_qss', ''))
