"""thread_group.py"""
from __future__ import annotations
import threading
from dataclasses import dataclass

from .utils import logger

@dataclass
class ThreadStatus:
    """class that summarizes the lifetime of a thread"""
    is_alive: bool
    exception: Exception | None = None

class _ThreadWithException(threading.Thread):
    """Helper class as per https://stackoverflow.com/a/31614591"""
    @property
    def exception(self) -> Exception | None:
        """needed as we can't really call the ctor of this as it calls threading.Thread again"""
        return getattr(self, "_exception", None)

    def start(self):
        if not self.daemon:
            logger.warning(f"Thread '{self.name}' is not a daemon. This is needed to kill it when Robot dies. Setting.")
            self.daemon = True
        return super().start()

    def run(self):
        try:
            super().run()
        except Exception as e:
            self._exception = e # pylint: disable=attribute-defined-outside-init
            raise e

class ThreadGroup(dict):
    """
    Thread group is a utility dictionary container (str->thread) for managing many threads at once. It also summarizes
    the execution of the thread and if it threw an exception, it captures it to be processed in main.
    """
    def __init__(self, threads: dict[str, threading.Thread] | None = None):
        threads = threads or {}
        for thr in (threads or {}).values():
            assert isinstance(thr, threading.Thread), f"Not all are threads: {thr}"
            assert not isinstance(thr, _ThreadWithException), f"You must pass regular threading.Thread objects: {thr}"
            thr.__class__ = type(type(thr).__name__, (_ThreadWithException, type(thr)), {}) # hack the inherticance list
        super().__init__(**threads)

    def start(self) -> ThreadGroup:
        """starts all the threads"""
        for k, v in self.items():
            assert isinstance(v, threading.Thread), f"{k=}, {type(v)=}"
            logger.debug(f"Starting thread '{k}'")
            v.start()
        return self

    def status(self) -> dict[str, ThreadStatus]:
        """Returns the status (is alive) of all threads"""
        return {k: ThreadStatus(is_alive=thr.is_alive(), exception=thr.exception) for k, thr in self.items()}

    def is_any_dead(self) -> bool:
        """checks if any thread is dead"""
        return any(not t.is_alive() for t in self.values())

    def join(self, timeout: float | None=1.0) -> dict[str, ThreadStatus]:
        """joins all the threads"""
        for k, thr in self.items():
            logger.debug(f"Joining thread '{k}' (timeout: {timeout})")
            if hasattr(thr, "close"):
                thr.close()
            thr.join(timeout)
        return self.status()

    def items(self) -> list[tuple[str, _ThreadWithException]]:
        """override to return the items as a list for simplicity and type hints"""
        return list(super().items())

    def values(self) -> list[_ThreadWithException]:
        """override to return the values as a list for simplicity and type hints"""
        return list(super().values())

    def __repr__(self):
        return f"ThreadGroup ({len(self)}): {'|'.join(f'- {k}: Is alive? {v.is_alive()}' for k, v in self.items())}"

    def __str__(self):
        return "\n".join(f"- {k}: Is alive? {v.is_alive()}" for k, v in self.items())
