import logging
from pathlib import Path


def setup_logger() -> logging.Logger:
    """Configure application logger for console output."""
    logger = logging.getLogger("ocr_overlay")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

    return logger
