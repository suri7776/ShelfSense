# backend/services/depth_counter.py
#
# Depth-based stock counting using a LiDAR depth map from Record3D.
#
# CORE FORMULA (replaces YOLOv8 facing count for total stock):
#
#   total = floor( (back_wall_cm - first_product_depth_cm) / product_depth_cm )
#
#   Where:
#     back_wall_cm          = distance from camera to back wall of shelf
#                             (auto-read from 99th percentile of depth map)
#     first_product_depth_cm = distance from camera to the FRONT FACE of the
#                             first visible product in this column
#                             (auto-read from depth map at bounding box centre)
#     product_depth_cm       = physical front-to-back dimension of the product
#                             (stored once in planogram.json product_dimensions)
#
#   YOLOv8 is used ONLY to:
#     1. Identify WHICH product class is in each column
#     2. Detect misplaced products (wrong product in a column)
#
#   MISPLACED CORRECTION:
#     If a column has misplaced products mixed in (e.g. 2 lays packets
#     among 6 maggies), the depth formula counts them all as one object type.
#     We subtract the misplaced count:
#
#       actual_total = depth_total - misplaced_count_in_this_column
#
#     Example: depth says 8 objects fit, 2 are detected as lays (misplaced),
#     so actual maggi = 8 - 2 = 6.
#
# DEPTH MAP FORMAT (auto-detected from numpy dtype):
#   uint16  → metric_mm  : pixel values are distances in millimetres
#   float32 → metric_m   : pixel values are distances in metres
#   uint8   → relative   : 0-255 relative only; uses planogram shelf_depth_cm
#                           as fallback range (less accurate)

import json
import numpy as np
from typing import Optional, Callable

PLANOGRAM_PATH = "backend/config/planogram.json"

# Bounding box aspect ratio threshold for "lying flat" maggi detection
LYING_FLAT_ASPECT = 1.3


def _load_planogram() -> dict:
    with open(PLANOGRAM_PATH) as f:
        return json.load(f)


# ─── DEPTH MAP LOADING AND FORMAT DETECTION ──────────────────────────────────

def load_depth_channel(depth_img: np.ndarray) -> np.ndarray:
    """Collapse RGB/RGBA depth map to single channel, preserving dtype."""
    if depth_img.ndim == 3:
        depth_img = depth_img[:, :, 0]
    return depth_img


def interpret_depth_map(depth_channel: np.ndarray, shelf_depth_cm_fallback: float) -> dict:
    """
    Auto-detect depth map format and return:
        {
          "mode":            "metric_mm" | "metric_m" | "relative_8bit",
          "front_border_cm": float,   # camera to closest point in scene
          "back_wall_cm":    float,   # camera to farthest point (shelf back)
          "to_cm":           callable(raw_value) -> float,
        }

    mode "metric_mm"  (uint16): pixel = mm   → divide by 10 for cm
    mode "metric_m"   (float32): pixel = m    → multiply by 100 for cm
    mode "relative_8bit" (uint8): no metric scale → use shelf_depth_cm_fallback
    """
    nonzero = depth_channel[depth_channel > 0]
    if nonzero.size == 0:
        return {
            "mode": "empty_depth_map",
            "front_border_cm": 0.0,
            "back_wall_cm": shelf_depth_cm_fallback,
            "to_cm": lambda v: 0.0,
        }

    dtype = depth_channel.dtype

    if dtype == np.uint8:
        # Relative only — map observed range onto [0, shelf_depth_cm_fallback]
        v_min = float(np.percentile(nonzero, 1))
        v_max = float(np.percentile(nonzero, 99))
        span = max(v_max - v_min, 1e-6)

        def to_cm_rel(v, _min=v_min, _span=span, _scale=shelf_depth_cm_fallback):
            return min(max((float(v) - _min) / _span, 0.0), 1.0) * _scale

        return {
            "mode": "relative_8bit",
            "front_border_cm": 0.0,
            "back_wall_cm": shelf_depth_cm_fallback,
            "to_cm": to_cm_rel,
        }

    v_min = float(np.percentile(nonzero, 1))
    v_max = float(np.percentile(nonzero, 99))

    if np.issubdtype(dtype, np.floating):
        # float32 metres (ARKit/Record3D convention)
        to_cm_fn: Callable = lambda v: float(v) * 100.0
        mode = "metric_m"
    else:
        # uint16 millimetres (standard LiDAR PNG export)
        to_cm_fn = lambda v: float(v) / 10.0
        mode = "metric_mm"

    return {
        "mode": mode,
        "front_border_cm": to_cm_fn(v_min),
        "back_wall_cm": to_cm_fn(v_max),
        "to_cm": to_cm_fn,
    }


def bbox_center_raw_value(
    depth_channel: np.ndarray,
    bbox: list,
    bbox_source_size: tuple,
    depth_size: tuple,
) -> float:
    """
    Read the raw depth value at the centre of a bounding box.
    Pass through depth_info["to_cm"] to convert to centimetres.
    """
    x1, y1, x2, y2 = bbox
    src_w, src_h = bbox_source_size
    depth_w, depth_h = depth_size

    cx = int(np.clip((x1 + x2) / 2 / src_w * depth_w, 0, depth_w - 1))
    cy = int(np.clip((y1 + y2) / 2 / src_h * depth_h, 0, depth_h - 1))

    return float(depth_channel[cy, cx])


# ─── CORE COUNTING FORMULA ───────────────────────────────────────────────────

def classify_maggi_orientation(bbox: list) -> str:
    """Upright or lying flat, based on bounding box aspect ratio."""
    x1, y1, x2, y2 = bbox
    h = y2 - y1
    if h <= 0:
        return "upright"
    return "lying_flat" if (x2 - x1) / h > LYING_FLAT_ASPECT else "upright"


def depth_count_column(
    product_class: str,
    first_product_depth_cm: float,
    back_wall_cm: float,
    shelf_height_cm: float,
    bbox: list,
    misplaced_count_in_column: int = 0,
) -> dict:
    """
    Compute total stock in one shelf column using the depth formula.

    Parameters
    ----------
    product_class           : detected product class for this column
    first_product_depth_cm  : camera → front face of first visible product
                              (read from depth map at bbox centre)
    back_wall_cm            : camera → shelf back wall
                              (from 99th percentile of depth map)
    shelf_height_cm         : top-to-bottom shelf height (from planogram)
    bbox                    : [x1,y1,x2,y2] in 640×640 detection space
    misplaced_count_in_column: number of misplaced products detected in
                              this column (subtracted from depth total)

    Returns
    -------
    dict with:
        depth_total   - what depth formula gives (no misplaced correction)
        actual_total  - depth_total - misplaced_count_in_column
        formula       - human-readable string showing the calculation
        orientation   - "upright" or "lying_flat" (maggi only)
        product_depth_cm - physical depth used in formula
    """
    planogram = _load_planogram()
    dims = planogram.get("product_dimensions", {}).get(product_class, {})

    product_depth_cm = dims.get("depth_cm", 0)
    width_cm         = dims.get("width_cm", 0)
    depth_cm_lying   = dims.get("depth_cm", 0)  # used as top-to-bottom when lying flat

    available_depth = max(0.0, back_wall_cm - first_product_depth_cm)

    # ── Maggi packets: check if lying flat ───────────────────────────────────
    if product_class in ("maggi_small", "maggi_large"):
        orientation = classify_maggi_orientation(bbox)

        if orientation == "lying_flat" and width_cm > 0 and depth_cm_lying > 0:
            # Lying flat: depth axis = width_cm, height axis = depth_cm
            front_to_back = max(1, int(available_depth / width_cm))
            top_to_bottom = max(1, int(shelf_height_cm / depth_cm_lying))
            depth_total   = front_to_back * top_to_bottom
            actual_total  = max(0, depth_total - misplaced_count_in_column)

            return {
                "product_class":      product_class,
                "orientation":        "lying_flat",
                "product_depth_cm":   width_cm,
                "first_product_depth_cm": round(first_product_depth_cm, 1),
                "back_wall_cm":       round(back_wall_cm, 1),
                "available_depth_cm": round(available_depth, 1),
                "front_to_back":      front_to_back,
                "top_to_bottom":      top_to_bottom,
                "depth_total":        depth_total,
                "misplaced_in_column": misplaced_count_in_column,
                "actual_total":       actual_total,
                "formula": (
                    f"floor({available_depth:.1f}cm ÷ {width_cm}cm) × "
                    f"floor({shelf_height_cm}cm ÷ {depth_cm_lying}cm) = "
                    f"{front_to_back} × {top_to_bottom} = {depth_total} "
                    f"- {misplaced_count_in_column} misplaced = {actual_total}"
                ),
            }

        orientation = "upright"

    else:
        orientation = "upright"

    # ── Standard upright formula ─────────────────────────────────────────────
    if product_depth_cm <= 0:
        return {
            "product_class":  product_class,
            "orientation":    orientation,
            "depth_total":    0,
            "actual_total":   0,
            "formula":        "missing product_depth_cm in planogram",
            "error":          "Set product depth in Planogram → Product Dimensions",
        }

    depth_total  = max(1, int(available_depth / product_depth_cm))
    actual_total = max(0, depth_total - misplaced_count_in_column)

    return {
        "product_class":           product_class,
        "orientation":             orientation,
        "product_depth_cm":        product_depth_cm,
        "first_product_depth_cm":  round(first_product_depth_cm, 1),
        "back_wall_cm":            round(back_wall_cm, 1),
        "available_depth_cm":      round(available_depth, 1),
        "depth_total":             depth_total,
        "misplaced_in_column":     misplaced_count_in_column,
        "actual_total":            actual_total,
        "formula": (
            f"floor(({back_wall_cm:.1f} - {first_product_depth_cm:.1f})cm "
            f"÷ {product_depth_cm}cm) = {depth_total} "
            f"- {misplaced_count_in_column} misplaced = {actual_total}"
        ),
    }
