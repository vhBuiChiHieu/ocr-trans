import sys
from functools import partial
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup, QColor, QFontDatabase, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.app_controller import AppController, OUTPUT_MODE_BOTH, OUTPUT_MODE_OCR_ONLY, OUTPUT_MODE_TRANSLATE
from ui.result_overlay import DEFAULT_FONT_SIZE
from utils.logger import setup_logger


APP_ICON_PATH = Path(__file__).resolve().parent / "imgs" / "app_icon.png"
FONT_DIR_PATH = Path(__file__).resolve().parent / "fonts"
DEFAULT_FONT_FAMILY = "Segoe UI"
DEFAULT_FONT_LABEL = "Default"


FONT_SIZE_OPTIONS = {
    "Small": 13,
    "Medium": DEFAULT_FONT_SIZE,
    "Large": 15,
}
OUTPUT_MODE_OPTIONS = {
    "OCR only": OUTPUT_MODE_OCR_ONLY,
    "Translate": OUTPUT_MODE_TRANSLATE,
    "Both": OUTPUT_MODE_BOTH,
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


def load_font_family_options(font_dir: Path = FONT_DIR_PATH) -> dict[str, str]:
    options = {DEFAULT_FONT_LABEL: DEFAULT_FONT_FAMILY}
    if not font_dir.exists():
        return options

    for font_path in sorted([*font_dir.glob("*.ttf"), *font_dir.glob("*.otf")]):
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id < 0:
            continue
        for family in QFontDatabase.applicationFontFamilies(font_id):
            options[family] = family

    return options


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
        action.setChecked(size == controller.settings.font_size)
        font_action_group.addAction(action)
        action.triggered.connect(partial(controller.set_result_font_size, size))

    font_family_menu = menu.addMenu("Font family")
    font_family_action_group = QActionGroup(font_family_menu)
    font_family_action_group.setExclusive(True)

    for label, family in load_font_family_options().items():
        action = font_family_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(family == controller.settings.font_family)
        font_family_action_group.addAction(action)
        action.triggered.connect(partial(controller.set_result_font_family, family))

    output_menu = menu.addMenu("Output mode")
    output_action_group = QActionGroup(output_menu)
    output_action_group.setExclusive(True)

    for label, mode in OUTPUT_MODE_OPTIONS.items():
        action = output_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(mode == controller.settings.output_mode)
        output_action_group.addAction(action)
        action.triggered.connect(partial(controller.set_output_mode, mode))

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
