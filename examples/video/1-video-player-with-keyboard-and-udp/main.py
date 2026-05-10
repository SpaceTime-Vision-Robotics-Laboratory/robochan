#!/usr/bin/env python3
"""keyboard controller and display example with frames of a video not a real or simulated drone"""
# pylint: disable=duplicate-code
from __future__ import annotations
from argparse import ArgumentParser, Namespace
from vre_video import VREVideo

from robochan import ActionsQueue, DataChannel, Robot, Action as Act
from roboimpl.envs.video import VideoPlayerEnv, video_actions_fn, VIDEO_ACTION_NAMES
from roboimpl.controllers import ScreenDisplayer, UDPController, Key, KeyboardController

DEFAULT_SCREEN_RESOLUTION = (420, 640)

def get_args() -> Namespace:
    """cli args"""
    parser = ArgumentParser()
    parser.add_argument("video_path")
    parser.add_argument("--port", type=int, default=42069)
    args = parser.parse_args()
    return args

def main(args: Namespace):
    """main fn"""
    (env := VideoPlayerEnv(VREVideo(args.video_path))).start() # start the video player

    actions_queue = ActionsQueue(action_names=VIDEO_ACTION_NAMES)
    data_channel = DataChannel(supported_types=["rgb", "frame_ix"], eq_fn=lambda a, b: a["frame_ix"] == b["frame_ix"])

    robot = Robot(env=env, data_channel=data_channel, actions_queue=actions_queue, actions_fn=video_actions_fn)
    robot.add_controller(sd := ScreenDisplayer(data_channel, actions_queue, resolution=DEFAULT_SCREEN_RESOLUTION))
    robot.add_controller(UDPController(port=args.port, data_channel=data_channel, actions_queue=actions_queue))
    key_to_action = {Key.Space: Act("PLAY_PAUSE"), Key.Esc: Act("DISCONNECT"), Key.Left: Act("GO_BACK", (env.fps, )),
                     Key.Right: Act("GO_FORWARD", (env.fps, )), Key.Comma: Act("GO_BACK", (1, )),
                     Key.Period: Act("GO_FORWARD", (1, ))}
    robot.add_controller(KeyboardController(data_channel, actions_queue, sd.backend, key_to_action=key_to_action))
    robot.run()

    data_channel.close()
    env.close()

if __name__ == "__main__":
    main(get_args())
