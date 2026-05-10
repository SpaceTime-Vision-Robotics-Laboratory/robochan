"""generic utils file"""
from pathlib import Path
from loggez import make_logger
from robochan.utils import logger as base_logger

_LOG_FILE = None
if base_logger.get_file_handler() is not None:
    _LOG_FILE = Path(base_logger.get_file_handler().file_path).parent / "ROBOIMPL.txt"

logger = make_logger("ROBOIMPL", log_file=_LOG_FILE)
