"""keyboard_controller.py - Generic multi-key keyboard controller for robobase"""
import os
from typing import Callable
from datetime import datetime
from robochan import BaseController, Action, ActionsQueue, DataChannel
from robochan.utils import freq_barrier
from robochan.controller import INITIAL_DATA_MAX_DURATION_S
from roboimpl.utils import logger
from roboimpl.controllers.screen_displayer.screen_displayer_utils import DisplayerBackend, Key

FREQ = int(os.getenv("ROBOIMPL_KEYBOARD_CONTROLLER_FREQ", "30")) # poll keyboard events 30 times per second.

# pylint: disable=invalid-name
KeyboardFn = Callable[[set[Key]], list[Action]] # keys -> (generic) actions

class KeyboardController(BaseController):
    """Generic multi-key keyboard controller for robobase"""
    def __init__(self, data_channel: DataChannel, actions_queue: ActionsQueue, backend: DisplayerBackend,
                 keyboard_fn: KeyboardFn = None, key_to_action: dict[Key, Action] | None = None):
        if key_to_action is not None:
            assert keyboard_fn is None, "key_to_action cannot be set if keyboard_fn is also set"
        super().__init__(data_channel, actions_queue)
        self.keyboard_fn = keyboard_fn or self._keyboard_fn
        self.key_to_action = key_to_action or {}
        self.backend = backend

    def run(self):
        """default data polling scheduling"""
        self.data_channel_event.wait(INITIAL_DATA_MAX_DURATION_S) # wait for initial data
        prev = datetime.now()
        while self.data_channel.has_data():
            prev = freq_barrier(FREQ, prev)

            pressed = self.backend.get_pressed_keys()
            actions: list[Action] = self.keyboard_fn(pressed)
            for action in actions:
                self.actions_queue.put(action, data_ts=None)

    def _keyboard_fn(self, pressed: set[Key]) -> list[Action]:
        res: list[Action] = []
        for key in pressed:
            if (action := self.key_to_action.get(key)) is not None:
                res.append(action)
        if len(pressed) > 0:
            logger.log_every_s(f"Pressed '{pressed}'. Returning: {res}", "INFO", True)
        return res
