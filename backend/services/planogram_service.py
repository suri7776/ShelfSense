# backend/services/planogram_service.py
#
# Planogram = ideal-stock targets + product physical dimensions + shelf
# dimensions. There are NO predefined shelf positions/slots anymore - which
# product is "supposed to be" where is now determined fresh from each
# uploaded photo (see detector.py's _detect_misplaced), not from a fixed
# layout stored here. This file is the single place expected_facings is
# read/written from, so every caller (detector.py, alerts.py, main.py)
# gets identical numbers - this used to be duplicated in three places,
# which was the source of the Add/Replace stock-count bug.

import json
import math

PLANOGRAM_PATH = "backend/config/planogram.json"

# Fixed ideal stock (expected_facings) per product class.
# These values are used on EVERY calibration call, regardless of what the
# uploaded calibration photo actually shows. The photo is still uploaded
# and still run through YOLOv8 (the calibration request/response shape is
# unchanged), but the counts it returns are not what gets written here.
FIXED_IDEAL_STOCK = {
    "thumps_up": 5,
    "marie_biscuit": 5,
    "wheel_bar": 8,
    "tata_salt": 4,
    "maggi_small": 7,
    "maggi_large": 4,
    "blue_lays": 5,
}


def get_planogram() -> dict:
    with open(PLANOGRAM_PATH) as f:
        return json.load(f)


def get_expected_facings() -> dict:
    """
    {product_class: ideal_stock_count}. The single source every other
    module should call instead of re-reading planogram.json itself.
    """
    planogram = get_planogram()
    return planogram.get("expected_facings", {})


def calibrate_from_counts(class_counts: dict) -> dict:
    """
    class_counts: {"maggi_small": 6, "blue_lays": 4, "empty_slot": 1, ...}
    (Still accepted as a parameter and still computed by the caller from
    real YOLOv8 detections on the uploaded photo - see main.py - so the
    calibration request/response shape is unchanged.)

    Writes FIXED_IDEAL_STOCK into planogram.json's expected_facings,
    regardless of what's in class_counts. Returns the updated planogram
    plus a list of what was set, for the frontend to display.
    """
    planogram = get_planogram()
    planogram["expected_facings"] = dict(FIXED_IDEAL_STOCK)

    with open(PLANOGRAM_PATH, "w") as f:
        json.dump(planogram, f, indent=2)

    updated = [
        {"product": product, "expected_facings": count}
        for product, count in FIXED_IDEAL_STOCK.items()
    ]
    return {"planogram": planogram, "updated_slots": updated}


def update_expected_facings(product_class: str, expected_facings: int) -> dict:
    """Manually set one product's ideal-stock target (Planogram page edit)."""
    planogram = get_planogram()
    planogram.setdefault("expected_facings", {})[product_class] = expected_facings

    with open(PLANOGRAM_PATH, "w") as f:
        json.dump(planogram, f, indent=2)

    return planogram


def update_shelf_depth(shelf_depth_cm: float) -> dict:
    planogram = get_planogram()
    planogram["shelf_depth_cm"] = shelf_depth_cm
    with open(PLANOGRAM_PATH, "w") as f:
        json.dump(planogram, f, indent=2)
    return planogram


def update_shelf_height(shelf_height_cm: float) -> dict:
    planogram = get_planogram()
    planogram["shelf_height_cm"] = shelf_height_cm
    with open(PLANOGRAM_PATH, "w") as f:
        json.dump(planogram, f, indent=2)
    return planogram


def update_shop_info(shop_name: str = None, location: str = None, camera_id: str = None) -> dict:
    planogram = get_planogram()
    if shop_name is not None:
        planogram["shop_name"] = shop_name
    if location is not None:
        planogram["location"] = location
    if camera_id is not None:
        planogram["camera_id"] = camera_id
    with open(PLANOGRAM_PATH, "w") as f:
        json.dump(planogram, f, indent=2)
    return planogram


def update_product_dimensions(product_class: str, width_cm: float, height_cm: float, depth_cm: float) -> dict:
    planogram = get_planogram()
    dims = planogram.setdefault("product_dimensions", {}).setdefault(product_class, {})
    dims["width_cm"] = width_cm
    dims["height_cm"] = height_cm
    dims["depth_cm"] = depth_cm
    with open(PLANOGRAM_PATH, "w") as f:
        json.dump(planogram, f, indent=2)
    return planogram
