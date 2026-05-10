"""yolo_data_producer.py - produces bounding boxes using a yolo pre-trained checkpoint"""
import numpy as np
from overrides import overrides
from ultralytics import YOLO # pylint: disable=import-error
from ultralytics.engine.results import Masks, Boxes # pylint: disable=import-error
from torch.nn import functional as F
from loggez import make_logger
from robochan import DataProducer, DataItem

logger = make_logger("ROBOIMPL_YOLO")

Bbox = tuple[int, int, int, int]
Segmentation = np.ndarray

class YOLODataProducer(DataProducer):
    """Yolo data producer - Returns bbox and/or segmentations. We can also optionally resize segmentations."""
    def __init__(self, weights_path: str, threshold: float, resize_segmentations: bool = True, bgr: bool=False):
        super().__init__(modalities=["bbox", "bbox_confidence", "segmentation", "segmentation_xy"],
                         dependencies=["rgb"])
        self.yolo = YOLO(weights_path)
        self.threshold = threshold
        self.resize_segmentations = resize_segmentations
        self.bgr = bgr

    def _compute_yolo(self, rgb: np.ndarray) \
            -> tuple[list[Bbox], list[float], list[Segmentation] | None, list[np.ndarray] | None] | None:
        """returns 4 lists: bounding boxes (over thr), confidences of bboxes, segmentation masks and segmentations xy"""
        results = self.yolo.predict(rgb)[0]
        boxes = good_boxes = results.boxes
        masks = good_masks = results.masks

        if no_bbox := (boxes is None or boxes.conf is None or len(boxes.conf) == 0 or len(good_boxes) == 0):
            logger.log_every_s(f"No bounding box was produced or none above threshold {self.threshold}")
        else:
            good_boxes: Boxes = boxes[boxes.conf > self.threshold]
            logger.log_every_s(f"Kept {len(good_boxes)}/{len(boxes)} bounding boxes after applying threshold.")
            no_bbox = no_bbox and (len(good_boxes) == 0)

        if no_segm := (masks is None or len(masks.data) == 0):
            logger.log_every_s("No segmentation masks were produced.")
        else:
            good_masks: Masks = masks[boxes.conf > self.threshold] if boxes.conf is not None else masks
            no_segm = no_segm and (len(good_masks) == 0)

        bbox = good_boxes.xyxy.int().tolist() if not no_bbox else None
        bbox_confidence = good_boxes.conf.tolist() if not no_bbox else None
        segmentation = None
        if not no_segm and len(good_masks) > 0:
            segmentation = good_masks.data[:, None] # (n_objs, 1, H, W)
            if self.resize_segmentations:
                segmentation = F.interpolate(segmentation, size=good_masks.orig_shape) # (n_objs, 1, H', W')
            segmentation = segmentation.permute(0, 2, 3, 1).cpu().numpy() # (n_objs, H', W', 1)
        segmentation_xy = good_masks.xy if not no_segm else None
        return bbox, bbox_confidence, segmentation, segmentation_xy

    @overrides
    def produce(self, deps: dict[str, DataItem] | None = None) -> dict[str, DataItem]:
        logger.log_every_s(f"RGB: {deps['rgb'].shape}", "DEBUG")
        rgb = deps["rgb"] if self.bgr is False else deps["rgb"][..., ::-1] # some yolo model'r trained with BGR images:)
        yolo_res = self._compute_yolo(rgb)
        bbox, bbox_confidence, segmentation, segmentation_xy = yolo_res if yolo_res is not None else [None] * 4
        logger.log_every_s(f"Segmentation: {segmentation.shape if segmentation is not None else None}", "DEBUG")
        return {"bbox": bbox, "bbox_confidence": bbox_confidence,
                "segmentation": segmentation, "segmentation_xy": segmentation_xy}
