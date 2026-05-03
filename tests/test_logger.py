from __future__ import annotations

import logging
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from utils import logger as logger_module


class SetupLoggerTests(unittest.TestCase):
    def tearDown(self) -> None:
        logger = logging.getLogger("ocr_overlay")
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
        logger.setLevel(logging.NOTSET)
        logger.propagate = True

    def test_setup_logger_keeps_stream_handler_and_adds_daily_file_handler(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.object(logger_module, "LOG_DIR", Path(temp_dir) / "logs"):
                logger = logger_module.setup_logger()

                self.assertEqual(logger.level, logging.INFO)
                self.assertFalse(logger.propagate)
                self.assertEqual(len(logger.handlers), 2)
                self.assertTrue(any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers))

                file_handlers = [handler for handler in logger.handlers if isinstance(handler, logging.FileHandler)]
                self.assertEqual(len(file_handlers), 1)
                self.assertEqual(file_handlers[0].encoding, "utf-8")
                self.assertTrue(file_handlers[0].baseFilename.endswith(".log"))

                for handler in list(logger.handlers):
                    handler.close()
                    logger.removeHandler(handler)

    def test_setup_logger_creates_logs_directory_and_daily_log_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            with patch.object(logger_module, "LOG_DIR", log_dir):
                logger = logger_module.setup_logger()
                logger.info("hello log file")

                files = list(log_dir.glob("*.log"))
                self.assertEqual(len(files), 1)
                self.assertIn("hello log file", files[0].read_text(encoding="utf-8"))

                for handler in list(logger.handlers):
                    handler.close()
                    logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()

    def test_setup_logger_creates_logs_directory_and_daily_log_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            with patch.object(logger_module, "LOG_DIR", log_dir):
                logger = logger_module.setup_logger()
                logger.info("hello log file")

                files = list(log_dir.glob("*.log"))
                self.assertEqual(len(files), 1)
                self.assertIn("hello log file", files[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
