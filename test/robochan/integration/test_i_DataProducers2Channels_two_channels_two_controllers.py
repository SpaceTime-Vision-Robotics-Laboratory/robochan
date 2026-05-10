from __future__ import annotations
import threading
from datetime import datetime
import time
import numpy as np

from robochan import (ActionsQueue, DataChannel, DataItem, ThreadGroup, DataProducers2Channels, Actions2Environment,
                      LambdaDataProducer, Controller, Action, Environment, RawDataProducer)
from robochan.utils import freq_barrier

N_FRAMES = 60
N1 = 0
N2 = 0

class FakeVideo(threading.Thread, Environment):
    def __init__(self, frames: np.ndarray, fps: int):
        threading.Thread.__init__(self, daemon=True)
        self.frames = frames
        self.fps = fps
        self._frame_ix = 0
        self._current_frame = frames[0]
        self._lock = threading.Lock()
        self._prev_time = datetime(1900, 1, 1)

    def get_state(self) -> dict[str, np.ndarray | int]:
        with self._lock:
            return {"rgb": self._current_frame, "frame_ix": self._frame_ix}

    def is_running(self):
        res = self._frame_ix < len(self.frames)
        return res

    def get_modalities(self):
        return ["rgb", "frame_ix"]

    def run(self):
        while self._frame_ix < len(self.frames):
            self._prev_time = freq_barrier(self.fps, self._prev_time)
            with self._lock:
                self._current_frame = self.frames[self._frame_ix]
                self._frame_ix += 1

def rgb_rev_produce_fn(deps: dict[str, DataItem] | None = None) -> dict[str, DataItem]:
    """fake some lag for the second producer"""
    time.sleep(0.5)
    return {"rgb_rev": deps["rgb"][:, ::-1]}

def controller_fn1(data: dict[str, DataItem]) -> list[Action]:
    global N1
    N1 += 1
    return []

def controller_fn2(data: dict[str, DataItem]) -> list[Action]:
    global N2
    N2 += 1
    return []

def test_i_DataProducers2Channels_two_channels_two_controllers():
    """main fn"""
    frames = np.random.randint(0, 255, size=(N_FRAMES, 30, 30, 3), dtype=np.uint8)
    video_player = FakeVideo(frames, fps=30)

    actions_queue = ActionsQueue(action_names=["a"])
    dc1 = DataChannel(supported_types=["rgb", "frame_ix"], eq_fn=lambda a, b: a["frame_ix"] == b["frame_ix"])
    dc2 = DataChannel(supported_types=["rgb", "frame_ix", "rgb_rev"], eq_fn=lambda a, b: a["frame_ix"] == b["frame_ix"])

    video_dp = RawDataProducer(env=video_player)
    rgb_rev_dp = LambdaDataProducer(rgb_rev_produce_fn, modalities=["rgb_rev"], dependencies=["rgb"])
    dpl = DataProducers2Channels(data_producers=[video_dp, rgb_rev_dp], data_channels=[dc1, dc2])
    ctrl1 = Controller(dc1, actions_queue, controller_fn1)
    ctrl2 = Controller(dc2, actions_queue, controller_fn2)
    action2video = Actions2Environment(env=video_player, actions_queue=actions_queue, actions_fn=lambda : None)

    # start the threads
    threads = ThreadGroup({
        "Video player env": video_player,
        "Video -> Data": dpl,
        "Ctrl1": ctrl1,
        "Ctrl2": ctrl2,
        "Action -> Video": action2video,
    }).start()

    while not threads.is_any_dead():
        time.sleep(0.1)

    threads.join(timeout=0.5)
    assert N1 > 20, N1
    assert N2 < 10, N2
    print(f"{N1=} {N2=}")

if __name__ == "__main__":
    test_i_DataProducers2Channels_two_channels_two_controllers()
