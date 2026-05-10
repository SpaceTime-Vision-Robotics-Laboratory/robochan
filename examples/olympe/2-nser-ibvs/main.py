#!/usr/bin/env python3
"""
IBVS example using: yolo + mask splitter networks
Usage: ./main.py DRONE_IP --weights_path_yolo 29_05_best__yolo11n-seg_sim_car_bunker__all.pt --weights_path_mask_splitter_network mask_splitter-sim-high-quality-partition-v10-dropout_0-augmentations_multi_scenes.pt # pylint:disable=line-too-long
"""
# pylint: disable=duplicate-code
from __future__ import annotations
from queue import Queue
from argparse import ArgumentParser, Namespace
import time
import numpy as np
from olympe.messages import gimbal
from olympe.messages.ardrone3.PilotingState import FlyingStateChanged
from olympe.messages.ardrone3.Piloting import TakeOff
from loggez import make_logger

from detection.mask_splitter_data_producer import MaskSplitterDataProducer, IMAGE_SIZE_SPLITTER_NET

from robochan import Robot, ActionsQueue, DataChannel, DataItem, Action as Act, DataProducer
from roboimpl.data_producers.yolo import YOLODataProducer
from roboimpl.envs.olympe import OlympeEnv, olympe_action_fn, OLYMPE_ACTION_NAMES
from roboimpl.controllers import ScreenDisplayer, Key, KeyboardController
from roboimpl.utils import image_draw_rectangle, image_paste, image_draw_circle, Color

logger = make_logger("IBVS")

QUEUE_MAX_SIZE = 30
SCREEN_RESOLUTION = 480, 640
BBOX_THICKNESS = 0.75
CIRCLE_RADIUS = 1
DT = 0.15
VELOCITY_PERC = 50

def screen_frame_callback(data: dict[str, DataItem]) -> np.ndarray:
    """produces RGB + semantic segmentation as a single frame"""
    res = data["rgb"].copy()

    # if data["segmentation"] is not None:
    #     all_segmentations = data["segmentation"].sum(0).repeat(3, axis=2) * Color.GREENISH
    #     image_paste(res, all_segmentations.astype(np.uint8), inplace=True)

    if data.get("bbox_oriented") is not None:
        p1, p2, p3, p4 = [p[::-1] for p in data["bbox_oriented"]]
        image_draw_circle(res, p1, radius=CIRCLE_RADIUS, color=Color.RED, fill=True, inplace=True)
        image_draw_circle(res, p2, radius=CIRCLE_RADIUS, color=Color.GREEN, fill=True, inplace=True)
        image_draw_circle(res, p3, radius=CIRCLE_RADIUS, color=Color.BLUE, fill=True, inplace=True)
        image_draw_circle(res, p4, radius=CIRCLE_RADIUS, color=Color.WHITE, fill=True, inplace=True)

    if data.get("front_mask") is not None:
        image_paste(res, (data["front_mask"].repeat(3, axis=2) * Color.RED).astype(np.uint8), inplace=True)

    if data.get("back_mask") is not None:
        image_paste(res, (data["back_mask"].repeat(3, axis=2) * Color.GREEN).astype(np.uint8), inplace=True)

    if data.get("bbox") is not None:
        data["bbox"] = data["bbox"][0:1]
        for bbox in data["bbox"]: # plot all bboxes
            x1, y1, x2, y2 = bbox
            image_draw_rectangle(res, (y1, x1), (y2, x2), color=Color.BLACK, thickness=BBOX_THICKNESS, inplace=True)

    return res

def ibvs_olympe_actions_fn(env: OlympeEnv, actions: list[Act]) -> bool:
    """IBVS actions fn. Overrides the generic olympe_actions_fn, but adds other specifics like INITIALIZE_FLIGHT"""
    all_good = True
    for action in actions:
        if action.name in OLYMPE_ACTION_NAMES:
            all_good = all_good and olympe_action_fn(env, action)
            continue

        if action.name == "INITIALIZE_FLIGHT":
            flying_state = env.drone.get_state(FlyingStateChanged)["state"]
            if flying_state.name == "landed":
                logger.info("Taking off...")
                assert env.drone(TakeOff()).wait().success(), "TakeOff failed"
                time.sleep(3)
            gimbal_kwargs = {
                "gimbal_id": 0, "control_mode": "position", "yaw_frame_of_reference": "none", "yaw": 0,
                "roll_frame_of_reference": "none", "roll": 0, "pitch_frame_of_reference": "absolute",}
            logger.info("Tilting gimbal to -45...")
            env.drone(gimbal.set_target(pitch=-45, **gimbal_kwargs)).wait()
            time.sleep(2)
    return all_good

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
        acts.append(Act("INITIALIZE_FLIGHT", parameters=()))
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
    parser.add_argument("drone_ip")
    parser.add_argument("--image_size", nargs=2, type=int, default=IMAGE_SIZE_SPLITTER_NET)
    # yolo params
    parser.add_argument("--yolo_weights_path")
    parser.add_argument("--yolo_threshold", default=0.75, type=float)
    # spliter network params
    parser.add_argument("--mask_splitter_network_weights_path")
    parser.add_argument("--mask_splitter_network_mask_threshold", default=0.5, type=float)
    parser.add_argument("--mask_splitter_network_bbox_threshold", default=0.5, type=float)
    args = parser.parse_args()
    return args

def main(args: Namespace):
    """main fn"""
    env = OlympeEnv(ip=args.drone_ip, image_size=args.image_size)
    action_names = [*OLYMPE_ACTION_NAMES, "INITIALIZE_FLIGHT"]
    actions_queue = ActionsQueue(action_names=action_names, queue=Queue(maxsize=QUEUE_MAX_SIZE))
    supported_types = env.get_modalities()
    dps: list[DataProducer] = []

    if args.yolo_weights_path is not None:
        dps.append(YOLODataProducer(args.yolo_weights_path, threshold=args.yolo_threshold, bgr=True))
        supported_types.extend(dps[-1].modalities)
    if args.mask_splitter_network_weights_path is not None:
        dps.append(MaskSplitterDataProducer(args.mask_splitter_network_weights_path,
                                            mask_threshold=args.mask_splitter_network_mask_threshold,
                                            bbox_threshold=args.mask_splitter_network_bbox_threshold))
        supported_types.extend(dps[-1].modalities)

    data_channel = DataChannel(supported_types=supported_types,
                               eq_fn=lambda a, b: a["metadata"]["time"] == b["metadata"]["time"])

    robot = Robot(env=env, data_channel=data_channel, actions_queue=actions_queue, actions_fn=ibvs_olympe_actions_fn)
    for dp in dps:
        robot.add_data_producer(dp)

    robot.add_controller(sd := ScreenDisplayer(data_channel, actions_queue, resolution=SCREEN_RESOLUTION,
                                               screen_frame_callback=screen_frame_callback))
    robot.add_controller(KeyboardController(data_channel, actions_queue, sd.backend, keyboard_fn=keyboard_fn))
    robot.run()

    env.close()
    data_channel.close()

if __name__ == "__main__":
    main(get_args())
