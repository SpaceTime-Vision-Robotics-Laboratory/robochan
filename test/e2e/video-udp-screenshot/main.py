#!/usr/bin/env python3
"""keyboard controller and display example with frames of a video not a real or simulated drone"""
# pylint: disable=duplicate-code
from __future__ import annotations
from argparse import ArgumentParser, Namespace
from vre_video import VREVideo

from robochan import ActionsQueue, DataChannel, Robot
from roboimpl.envs.video import VideoPlayerEnv, video_actions_fn, VIDEO_ACTION_NAMES
from roboimpl.controllers import UDPController

SCREEN_HEIGHT = 420

def get_args() -> Namespace:
    """cli args"""
    parser = ArgumentParser()
    parser.add_argument("video_path")
    parser.add_argument("--port", type=int, default=42069)
    parser.add_argument("--frame_resolution", type=int, nargs=2, help="optional, only for video_path='-'")
    parser.add_argument("--fps", type=float, help="optional only for video_path='-'")
    args = parser.parse_args()
    return args

def main(args: Namespace):
    """main fn"""
    reader_kwargs = {} if args.video_path != "-" else {"resolution": args.frame_resolution, "fps": args.fps}
    (video_player := VideoPlayerEnv(VREVideo(args.video_path, **reader_kwargs))).start() # start the video player

    actions_queue = ActionsQueue(action_names=VIDEO_ACTION_NAMES)
    data_channel = DataChannel(supported_types=["rgb", "frame_ix"], eq_fn=lambda a, b: a["frame_ix"] == b["frame_ix"])

    robot = Robot(env=video_player, data_channel=data_channel, actions_queue=actions_queue, actions_fn=video_actions_fn)
    udp_controller = UDPController(port=args.port, data_channel=data_channel, actions_queue=actions_queue)
    robot.add_controller(udp_controller, name="UDP controller")
    robot.run()

    video_player.close()

if __name__ == "__main__":
    main(get_args())
