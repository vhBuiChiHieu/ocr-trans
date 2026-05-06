from __future__ import annotations

from datetime import datetime
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QResizeEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.ocr_history import OCRHistoryEntry


DEFAULT_PANEL_WIDTH = 340
MIN_PANEL_WIDTH = 280
MAX_PANEL_WIDTH = 640
COLLAPSED_WIDTH = 44
COLLAPSED_HEIGHT = 44
COLLAPSED_TOP_MARGIN = 20
COLLAPSED_VERTICAL_ANCHOR_RATIO = 0.5


class HistoryPanel(QWidget):
    def __init__(self, width: int = DEFAULT_PANEL_WIDTH, font_size: int = 14, font_family: str = "Segoe UI") -> None:
        super().__init__()
        self._font_size = font_size
        self._font_family = font_family
        self._expanded_width = max(MIN_PANEL_WIDTH, min(MAX_PANEL_WIDTH, width))
        self._collapsed = True
        self._history_count = 0
        self._width_changed_callback: Callable[[int], None] | None = None
        self._toggle_callback: Callable[[bool], None] | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setObjectName("historyPanel")
        self.setStyleSheet(
            "QWidget#historyPanel {"
            "background-color: rgba(11, 20, 26, 224);"
            "border: 1px solid rgba(56, 189, 248, 95);"
            "border-radius: 14px;"
            "}"
            "QLabel#historyTitle {"
            "color: #d7dde4;"
            "font-weight: 600;"
            "border: none;"
            "background: transparent;"
            "}"
            "QPushButton#historyToggle {"
            "color: #d7dde4;"
            "background-color: rgba(21, 36, 46, 220);"
            "border: 1px solid rgba(88, 166, 255, 95);"
            "border-radius: 10px;"
            "padding: 4px 6px;"
            "}"
            "QPushButton#historyToggle:hover {"
            "background-color: rgba(34, 53, 66, 228);"
            "}"
            "QFrame#historyItem {"
            "background-color: rgba(15, 27, 35, 205);"
            "border: 1px solid rgba(88, 166, 255, 70);"
            "border-radius: 10px;"
            "}"
            "QLabel#historyMeta {"
            "color: #8fa3b8;"
            "border: none;"
            "background: transparent;"
            "}"
            "QLabel#historyText {"
            "color: #d7dde4;"
            "border: none;"
            "background: transparent;"
            "}"
            "QScrollArea {"
            "border: none;"
            "background: transparent;"
            "}"
            "QScrollBar:vertical {"
            "background: rgba(0, 0, 0, 0);"
            "width: 8px;"
            "margin: 0px;"
            "}"
            "QScrollBar::handle:vertical {"
            "background: rgba(114, 136, 157, 140);"
            "border-radius: 4px;"
            "min-height: 28px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "height: 0px;"
            "}"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(12, 12, 8, 12)
        self._root_layout.setSpacing(10)

        header_row = QWidget(self)
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self._title = QLabel("History (0)", header_row)
        self._title.setObjectName("historyTitle")

        self._toggle_button = QPushButton(header_row)
        self._toggle_button.setObjectName("historyToggle")
        self._toggle_button.clicked.connect(self._handle_toggle_clicked)

        header_layout.addWidget(self._title)
        header_layout.addStretch(1)
        header_layout.addWidget(self._toggle_button)

        self._root_layout.addWidget(header_row)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._list_container = QWidget(self)
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll_area.setWidget(self._list_container)
        self._root_layout.addWidget(self._scroll_area)

        self._apply_font()
        self._update_header_text()
        self._apply_mode()
        self.hide()

    def set_width_changed_callback(self, callback: Callable[[int], None]) -> None:
        self._width_changed_callback = callback

    def set_toggle_callback(self, callback: Callable[[bool], None]) -> None:
        self._toggle_callback = callback

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self._apply_mode()
        self._anchor_to_right_edge()

    def set_panel_width(self, width: int) -> None:
        normalized_width = max(MIN_PANEL_WIDTH, min(MAX_PANEL_WIDTH, width))
        self._expanded_width = normalized_width
        if self._collapsed:
            return
        if self.width() == normalized_width:
            return
        self.resize(normalized_width, self.height())
        self._anchor_to_right_edge()

    def set_font_size(self, font_size: int) -> None:
        self._font_size = font_size
        self._apply_font()

    def set_font_family(self, font_family: str) -> None:
        self._font_family = font_family
        self._apply_font()

    def set_entries(self, entries: list[OCRHistoryEntry]) -> None:
        self._history_count = len(entries)
        self._update_header_text()

        while self._list_layout.count():
            child = self._list_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

        if not entries:
            empty = QLabel("Chưa có kết quả OCR.", self._list_container)
            empty.setObjectName("historyMeta")
            empty.setWordWrap(True)
            self._list_layout.addWidget(empty)
            self._apply_font()
            return

        for entry in entries:
            item = QFrame(self._list_container)
            item.setObjectName("historyItem")
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(10, 8, 10, 8)
            item_layout.setSpacing(4)

            meta = QLabel(f"{self._format_created_at(entry.created_at)} · {entry.mode}", item)
            meta.setObjectName("historyMeta")

            preview_text = entry.display_text.strip() or entry.ocr_text.strip()
            if len(preview_text) > 280:
                preview_text = preview_text[:280].rstrip() + "…"
            text_label = QLabel(preview_text, item)
            text_label.setObjectName("historyText")
            text_label.setWordWrap(True)
            text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            item_layout.addWidget(meta)
            item_layout.addWidget(text_label)
            self._list_layout.addWidget(item)

        self._apply_font()

    def show_docked_right(self) -> None:
        self._anchor_to_right_edge()
        self.show()
        self.raise_()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not event.oldSize().isValid():
            return
        self._anchor_to_right_edge()
        if (
            not self._collapsed
            and self._width_changed_callback is not None
            and event.size().width() != event.oldSize().width()
        ):
            self._width_changed_callback(event.size().width())

    def _handle_toggle_clicked(self) -> None:
        self.set_collapsed(not self._collapsed)
        if self._toggle_callback is not None:
            self._toggle_callback(self._collapsed)

    def _apply_mode(self) -> None:
        if self._collapsed:
            self._title.hide()
            self._scroll_area.hide()
            self._root_layout.setContentsMargins(5, 5, 5, 5)
            self._toggle_button.setText("H")
            self._toggle_button.setToolTip(f"History ({self._history_count})")
            self._toggle_button.setMinimumHeight(COLLAPSED_HEIGHT - 10)
            self._toggle_button.setMaximumHeight(COLLAPSED_HEIGHT - 10)
            self._toggle_button.setMinimumWidth(COLLAPSED_WIDTH - 10)
            self._toggle_button.setMaximumWidth(COLLAPSED_WIDTH - 10)
            self.setMinimumWidth(COLLAPSED_WIDTH)
            self.setMaximumWidth(COLLAPSED_WIDTH)
            self.setMinimumHeight(COLLAPSED_HEIGHT)
            self.setMaximumHeight(COLLAPSED_HEIGHT)
        else:
            self._title.show()
            self._scroll_area.show()
            self._root_layout.setContentsMargins(12, 12, 8, 12)
            self._toggle_button.setText("Thu gọn")
            self._toggle_button.setToolTip("")
            self._toggle_button.setMinimumHeight(30)
            self._toggle_button.setMaximumHeight(36)
            self._toggle_button.setMinimumWidth(76)
            self._toggle_button.setMaximumWidth(92)
            self.setMinimumWidth(MIN_PANEL_WIDTH)
            self.setMaximumWidth(MAX_PANEL_WIDTH)
            self.setMinimumHeight(120)
            self.setMaximumHeight(16777215)
            self.resize(self._expanded_width, self.height())
            self._update_header_text()

    def _anchor_to_right_edge(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        width = self.width()
        x = available.right() - width + 1
        if self._collapsed:
            collapsed_y = available.top() + int((available.height() - COLLAPSED_HEIGHT) * COLLAPSED_VERTICAL_ANCHOR_RATIO)
            collapsed_y = max(available.top() + COLLAPSED_TOP_MARGIN, collapsed_y)
            self.setGeometry(x, collapsed_y, width, COLLAPSED_HEIGHT)
            return

        # Giữ panel dính cạnh phải màn hình chính ngay cả sau resize ở trạng thái mở rộng.
        self.setGeometry(x, available.top(), width, available.height())

    def _update_header_text(self) -> None:
        self._title.setText(f"History ({self._history_count})")
        if self._collapsed:
            self._toggle_button.setToolTip(f"History ({self._history_count})")

    def _apply_font(self) -> None:
        title_font = QFont(self._font_family, self._font_size + 1)
        title_font.setBold(True)
        self._title.setFont(title_font)

        toggle_font = QFont(self._font_family, max(9, self._font_size - 1))
        self._toggle_button.setFont(toggle_font)

        meta_font = QFont(self._font_family, max(9, self._font_size - 2))
        text_font = QFont(self._font_family, self._font_size)

        for name, font in (("historyMeta", meta_font), ("historyText", text_font)):
            for label in self.findChildren(QLabel, name):
                label.setFont(font)

    @staticmethod
    def _format_created_at(created_at: str) -> str:
        if not created_at:
            return ""
        try:
            dt = datetime.fromisoformat(created_at)
        except ValueError:
            return created_at
        return dt.strftime("%Y-%m-%d %H:%M:%S")
