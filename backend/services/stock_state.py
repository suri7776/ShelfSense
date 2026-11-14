# backend/services/stock_state.py
#
# "Current stock" snapshot - a single dict of {product_class: facings_count}
# stored in backend/data/current_stock.json.
#
# WHY THIS EXISTS:
# Earlier, the Dashboard read "the most recent ShelfState row per product".
# That breaks down once you're uploading multiple photos/videos that each
# cover only PART of the shelf - the last upload would silently overwrite
# the count for products it didn't even see (because their old rows just
# stop being "latest" for nothing - they're still latest, but a new batch
# that covers different products doesn't update them either, so stale data
# and fresh data get mixed with no way to reason about it).
#
# Instead, current_stock.json is THE current snapshot, updated explicitly
# by one of three operations:
#
#   replace_detected (default for a single Live Shelf photo):
#       For each product seen in this detection, SET its count to what was
#       seen. Products not in this photo are left untouched. Good for "I
#       photographed one section of the shelf."
#
#   add (batch upload, mode="add"):
#       ADD this batch's counts on top of the existing snapshot, per
#       product. Use when uploading several photos that together cover the
#       WHOLE shelf in separate, non-overlapping sections, and you want the
#       totals to combine with whatever was already recorded.
#
#   replace_all (batch upload, mode="replace"):
#       Treat this batch as a FRESH FULL SCAN. Every product's count is
#       reset, then set from this batch (0 if a product wasn't seen at
#       all). Use after restocking, when old counts are no longer relevant.

import json
import os

CURRENT_STOCK_PATH = "backend/data/current_stock.json"
PLANOGRAM_PATH = "backend/config/planogram.json"


def _load_planogram_products() -> list:
    with open(PLANOGRAM_PATH) as f:
        planogram = json.load(f)
    return [
        p for p in planogram.get("product_dimensions", {}).keys()
        if p != "empty_slot"
    ]


def get_current_stock() -> dict:
    """
    Return {product_class: count}, guaranteed to have an entry for every
    product in the planogram (defaulting to 0 if never recorded).
    """
    os.makedirs(os.path.dirname(CURRENT_STOCK_PATH), exist_ok=True)

    if os.path.exists(CURRENT_STOCK_PATH):
        with open(CURRENT_STOCK_PATH) as f:
            stock = json.load(f)
    else:
        stock = {}

    for product in _load_planogram_products():
        stock.setdefault(product, 0)

    return stock


def _save(stock: dict):
    os.makedirs(os.path.dirname(CURRENT_STOCK_PATH), exist_ok=True)
    with open(CURRENT_STOCK_PATH, "w") as f:
        json.dump(stock, f, indent=2)


def update_stock(class_counts: dict, mode: str = "replace_detected") -> dict:
    """
    Update the current-stock snapshot. See module docstring for `mode`
    semantics. `class_counts` should exclude "empty_slot" - callers should
    filter it out before calling.

    Returns the updated snapshot.
    """
    counts = {k: v for k, v in class_counts.items() if k != "empty_slot"}

    if mode == "replace_detected":
        stock = get_current_stock()
        for product, count in counts.items():
            stock[product] = count

    elif mode == "add":
        stock = get_current_stock()
        for product, count in counts.items():
            stock[product] = stock.get(product, 0) + count

    elif mode == "replace_all":
        # Deliberately does NOT start from get_current_stock() - this mode
        # means "throw away everything old, this batch is the new truth."
        # Starting from a fresh {} (rather than the existing snapshot)
        # guarantees no stale value from a previous scan can survive,
        # even for a product this batch didn't detect at all (those get
        # explicitly set to 0 below, not left at their old value).
        stock = {product: 0 for product in _load_planogram_products()}
        for product, count in counts.items():
            stock[product] = count

    else:
        raise ValueError(f"Unknown mode: {mode}")

    print(f"[stock_state.update_stock] mode={mode!r} incoming_counts={counts} -> snapshot={stock}")

    _save(stock)
    return stock


def reset_stock():
    """Zero out everything - useful for a clean demo restart."""
    stock = {p: 0 for p in _load_planogram_products()}
    _save(stock)
    return stock
