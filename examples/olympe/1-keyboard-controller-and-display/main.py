#!/usr/bin/env python3
"""keyboard controller and display example"""
from argparse import ArgumentParser, Namespace
from queue import Queue

from robochan import ActionsQueue, DataChannel, Robot, Action as Act
from roboimpl.envs.olympe import OlympeEnv, olympe_actions_fn, OLYMPE_ACTION_NAMES
from roboimpl.controllers import ScreenDisplayer, Key, KeyboardController

QUEUE_MAX_SIZE = 30
RESOLUTION = 480, 640
DT = 0.15
VELOCITY_PERC = 50

def keyboard_fn(pressed: set[Key]) -> list[Act]:
    """The keyboard to actions function"""
    if Key.Esc in pressed:
        return [Act("DISCONNECT")]
    acts = []
    if Key.Space in pressed:
        acts.append(Act("LIFT"))
        pressed.discard(Key.Space)
    if Key.b in pressed:
        acts.append(Act("LAND"))
        pressed.discard(Key.b)
    if Key.k in pressed:
        acts.append(Act("GIMBAL_ABSOLUTE", parameters=(-45, )))
        pressed.discard(Key.k)

    # piloting: (roll, pitch, yaw, gaz, piloting_time)
    roll = (Key.d in pressed) - (Key.a in pressed)
    pitch = (Key.w in pressed) - (Key.s in pressed)
    yaw = (Key.e in pressed) - (Key.q in pressed)
    gaz = (Key.Up in pressed) - (Key.Down in pressed)
    if roll or pitch or yaw or gaz:
        parameters = (roll * VELOCITY_PERC, pitch * VELOCITY_PERC, yaw * VELOCITY_PERC, gaz * VELOCITY_PERC, DT)
        acts.append(Act("PILOTING", parameters=parameters))
    # gimbal
    if Key.PageUp in pressed:
        acts.append(Act("GIMBAL_UP", parameters=(VELOCITY_PERC, DT)))
    if Key.PageDown in pressed:
        acts.append(Act("GIMBAL_DOWN", parameters=(VELOCITY_PERC, DT)))
    return acts

def get_args() -> Namespace:
    """cli args"""
    parser = ArgumentParser()
    parser.add_argument("ip", help="IP for olympe simulator: 10.202.0.1")
    parser.add_argument("--image_size", nargs=2, type=int)
    args = parser.parse_args()
    return args

def main(args: Namespace):
    """main fn"""
    env = OlympeEnv(ip=args.ip, image_size=args.image_size)
    actions_queue = ActionsQueue(action_names=OLYMPE_ACTION_NAMES, queue=Queue(maxsize=QUEUE_MAX_SIZE))
    data_channel = DataChannel(supported_types=env.get_modalities(),
                               eq_fn=lambda a, b: a["metadata"]["time"] == b["metadata"]["time"])

    robot = Robot(env=env, data_channel=data_channel, actions_queue=actions_queue, actions_fn=olympe_actions_fn)
    robot.add_controller(sd := ScreenDisplayer(data_channel, actions_queue, resolution=RESOLUTION))
    robot.add_controller(KeyboardController(data_channel, actions_queue, sd.backend, keyboard_fn=keyboard_fn))
    robot.run()

    data_channel.close()
    env.close()

if __name__ == "__main__":
    main(get_args())
