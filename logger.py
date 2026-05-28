import logging
import os
from datetime import datetime


def setup_logger(name="youtube-shorts", level=logging.INFO):
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s - %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    fh = logging.FileHandler(f"logs/youtube-shorts-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger
