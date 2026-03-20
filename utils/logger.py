"""Logger with rotating file handler + console output."""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")


def get_logger(name: str = "cfdi_automation") -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    fh = RotatingFileHandler(
        os.path.join(LOG_DIR, f"run_{datetime.now().strftime('%Y%m%d')}.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
