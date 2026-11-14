# backend/services/detector.py
# Core detection engine.
# Loads the trained YOLOv8 model and runs inference on a frame.
#
# What it computes per detected product:
#   - facings_count   : how many of this product are visible in THIS frame
#   - estimated_total : facings_count * (shelf_depth_cm / product_depth_cm)
#                        This is a CAPACITY-based estimate (max that could
#                        fit behind), not a vision-based hidden-object count.
#   - severity         : full / low / empty, based on percentage of the
#                        planogram's expected_facings (ideal stock target):
#                           0%        -> empty   (out of stock)
#                           0-40%     -> low     (low stock alert)
#                           40-100%+  -> full    (normal, no alert)
#                        If the product has not been calibrated yet
#                        (expected_facings == 0 / missing), severity =
#                        "uncalibrated".
#
# It also detects MISPLACED products. THERE ARE NO PREDEFINED SHELF SLOTS -
# "what's supposed to be where" is determined fresh from THIS SAME PHOTO,
# not from a fixed layout. See `_detect_misplaced` below for exactly how.

import json
import os
from typing import List

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from backend.models.schemas import DetectionResult
from backend.services import planogram_service

# PyTorch 2.6+ changed torch.load's default to weights_only=True, which
# blocks loading full Ultralytics checkpoints (they pickle the model
# class + Sequential containers, not just tensor weights). Allowlisting
# classes one by one is fragile - instead we force weights_only=False
# for this trusted, self-trained checkpoint by patching torch.load.
_original_torch_load = torch.load


def _patched_torch_load(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _original_torch_load(*args, **kwargs)


torch.load = _patched_torch_load

PLANOGRAM_PATH = "backend/config/planogram.json"

# Thresholds for percentage-based severity (see module docstring)
LOW_STOCK_PCT = 40.0

# Detection runs on a 640x640 resized frame
FRAME_SIZE = 640

# Misplaced-detection column inference: how close (in pixels, at 640-wide
# detection resolution) two detections' x-centers need to be to count as
# "the same column" when we don't have a predefined slot grid. This is a
# tunable heuristic, not a physical constant - see _group_into_columns.
COLUMN_GROUPING_TOLERANCE_PX = 60


def _load_planogram() -> dict:
    with open(PLANOGRAM_PATH) as f:
        return json.load(f)


class ShelfDetector:
    """Wraps the trained YOLOv8 model and applies planogram logic."""

    def __init__(self, model_path: str):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model weights not found at {model_path}")
        self.model = YOLO(model_path)
        print(f"[ShelfDetector] Loaded model from {model_path}")
        print(f"[ShelfDetector] Classes: {self.model.names}")

    def _planogram(self) -> dict:
        # Re-read on every call so edits via the Planogram page take effect
        # immediately, with no server restart needed.
        return _load_planogram()

    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Resize + CLAHE contrast enhancement for varied shop lighting."""
        resized = cv2.resize(frame, (FRAME_SIZE, FRAME_SIZE))
        lab = cv2.cvtColor(resized, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def detect(self, frame: np.ndarray, confidence_threshold: float = 0.4) -> dict:
        """
        Run detection on a single frame.

        Returns:
            {
              "detections": [DetectionResult, ...],
              "class_counts": {"maggi_small": 2, "empty_slot": 1, ...},
              "health_score": 0-100 float,
              "misplaced_products": [ {...}, ... ]
            }
        """
        planogram = self._planogram()
        expected_facings = planogram.get("expected_facings", {})
        dims = planogram.get("product_dimensions", {})
        shelf_depth_cm = planogram.get("shelf_depth_cm", 15.0)

        processed = self.preprocess_frame(frame)
        results = self.model(processed, conf=confidence_threshold, verbose=False)

        class_counts: dict = {}
        detections: List[DetectionResult] = []
        raw_boxes: List[dict] = []  # for misplaced-product pass

        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                class_name = self.model.names[class_id]
                confidence = float(box.conf[0])
                bbox = [float(v) for v in box.xyxy[0].tolist()]

                raw_boxes.append({"product_class": class_name, "bbox": bbox})

                class_counts[class_name] = class_counts.get(class_name, 0) + 1

                if class_name == "empty_slot":
                    # empty_slot has no "stock level" - record and skip severity calc
                    detections.append(DetectionResult(
                        product_class=class_name,
                        confidence=confidence,
                        bbox=bbox,
                        facings_count=class_counts[class_name],
                        estimated_total=0,
                        severity="empty",
                    ))
                    continue

                facings = class_counts[class_name]

                # Capacity-based estimate: how many could fit given shelf depth
                product_depth = dims.get(class_name, {}).get("depth_cm", 0)
                if product_depth > 0:
                    depth_multiplier = max(1, int(shelf_depth_cm / product_depth))
                else:
                    depth_multiplier = 1
                estimated_total = facings * depth_multiplier

                severity = self._severity(class_name, facings, expected_facings)

                detections.append(DetectionResult(
                    product_class=class_name,
                    confidence=confidence,
                    bbox=bbox,
                    facings_count=facings,
                    estimated_total=estimated_total,
                    severity=severity,
                ))

        health_score = self._health_score(class_counts, expected_facings)
        misplaced = self._detect_misplaced(raw_boxes)

        return {
            "detections": detections,
            "class_counts": class_counts,
            "health_score": health_score,
            "misplaced_products": misplaced,
        }

    def _severity(self, product_class: str, facings: int, expected_facings: dict) -> str:
        expected = expected_facings.get(product_class, 0)

        if expected == 0:
            return "uncalibrated"
        if facings == 0:
            return "empty"

        pct = (facings / expected) * 100
        if pct < LOW_STOCK_PCT:
            return "low"
        return "full"

    def _health_score(self, class_counts: dict, expected_facings: dict) -> float:
        """0-100. Average of (detected/expected) across calibrated products only."""
        calibrated = {p: e for p, e in expected_facings.items() if e > 0}
        if not calibrated:
            return 0.0

        total = 0.0
        for product, expected in calibrated.items():
            detected = class_counts.get(product, 0)
            total += min(detected / expected, 1.0) * 100

        return round(total / len(calibrated), 1)

    def _group_into_columns(self, raw_boxes: List[dict]) -> List[List[dict]]:
        """
        Groups detections (excluding empty_slot) into shelf "columns" purely
        from THIS photo's own bounding-box x-positions - no predefined slot
        layout is used anywhere here.

        Method: sort all boxes left-to-right by bbox center-x, then walk
        through them and start a new column every time the gap to the next
        box's center-x exceeds COLUMN_GROUPING_TOLERANCE_PX. This finds
        natural horizontal clusters (one shelf column = one cluster of
        boxes whose x-centers sit close together), without needing to know
        in advance how many columns the shelf has.
        """
        items = [b for b in raw_boxes if b["product_class"] != "empty_slot"]
        if not items:
            return []

        def center_x(b):
            x1, _, x2, _ = b["bbox"]
            return (x1 + x2) / 2

        items_sorted = sorted(items, key=center_x)

        columns: List[List[dict]] = [[items_sorted[0]]]
        for prev, cur in zip(items_sorted, items_sorted[1:]):
            if center_x(cur) - center_x(prev) > COLUMN_GROUPING_TOLERANCE_PX:
                columns.append([])
            columns[-1].append(cur)

        return columns

    def _detect_misplaced(self, raw_boxes: List[dict]) -> List[dict]:
        """
        Misplaced-product detection with NO predefined shelf slots.

        For THIS photo only:
          1. Group detections into columns purely from their own x-positions
             (see _group_into_columns) - the shelf layout is read from the
             photo, not from a stored planogram layout.
          2. For each column, the MAJORITY product class in that column is
             treated as "what belongs here" (e.g. if a column has 5
             maggi_small and 1 blue_lays, maggi_small is the column's
             expected product for this photo).
          3. Any detection in a column that disagrees with that column's
             own majority product is flagged misplaced.

        This means misplaced-product detection works on ANY shelf
        arrangement the photo shows - it has no memory of a "correct"
        layout between photos, it only flags internal inconsistency
        WITHIN one photo (an item visually out of place among its
        neighbours).

        A column with only one item, or where every item agrees, produces
        no misplaced flags (a single item / a uniform column has nothing
        to disagree with).
        """
        columns = self._group_into_columns(raw_boxes)
        misplaced = []

        for col_index, column in enumerate(columns):
            if len(column) < 2:
                continue  # nothing to compare against in a single-item column

            counts: dict = {}
            for item in column:
                counts[item["product_class"]] = counts.get(item["product_class"], 0) + 1

            majority_product = max(counts.items(), key=lambda kv: kv[1])[0]

            for item in column:
                product_class = item["product_class"]
                if product_class != majority_product:
                    misplaced.append({
                        "detected_product": product_class,
                        "expected_product": majority_product,
                        "slot_number": col_index + 1,
                        "bbox": item["bbox"],
                        "message": (
                            f"{product_class} found among {majority_product} "
                            f"(column {col_index + 1})"
                        ),
                    })

        return misplaced
