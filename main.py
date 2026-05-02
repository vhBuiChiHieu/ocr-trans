import sys

from PyQt6.QtWidgets import QApplication

from core.app_controller import AppController
from utils.logger import setup_logger


def main() -> int:
    logger = setup_logger()
    logger.info("Application startup")

    app = QApplication(sys.argv)
    controller = AppController(logger=logger)
    app.aboutToQuit.connect(controller.stop)

    try:
        controller.start()
        exit_code = app.exec()
    finally:
        controller.stop()

    logger.info("Application shutdown")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
