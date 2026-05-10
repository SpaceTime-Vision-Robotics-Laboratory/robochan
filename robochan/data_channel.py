"""data_channel.py - Thread-safe channel to place perception data from the data modules"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime
from pprint import pformat
import threading
import numpy as np

from robochan.types import DataItem, DataEqFn
from robochan.utils import logger
from robochan.utils.data_storer import DataStorer

SLEEP_INTERVAL = 0.01

def _fmt(item: dict[str, DataItem]) -> str:
    return pformat({k: v.shape if isinstance(v, np.ndarray) else type(v) for k, v in item.items() })

class DataChannelClosedError(ValueError): pass # pylint: disable=all # noqa

class DataChannel:
    """DataChannel defines the thread-safe data structure where the data producer writes the data and consumers read"""
    def __init__(self, supported_types: list[str], eq_fn: DataEqFn):
        assert len(supported_types) > 0, "cannot have a data channel that supports no data type (i.e. rgb, pose etc.)"
        self.supported_types = set(supported_types)
        self.eq_fn = eq_fn

        self._lock = threading.Lock()
        self._data: dict[str, DataItem] = {}
        self._data_ts: datetime = datetime(1900, 1, 1)
        self._is_closed = False

        self._subscribers_events: list[threading.Event] = [] # a list of subscribers that are notified on data change

    def is_open(self) -> bool:
        """check is the channel is open. Used by other data producers to whether they can continue or not"""
        return not self._is_closed

    def put(self, item: dict[str, DataItem]):
        """Put data into the queue"""
        data_ts = datetime.now()
        assert isinstance(item, dict), type(item)
        assert (ks := set(item.keys())) == (st := self.supported_types), f"Data keys: {ks} vs. Supported types: {st}"
        with self._lock:
            if not self.is_open():
                raise DataChannelClosedError("Channel is closed, cannot put data.")

            if self._data != {} and self.eq_fn(item, self._data): # duplicate data
                return

            logger.log_every_s(f"Got data (data_ts='{data_ts}'):\n'{_fmt(item)}'", "DEBUG", True)
            if (storer := DataStorer.get_instance()) is not None:
                storer.push(item, tag="DataChannel", timestamp=data_ts) # only push different items to logger

            for subscriber_event in self._subscribers_events: # announce each 'subscriber' of new data too
                subscriber_event.set()

            self._data = item
            self._data_ts = data_ts

    def get(self, return_copy: bool=True) -> tuple[dict[str, DataItem], datetime]:
        """
        Return the current item from the channel + its the timestamp when it was received.
        Optionally allows to return the actual reference which may be invalidated when new data arives.
        """
        with self._lock:
            if not self.is_open():
                raise DataChannelClosedError("Channel is closed, cannot get data.")
            return (deepcopy(self._data), deepcopy(self._data_ts)) if return_copy else (self._data, self._data_ts)

    def has_data(self) -> bool:
        """Checks if the channel has data"""
        with self._lock:
            return len(self._data) > 0 and self.is_open()

    def close(self):
        """Closes the channel"""
        with self._lock:
            self._is_closed = True
            for subscriber_event in self._subscribers_events:
                subscriber_event.set() # set green light so the subscribers don't block forever

    def subscribe(self) -> threading.Event:
        """subscribe to this data channel, receiving a threading.Event object"""
        with self._lock:
            self._subscribers_events.append(res := threading.Event())
        return res

    def __repr__(self) -> str:
        return f"[DataChannel] Types: {self.supported_types}. Has data: {self.has_data()}. Open: {self.is_open()}."
