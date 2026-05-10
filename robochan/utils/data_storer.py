"""data_storer.py A thread with a queue for storing data on disk as npz files"""
from __future__ import annotations
import threading
import atexit
from typing import Any
from pathlib import Path
from datetime import datetime
from queue import Queue, Empty
import time
import os
from overrides import overrides
import numpy as np

from .utils import logger

SLEEP_INTERVAL = 0.01
DATA_STORER_QUEUE_MAXSIZE = int(os.getenv("ROBOCHAN_DATA_STORER_QUEUE_SIZE", "100"))
_INSTANCE: DataStorer | None = None # pylint: disable=invalid-name

class DataStorer(threading.Thread):
    """
    Thread that operates a queue for storing data from other threads i.e. DataChannel or ActionsQueue.
    Note: you can control the queue size with `ROBOCHAN_DATA_STORER_QUEUE_SIZE` env variable. If the queue is full, then
    the data producer and actions consumers will also be throthled, making the robot lag. So be careful if you have too
    much stuff you want to log to the disk, becuase it may propagate. See issue (!11) as well.
    """
    def __init__(self, path: Path):
        super().__init__(daemon=True)
        path.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.data_queue = Queue(maxsize=DATA_STORER_QUEUE_MAXSIZE)
        self.is_closed = False

    @staticmethod
    def get_instance() -> DataStorer | None:
        """Singleton: creates the unique instance of DataStorer"""
        global _INSTANCE # pylint: disable=global-statement
        if _INSTANCE is not None and not _INSTANCE.is_closed:
            return _INSTANCE
        if os.getenv("ROBOCHAN_STORE_LOGS", "0") != "2":
            return None
        if logger.get_file_handler() is not None:
            logs_dir = Path(logger.get_file_handler().file_path).parent
        else: # can happen in tests -_-
            logs_dir = Path(os.environ["ROBOCHAN_LOGS_DIR"])

        logger.info(f"Setting DataStorer at '{logs_dir}'")
        (_INSTANCE := DataStorer(logs_dir)).start()
        atexit.register(_INSTANCE.close)
        return _INSTANCE

    def close(self):
        """method to close the data storer"""
        if self.is_closed:
            return
        self.is_closed = True
        self.join()

    def push(self, item: dict[str, Any], tag: str, timestamp: datetime):
        """Push a data item to the queue so it's later stored on disk. A 'tag' of the source must be provided."""
        assert not self.is_closed, "DataStorer is closed, cannot push."
        assert isinstance(item, dict), f"Can only push dicts to DataStorer. Got {type(item)}"
        logger.trace(f"Pushing item at {self.path}/{tag}/{timestamp} (#queue: {len(self)})")
        self.data_queue.put({"item": item, "tag": tag, "timestamp": timestamp.isoformat()}) # arr_0 for compat!

    def get_and_store(self):
        """gets one item from the data queue and stores it to the disk"""
        x: dict[str, Any] = self.data_queue.get_nowait()
        (path := self.path / x["tag"] / x["timestamp"]).parent.mkdir(exist_ok=True, parents=True)
        data = {k: np.array(v, dtype=object) for k, v in x["item"].items()}
        np.savez_compressed(path, **data) # the actual keys will be mapped in the .npz file
        logger.log_every_s(f"Stored at '{path}' (#storer queue: {self.data_queue.qsize()})", "DEBUG", True)

    @overrides
    def run(self):
        logger.debug(f"Starting DataStorer at '{self.path}'")
        while True:
            try:
                self.get_and_store()
            except Empty:
                if self.is_closed:
                    break
                logger.log_every_s("Empty queue on DataStorer.", "TRACE", True)
                time.sleep(SLEEP_INTERVAL)

        if (n := self.data_queue.qsize()) > 0:
            logger.info(f"Waiting for DataChannel to write {n} left data logs to '{self.path}'")
            while self.data_queue.qsize() > 0:
                self.get_and_store()
        logger.debug(f"Ending DataStorer at '{self.path}'")

    def __len__(self):
        return self.data_queue.qsize()
