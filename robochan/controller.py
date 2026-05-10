"""controller.py - Interface between the DataConsumer's data and the next best action for the ActionsQueue"""
from __future__ import annotations
from typing import Callable
import threading
from overrides import overrides

from .action import Action
from .data_channel import DataChannel, DataChannelClosedError
from .actions_queue import ActionsQueue
from .utils import logger, wait_and_clear
from .types import ControllerFn

INITIAL_DATA_MAX_DURATION_S = 5

class BaseController(threading.Thread):
    """
    Interface defining the requirements of a data consumer getting data from a DataProducer.
    Users can extend this class and define their scheduling but the default behavior is to provide a controller fn
    and use the default scheduling (data polling) provided in this library.
    """
    def __init__(self, data_channel: DataChannel, actions_queue: ActionsQueue):
        threading.Thread.__init__(self, daemon=True)
        self._data_channel = data_channel
        self._actions_queue = actions_queue
        self.data_channel_event = self.data_channel.subscribe()

    @property
    def data_channel(self) -> DataChannel:
        """The data queue where the data taken from"""
        return self._data_channel

    @property
    def actions_queue(self) -> ActionsQueue:
        """The actions where where the action is sent to"""
        return self._actions_queue

class Controller(BaseController):
    """small wrapper on top of a generic controller for 'planner' kind of controllers with a controller_fn callback."""
    def __init__(self, data_channel: DataChannel, actions_queue: ActionsQueue,
                 controller_fn: ControllerFn = None,
                 initial_data_max_duration_s: float = INITIAL_DATA_MAX_DURATION_S):
        super().__init__(data_channel, actions_queue)
        assert isinstance(controller_fn, Callable), type(controller_fn)
        self.controller_fn = controller_fn
        self.initial_data_max_duration_s = initial_data_max_duration_s

    @overrides
    def run(self):
        """default data polling scheduling"""
        self.data_channel_event.wait(self.initial_data_max_duration_s) # wait for initial data
        while self.data_channel.has_data():
            wait_and_clear(self.data_channel_event) # get new data and set red light again.
            try:
                curr_data, data_ts = self.data_channel.get()
            except DataChannelClosedError:
                break
            logger.log_every_s(f"Processing data (data_ts='{data_ts}')", "DEBUG", True)
            # the planner may also return 0 actions ("IDK" action basically)
            actions: list[Action] = self.controller_fn(curr_data)
            for action in actions:
                self.actions_queue.put(action, data_ts=data_ts)
