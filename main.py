import sys
from functools import partial
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.app_controller import AppController
from ui.result_overlay import DEFAULT_FONT_SIZE
from utils.logger import setup_logger


APP_ICON_PATH = Path(__file__).resolve().parent / "imgs" / "app_icon.png"


FONT_SIZE_OPTIONS = {
    "Small": 13,
    "Medium": DEFAULT_FONT_SIZE,
    "Large": 15,
}


def _create_fallback_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#1f6feb"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
    painter.setPen(QPen(QColor("white")))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(24)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "O")
    painter.end()
    return QIcon(pixmap)


def _load_tray_icon() -> QIcon:
    if APP_ICON_PATH.exists():
        file_pixmap = QPixmap(str(APP_ICON_PATH))
        if not file_pixmap.isNull():
            return QIcon(file_pixmap)

    theme_icon = QIcon.fromTheme("text-x-generic")
    if not theme_icon.isNull():
        return theme_icon

    return _create_fallback_icon()


def create_tray_icon(app: QApplication, controller: AppController) -> QSystemTrayIcon:
    tray_icon = QSystemTrayIcon()
    tray_icon.setToolTip("orc-trans-app")
    tray_icon.setIcon(_load_tray_icon())

    menu = QMenu()
    font_menu = menu.addMenu("Font size")
    font_action_group = QActionGroup(font_menu)
    font_action_group.setExclusive(True)

    for label, size in FONT_SIZE_OPTIONS.items():
        action = font_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(size == DEFAULT_FONT_SIZE)
        font_action_group.addAction(action)
        action.triggered.connect(partial(controller.set_result_font_size, size))

    menu.addSeparator()
    menu.addAction("Exit", app.quit)
    tray_icon.setContextMenu(menu)
    return tray_icon


def main() -> int:
    logger = setup_logger()
    logger.info("Application startup")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = AppController(logger=logger)
    tray_icon = create_tray_icon(app, controller)
    app.aboutToQuit.connect(controller.stop)
    app.aboutToQuit.connect(tray_icon.hide)

    try:
        tray_icon.show()
        controller.start()
        exit_code = app.exec()
    finally:
        tray_icon.hide()
        controller.stop()

    logger.info("Application shutdown")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
