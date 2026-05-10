#!/usr/bin/env python3
"""keyboard controller and display example with frames of a video + semantic segmentation"""
# pylint: disable=duplicate-code
from __future__ import annotations
from functools import partial
from argparse import ArgumentParser, Namespace
import numpy as np
from vre_video import VREVideo
from vre_repository.utils import colorize_depth, colorize_semantic_segmentation # pylint: disable=all

from robochan import Robot, ActionsQueue, DataChannel, DataItem, Action as Act
from roboimpl.data_producers.yolo import YOLODataProducer
from roboimpl.envs.video import VideoPlayerEnv, video_actions_fn, VIDEO_ACTION_NAMES
from roboimpl.controllers import ScreenDisplayer, Key, KeyboardController
from roboimpl.utils import image_draw_rectangle, image_paste, Color, image_resize
from roboimpl.data_producers.vre import build_vre_data_producers

BBOX_THICKNES = 1
DEFAULT_SCREEN_RESOLUTION = (600, 800)

def screen_frame_callback(data: dict[str, DataItem], color_map: list[Color], only_top1_bbox: bool) -> np.ndarray:
    """produces RGB + semantic segmentation as a single frame"""
    res, (h, w) = data["rgb"], data["rgb"].shape[0:2]
    if "bbox" in data and data["bbox"] is not None:
        data["bbox"] = data["bbox"][0:1] if only_top1_bbox else data["bbox"]
        for bbox in data["bbox"]:
            x1, y1, x2, y2 = bbox
            res = image_draw_rectangle(res, top_left=(y1, x1), bottom_right=(y2, x2),
                                       color=Color.GREEN, thickness=BBOX_THICKNES)

    if "segmentation" in data and data["segmentation"] is not None:
        # merge all segmentation masks together (as bools)
        data["segmentation"] = data["segmentation"][0:1] if only_top1_bbox else data["segmentation"]
        all_segmentations = (data["segmentation"].sum(0).repeat(3, axis=-1) * Color.GREENISH).astype(np.uint8)
        res = image_paste(res, all_segmentations)

    if "safeuav" in data:
        sema_rgb = colorize_semantic_segmentation(data["safeuav"].argmax(-1)[None], color_map, method="fast_simple")[0]
        sema_rgb_rsz = image_resize(sema_rgb, h, w, "nearest") # (Hs, Ws, 3) -> (H, W, 3)
        res = np.concatenate([res, sema_rgb_rsz], axis=1)

    if "depth_dpt" in data:
        depth_rgb = (colorize_depth(data["depth_dpt"][None], percentiles=[1, 95]) * 255).astype("uint8")[0]
        depth_rgb_rsz = image_resize(depth_rgb, h, w, "nearest") # (Hd, Wd, 3) -> (H, W, 3)
        res = np.concatenate([res, depth_rgb_rsz], axis=1)
    return res

def get_args() -> Namespace:
    """cli args"""
    parser = ArgumentParser()
    parser.add_argument("video_path")
    parser.add_argument("--frame_resolution", type=int, nargs=2, help="optional, only for video_path='-'")
    parser.add_argument("--fps", type=float, help="optional only for video_path='-'")
    # yolo params
    parser.add_argument("--yolo_weights_path")
    parser.add_argument("--yolo_threshold", default=0.75, type=float, help="applied to both bbox and segmentation")
    parser.add_argument("--yolo_only_top1_bbox", action="store_true")
    # vre params
    parser.add_argument("--vre_config_path")
    args = parser.parse_args()
    return args

def main(args: Namespace):
    """main fn"""
    reader_kwargs = {} if args.video_path != "-" else {"resolution": args.frame_resolution, "fps": args.fps}
    (env := VideoPlayerEnv(VREVideo(args.video_path, **reader_kwargs))).start() # start the video player
    color_map = None

    supported_types, dps = ["rgb", "frame_ix"], []
    if args.yolo_weights_path is not None:
        supported_types.extend(["bbox", "bbox_confidence", "segmentation", "segmentation_xy"])
        dps.append(YOLODataProducer(weights_path=args.yolo_weights_path, threshold=args.yolo_threshold))
    if args.vre_config_path is not None:
        for dp in build_vre_data_producers(args.vre_config_path):
            supported_types.append(dp.repr.name)
            dps.append(dp)
            if dp.repr.name == "safeuav":
                color_map = dp.repr.color_map

    data_channel = DataChannel(supported_types=supported_types, eq_fn=lambda a, b: a["frame_ix"] == b["frame_ix"])
    actions_queue = ActionsQueue(action_names=VIDEO_ACTION_NAMES)
    robot = Robot(env=env, data_channel=data_channel, actions_queue=actions_queue, actions_fn=video_actions_fn)
    for dp in dps:
        robot.add_data_producer(dp)

    f_screen_frame_callback = partial(screen_frame_callback, color_map=color_map,
                                      only_top1_bbox=args.yolo_only_top1_bbox)
    robot.add_controller(sd := ScreenDisplayer(data_channel, actions_queue, resolution=DEFAULT_SCREEN_RESOLUTION,
                                               screen_frame_callback=f_screen_frame_callback))
    key_to_action = {Key.Space: Act("PLAY_PAUSE"), Key.Esc: Act("DISCONNECT"), Key.Left: Act("GO_BACK", (env.fps, )),
                     Key.Right: Act("GO_FORWARD", (env.fps, )), Key.Comma: Act("GO_BACK", (1, )),
                     Key.Period: Act("GO_FORWARD", (1, ))}
    robot.add_controller(KeyboardController(data_channel, actions_queue, sd.backend, key_to_action=key_to_action))

    robot.run()
    env.close()
    data_channel.close()

if __name__ == "__main__":
    main(get_args())
