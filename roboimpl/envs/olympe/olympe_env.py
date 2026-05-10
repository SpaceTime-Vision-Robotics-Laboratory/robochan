"""olympe_data_producer.py - Data producer for an olympe drone."""
from datetime import datetime
import threading
from overrides import overrides
import numpy as np
import cv2
import olympe
from olympe.video.pdraw import PdrawState
from olympe.messages import gimbal
from olympe.messages.ardrone3.PilotingState import FlyingStateChanged

from robochan import Environment
from robochan.utils import wait_and_clear
from roboimpl.utils import logger, image_resize

class OlympeEnv(Environment):
    """
    Handler for drone video streams that processes frames and manages metadata.
    This class handles the streaming of video from a drone, converting frames to OpenCV
    format, and optionally saving metadata associated with the stream.
    """
    WAIT_FOR_DATA_SECONDS = 5

    def __init__(self, ip: str, image_size: tuple[int, int] | None = None):
        super().__init__()
        self.drone = olympe.Drone(ip)
        self.image_size = image_size
        assert self.drone.connect(), f"could not connect to '{ip}'"
        logger.info(f"Connected to drone at '{ip}'")

        self._current_frame: np.ndarray | None = None
        self._current_metadata: dict | None = None
        self._current_frame_lock = threading.Lock()

        self.drone.streaming.set_callbacks(
            raw_cb=self._yuv_frame_cb,
            start_cb=(lambda _: logger.info("Video stream started.")),
            end_cb=(lambda _: logger.info("Video stream end.")),
            flush_raw_cb=(lambda _: logger.warning("Flush requested for stream. Resetting queue.")),
        )
        assert self.drone.streaming.start(), "error starting stream"
        logger.info(f"Starting streaming from drone at '{ip}'")

    @overrides
    def is_running(self) -> bool:
        return self.drone.connected and self.drone.streaming.state == PdrawState.Playing

    @overrides
    def get_state(self) -> dict:
        wait_and_clear(self.data_ready, OlympeEnv.WAIT_FOR_DATA_SECONDS if self._current_frame is None else None)
        with self._current_frame_lock:
            res = self._current_frame
            res = image_resize(res, *self.image_size) if self.image_size is not None else res
            gimbal_keys = ["roll_absolute", "pitch_absolute", "yaw_absolute"]
            gimbal_state = {k: v for k, v in self.drone.get_state(gimbal.attitude)[0].items() if k in gimbal_keys}
            flying_state = self.drone.get_state(FlyingStateChanged)["state"]
            return {"rgb": res, "metadata": self._current_metadata, "gimbal": gimbal_state,
                    "flying_state": flying_state.name}

    @overrides
    def get_modalities(self) -> list[str]:
        return ["rgb", "metadata", "gimbal", "flying_state"]

    @overrides
    def close(self):
        self.data_ready.set()
        self.drone.disconnect()

    def _yuv_frame_cb(self, yuv_frame: olympe.VideoFrame):
        """
        This function will be called by Olympe for each decoded YUV frame. It transforms the YUV frame into an OpenCV
        frame, and unrefs the frame.
        """
        if not yuv_frame:
            logger.warning("Received empty frame")
            return

        cv2_cvt_colors = {
            olympe.VDEF_I420: cv2.COLOR_YUV2RGB_I420,
            olympe.VDEF_NV12: cv2.COLOR_YUV2RGB_NV12,
        }

        try:
            with self._current_frame_lock:
                yuv_frame.ref()
                self._current_frame = cv2.cvtColor(yuv_frame.as_ndarray(), cv2_cvt_colors[yuv_frame.format()])
                self._current_metadata = {
                    "time": (now := datetime.now().isoformat()),
                    "drone": yuv_frame.vmeta()[1]["drone"],
                    "camera": yuv_frame.vmeta()[1]["camera"],
                }
                logger.trace(f"Received a new frame at {now}. Shape: {self._current_frame.shape}")
                self.data_ready.set()
        finally:
            yuv_frame.unref()
