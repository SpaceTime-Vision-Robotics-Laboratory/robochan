"""screen_displayer.py - This module reads the data from a drone and prints the RGB. No action is produced"""
from __future__ import annotations
import os
from typing import Callable
from overrides import overrides
import numpy as np

from robochan import DataChannel, DataItem, BaseController, ActionsQueue
from roboimpl.utils import image_resize, logger, CircularBuffer

from .screen_displayer_utils import DisplayerState, DisplayerBackend
from .screen_displayer_tkinter import ScreenDisplayerTkinter
from .screen_displayer_sdl2 import ScreenDisplayerSDL2

INITIAL_TIMEOUT_S = 60
TIMEOUT_S = 0.01
INITIAL_RESOLUTION_FALLBACK = (480, 640)
DEFAULT_BACKEND = os.getenv("ROBOIMPL_SCREEN_DISPLAYER_BACKEND", "sdl2")

class ScreenDisplayer(BaseController):
    """ScreenDisplayer provides support for displaying the DataChannel at each frame + support for keyboard actions."""
    def __init__(self, data_channel: DataChannel, actions_queue: ActionsQueue,
                 resolution: tuple[int, int] | None = None,
                 screen_frame_callback: Callable[[DataItem], np.ndarray | None] | None = None,
                 backend: str | None = None):
        super().__init__(data_channel=data_channel, actions_queue=actions_queue)
        self.initial_resolution = resolution
        self.backend_type = backend or DEFAULT_BACKEND
        self.screen_frame_callback = screen_frame_callback or ScreenDisplayer.rgb_only_displayer

        self.backend: DisplayerBackend = {
            "tkinter": lambda: ScreenDisplayerTkinter(),
            "sdl2": lambda: ScreenDisplayerSDL2(),
        }[self.backend_type]()

    @staticmethod
    def rgb_only_displayer(data: dict[str, DataItem]) -> np.ndarray:
        """returns the final frame as RGB from the current data (rgb, semantic etc.)"""
        return data["rgb"]

    def _get_initial_height_width(self, prev_data: dict[str, DataItem]) -> tuple[int, int]:
        """try hard to get the initial h,w. Either provided in ctor, from data (if 'rgb' is found) or default"""
        if self.initial_resolution is not None:
            return self.initial_resolution
        if "rgb" in prev_data:
            return prev_data["rgb"].shape[0:2]
        return INITIAL_RESOLUTION_FALLBACK

    @overrides
    def run(self):
        self.data_channel_event.wait(INITIAL_TIMEOUT_S)

        height, width = self._get_initial_height_width(prev_data=self.data_channel.get()[0])
        self.backend.initialize_window(height, width, title=f"Screen Displayer ({self.backend_type})")

        old_state = DisplayerState((height, width), hud=False)
        fpss = CircularBuffer(capacity=20)

        while self.data_channel.has_data():
            self.backend.poll_events() # need to call this to also update the frames
            logger.log_every_s(f"FPS: {len(fpss) / (sum(fpss.get()) + 1e-5):.2f}", "DEBUG")
            new_state = DisplayerState(resolution=self.backend.get_current_size(), hud=False)

            ui_event = new_state != old_state # UI events i.e. resize or toggle info
            data_event = self.data_channel_event.wait(timeout=TIMEOUT_S) # data events: new frame arived
            if not ui_event and not data_event:
                continue
            logger.log_every_s(f"Updating UI: {ui_event=}, {data_event=}", "DEBUG", log_to_next_level=True)

            self.data_channel_event.clear() # if green, make it red again
            curr_data, _ = self.data_channel.get(return_copy=False)

            frame = self.screen_frame_callback(curr_data)
            if frame is None:
                continue
            frame_rsz = image_resize(frame, height=new_state.resolution[0], width=new_state.resolution[1],
                                     interpolation="nearest") # can be noop. 'nearest' for max speed.
            self.backend.update_frame(frame_rsz)

            fpss.add((new_state.ts - old_state.ts).total_seconds())
            old_state = new_state

        self.backend.close_window()
        logger.warning("ScreenDisplayer thread stopping")
