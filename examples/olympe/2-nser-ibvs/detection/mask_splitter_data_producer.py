#!/usr/bin/env python3
# pylint: disable=all
import torch
import cv2
import numpy as np
from dataclasses import dataclass
from overrides import overrides
from robochan import DataProducer, DataItem
from roboimpl.utils import image_resize

from .mask_splitter_nn import MaskSplitterNet

DEVICE = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
MAX_NUMBER_OF_POINTS = 2
CONTOUR_2D_DIMENSIONS = 2
TOL_ERR_NORM = 1E-3
IMAGE_SIZE_SPLITTER_NET = (360, 640)
RED = (255, 0, 0, 8)
BLUE = (0, 0, 255, 8)

@dataclass(frozen=True)
class TargetIBVS:
    confidence: float
    segmented_frame: np.ndarray | None = None
    center: tuple[int, int] | None = None
    size: tuple[int, int] | None = None
    box: tuple[int, int, int, int] | None = None
    is_lost: bool = True
    masks_xy: list[list[tuple[int, int]]] | np.ndarray | None = None
    bbox_oriented: list[tuple[int, ...]] | None = None
    front_mask: np.ndarray | None = None
    back_mask: np.ndarray | None = None
    mask_bool: np.ndarray | None = None

class MaskSplitterDataProducer(DataProducer):
    def __init__(self, splitter_model_path: str, mask_threshold: float, bbox_threshold: float):
        super().__init__(modalities=["front_mask", "back_mask", "bbox_oriented", "splitter_segmentation"],
                         dependencies=["rgb", "segmentation_xy", "segmentation"])
        self.splitter_model = MaskSplitterNet(in_channels=4, out_channels=2, base_channels=32, dropout_rate=0)
        self._load_and_warmup_model(splitter_model_path)

        self.mask_threshold = mask_threshold
        self.bbox_threshold= bbox_threshold

    def _load_and_warmup_model(self, model_path: str):
        self.splitter_model.load_model(model_path).to(DEVICE).eval()
        # self.splitter_model.compile()
        _ = self.splitter_model(torch.randn(1, 4, *IMAGE_SIZE_SPLITTER_NET).to(DEVICE))

    def _compute_bbox_oriented(self, frame: np.ndarray, xy_seg: np.ndarray) -> list[tuple[int, ...]]:
        """
        Computes the oriented bounding box of a segmented object using its polygon coordinates.

        :param frame: Input image frame.
        :param xy_seg: Segmentation polygon points.
        :returns: List of 4 points (tuples) representing the oriented bounding box.
        """
        obj_frame = np.zeros(frame.shape[:2], dtype=np.uint8)
        cv2.fillPoly(obj_frame, pts=[xy_seg], color=255)
        contours, _ = cv2.findContours(obj_frame, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        if not contours:
            raise ValueError("No contours found for the segmentation mask")

        cont = contours[0]
        rect = cv2.minAreaRect(cont)
        box = [tuple(int(x) for x in point) for point in cv2.boxPoints(rect)]
        return box

    def _reorder_bbox_oriented_fallback(self, box: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
        """
        Reoreders the points of an oriented bounding box to ensure consistent ordering,
        starting from the topmost pair of points in image coordinates.

        :param box: List of 4 bounding box corner points.
        :returns: Reordered list of 4 corner points.
        """
        pts = sorted(box, key=lambda x: x[1])
        points_reordered = [pts[0], pts[1]]
        points_neighbours = [*box, box[0]]

        for i in range(len(points_neighbours) - 1):
            if ((points_neighbours[i] == pts[0] and points_neighbours[i + 1] == pts[1]) or
                    (points_neighbours[i] == pts[1] and points_neighbours[i + 1] == pts[0])):
                points_reordered = box[i:] + box[:i]
                break

        points_reordered = [tuple(map(int, p)) for p in points_reordered]
        return points_reordered

    def _reorder_bbox_oriented(self, box: list[tuple[int, ...]], best_front: dict,
                               best_back: dict) -> list[tuple[int, ...]]:
        """
        Reorder bounding box points to achieve a consistent clockwise order:
        [front-left, front-right, back-right, back-left],
        relative to the car's orientation determined by front and back mask centroids.
        Falls back to parent's ordering if masks are insufficient.
        """
        front_mask_points = np.array(best_front.get("masks_xy", []))
        back_mask_points = np.array(best_back.get("masks_xy", []))

        if front_mask_points.size == 0 or back_mask_points.size == 0:
            return self._reorder_bbox_oriented_fallback(box)

        centroid_front = np.mean(front_mask_points, axis=0)
        centroid_back = np.mean(back_mask_points, axis=0)

        box_np = [np.array(p, dtype=float) for p in box]

        front_points_candidates = []
        back_points_candidates = []
        for point_np in box_np:
            dist_to_front = np.linalg.norm(point_np - centroid_front)
            dist_to_back = np.linalg.norm(point_np - centroid_back)
            if dist_to_front < dist_to_back:
                front_points_candidates.append(point_np)
            else:
                back_points_candidates.append(point_np)

        if len(front_points_candidates) != MAX_NUMBER_OF_POINTS or len(back_points_candidates) != MAX_NUMBER_OF_POINTS:
            return self._reorder_bbox_oriented_fallback(box)

        vec_car_orientation = centroid_back - centroid_front
        if np.linalg.norm(vec_car_orientation) < TOL_ERR_NORM:  # Centroids are too close
            return self._reorder_bbox_oriented_fallback(box)

        pts0 = tuple(map(int, front_points_candidates[0]))
        pts1 = tuple(map(int, front_points_candidates[1]))

        points_reordered = [pts0, pts1]

        points_neighbours = [*box, box[0]]
        for i in range(len(points_neighbours) - 1):
            if ((points_neighbours[i] == pts0 and points_neighbours[i + 1] == pts1) or
                    (points_neighbours[i] == pts1 and points_neighbours[i + 1] == pts0)):
                points_reordered = box[i:] + box[:i]
                break

        points_reordered = [tuple(map(int, p)) for p in points_reordered]

        return points_reordered

    def find_best_target(self, frame: np.ndarray, best_mask: np.ndarray,
                         best_mask_xy_scaled: np.ndarray) -> TargetIBVS | None:
        """
        Mask is usually not scaled to image frame, while xy are (yolo...) so we need to resize it ourselves here.
        Parameters:
        - frame The original frame.
        - best_mask The float [0:1] mask which we threshold. Unscaled.
        - best_mask_xy_scaled: The contour points of the best mask scaled to the original frame size.
        """
        mask_bool: np.ndarray = best_mask > self.mask_threshold
        mask_rgb = mask_bool.astype(np.uint8) * 255

        front_mask, back_mask = self.splitter_model.infer(
            image=frame, mask=mask_rgb, image_size=IMAGE_SIZE_SPLITTER_NET, bbox_threshold=self.bbox_threshold)

        segmented_frame = frame.copy()
        best_back = {"conf": 0.8, "idx": None, "masks_xy": []}
        best_front = {"conf": 0.8, "idx": None, "masks_xy": []}

        if (back_mask > 0).any():
            contours_back, _ = cv2.findContours(back_mask * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours_back:
                largest_contour_back = max(contours_back, key=cv2.contourArea)
                masks_xy_back = largest_contour_back.squeeze().astype(np.int32)
                if masks_xy_back.ndim == CONTOUR_2D_DIMENSIONS:
                    best_back["masks_xy"] = masks_xy_back
                    segmented_frame = cv2.fillPoly(segmented_frame, pts=[masks_xy_back], color=RED)

        if (front_mask > 0).any():
            contours_front, _ = cv2.findContours(front_mask * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours_front:
                largest_contour_front = max(contours_front, key=cv2.contourArea)
                masks_xy_front = largest_contour_front.squeeze().astype(np.int32)
                if masks_xy_front.ndim == CONTOUR_2D_DIMENSIONS:
                    best_front["masks_xy"] = masks_xy_front
                    segmented_frame = cv2.fillPoly(segmented_frame, pts=[masks_xy_front], color=BLUE)

        if len(best_back["masks_xy"]) == 0 and len(best_front["masks_xy"]) == 0:
            return None

        combined_masks = []
        if len(best_back["masks_xy"]) > 0:
            combined_masks.append(best_back["masks_xy"])
        if len(best_front["masks_xy"]) > 0:
            combined_masks.append(best_front["masks_xy"])

        all_points = np.vstack(combined_masks)
        assert len(all_points) > 0, combined_masks

        x1, y1 = all_points.min(axis=0)
        x2, y2 = all_points.max(axis=0)
        box = (int(x1), int(y1), int(x2), int(y2))
        center = ((x1 + x2) // 2, (y1 + y2) // 2)
        size = (int(x2 - x1), int(y2 - y1))

        bbox_oriented = self._compute_bbox_oriented(segmented_frame, best_mask_xy_scaled)
        bbox_oriented = self._reorder_bbox_oriented(bbox_oriented, best_front, best_back)

        return TargetIBVS(
            segmented_frame=segmented_frame,
            confidence=max(best_back["conf"], best_front["conf"]),
            center=center,
            size=size,
            box=box,
            is_lost=False,
            masks_xy=all_points,
            bbox_oriented=bbox_oriented,
            front_mask=front_mask,
            back_mask=back_mask,
            mask_bool=mask_bool
        )

    @overrides
    def produce(self, deps: dict[str, DataItem] | None = None) -> dict[str, DataItem]:
        res = {"front_mask": None, "back_mask": None, "bbox_oriented": None, "splitter_segmentation": None}
        if deps["segmentation"] is None or len(deps["segmentation"]) == 0:
            return res

        best_mask = deps["segmentation"][0]
        best_mask_xy_scaled = deps["segmentation_xy"][0].astype(int)
        target = self.find_best_target(deps["rgb"], best_mask, best_mask_xy_scaled)
        if target is None:
            return res

        height, width = deps["rgb"].shape[0:2]
        front_mask_rsz = image_resize(target.front_mask[..., None], height=height, width=width, interpolation="nearest")
        back_mask_rsz = image_resize(target.back_mask[..., None], height=height, width=width, interpolation="nearest")

        return {"front_mask": front_mask_rsz, "back_mask": back_mask_rsz, "bbox_oriented": target.bbox_oriented,
                "splitter_segmentation": target.segmented_frame}
