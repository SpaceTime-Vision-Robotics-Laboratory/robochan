#!/usr/bin/env python3
"""Usage ./main.py [device_id]. Space for pause, Esc for exit."""
import sys

from robochan import Environment, Robot, DataChannel, ActionsQueue, Action
from roboimpl.controllers import ScreenDisplayer, Key, KeyboardController
from roboimpl.utils import logger

try:
    import cv2
except ImportError as e:
    logger.error(e)

class WebcamEnv(Environment):
    """Basic OpenCV-based environment to get the current RGB frame from a webcam"""
    def __init__(self, device_id: int):
        super().__init__()
        self.cam = cv2.VideoCapture(device_id)
        self.is_paused = False
        self.curr_frame = None

    def get_state(self) -> dict:
        if self.is_paused is False or self.curr_frame is None:
            self.curr_frame = self.cam.read()[1][..., ::-1]
        return {"rgb": self.curr_frame}

    def is_running(self) -> bool:
        return self.cam.isOpened()

    def get_modalities(self) -> list[str]:
        return ["rgb"]

    def close(self):
        self.cam.release()

def actions_fn(env: WebcamEnv, actions: list[Action]) -> bool | None:
    """The action->env function. Takes the generic action returned by the controller (keyboard) and updates the env"""
    for action in actions:
        if action.name == "pause":
            env.is_paused = not env.is_paused
        if action.name == "close":
            env.cam.release()
    return True

def keyboard_fn(pressed: set[Key]) -> list[Action]:
    """keyboard to actions function"""
    res = []
    if Key.Space in pressed:
        res.append(Action("pause"))
        pressed.discard(Key.Space)
    if Key.Esc in pressed:
        return [Action("close")]
    return res

def main():
    """main fn"""
    env = WebcamEnv(device_id=0 if len(sys.argv) == 1 else int(sys.argv[1])) # change if needed
    data_channel = DataChannel(supported_types=["rgb"], eq_fn=lambda a, b: False) # eq fn: every data is assumed new
    actions_queue = ActionsQueue(action_names=["pause", "close"])
    robot = Robot(env, data_channel, actions_queue, actions_fn=actions_fn)
    robot.add_controller(sd := ScreenDisplayer(data_channel, actions_queue))
    robot.add_controller(KeyboardController(data_channel, actions_queue, sd.backend, keyboard_fn=keyboard_fn))
    robot.run()

    data_channel.close()
    env.close()

if __name__ == "__main__":
    main()
