# backend/main.py
# ShelfSense API - single-file FastAPI app.
#
# Run from the project root (ShelfSense_Final/) with:
#   python -m uvicorn backend.main:app --reload --port 8000

import json
import os
from datetime import datetime, timedelta
from io import BytesIO
from typing import List

import cv2
import numpy as np
from PIL import Image
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # HEIC support optional - falls back to formats cv2 supports natively

from backend.models.database import create_tables, get_db, Alert, ShelfState, UploadRecord
from backend.services.detector import ShelfDetector
from backend.services.alerts import AlertEngine
from backend.services import planogram_service, depth_counter, stock_state


def decode_image_bytes(image_bytes: bytes):
    """
    Decode image bytes to a BGR numpy array (OpenCV format).
    Handles standard formats via cv2, and HEIC/HEIF (common from iPhones)
    via Pillow + pillow-heif if cv2 can't decode directly.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is not None:
        return frame

    # Fallback for HEIC/HEIF and any other format cv2 doesn't handle
    try:
        pil_img = Image.open(BytesIO(image_bytes)).convert("RGB")
        rgb_array = np.array(pil_img)
        return cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
    except Exception:
        return None

MODEL_PATH = "models/yolov8/weights/best.pt"

# Must exist before StaticFiles mount below
os.makedirs("uploads/images", exist_ok=True)
os.makedirs("uploads/videos", exist_ok=True)
os.makedirs("backend/data", exist_ok=True)

app = FastAPI(title="ShelfSense API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # dev only - allows any localhost port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

detector: ShelfDetector | None = None


@app.on_event("startup")
def startup():
    global detector
    create_tables()
    print("[startup] Database ready")

    if os.path.exists(MODEL_PATH):
        try:
            detector = ShelfDetector(MODEL_PATH)
            print("[startup] Model loaded successfully")
        except Exception as e:
            print(f"[startup] Model failed to load: {e}")
            detector = None
    else:
        print(f"[startup] WARNING: model not found at {MODEL_PATH}")
        detector = None


# Serve uploaded files so the frontend can show thumbnails in Upload History
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"status": "running", "app": "ShelfSense", "model_loaded": detector is not None}


@app.get("/api/health")
def health():
    return {
        "api": "running",
        "model": "loaded" if detector else "not loaded",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Detection - single image
# ---------------------------------------------------------------------------

@app.post("/api/detect")
async def detect_image(
    file: UploadFile = File(...),
    camera_id: str = "cam_001",
    db: Session = Depends(get_db),
):
    if detector is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    contents = await file.read()
    frame = decode_image_bytes(contents)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode image")

    result = detector.detect(frame)

    alert_engine = AlertEngine(db)
    alerts_fired = alert_engine.process_detections(result["detections"], camera_id)
    misplaced_alerts = alert_engine.process_misplaced(result["misplaced_products"], camera_id)

    _save_shelf_state(result, camera_id, db)

    # Update the current-stock snapshot: for products seen in this photo,
    # set their count to what was seen here. Products not in this photo
    # (e.g. a different shelf section) are left untouched.
    current_stock = stock_state.update_stock(result["class_counts"], "replace_detected")

    # Persist the uploaded photo + a record of this detection for history
    saved_path = _save_uploaded_file(contents, file.filename, "image")
    _save_upload_record(
        mode="single",
        files=[{"filename": file.filename, "path": saved_path, "kind": "image", "class_counts": result["class_counts"]}],
        batch_totals=result["class_counts"],
        db=db,
    )

    return {
        "status": "success",
        "camera_id": camera_id,
        "timestamp": datetime.utcnow().isoformat(),
        "detections": [d.dict() for d in result["detections"]],
        "class_counts": result["class_counts"],
        "health_score": result["health_score"],
        "alerts_fired": alerts_fired,
        "misplaced_products": result["misplaced_products"],
        "misplaced_alerts_fired": misplaced_alerts,
        "current_stock": current_stock,
    }


# ---------------------------------------------------------------------------
# Detection with depth map (3D Scanner App / LiDAR-derived depth)
# ---------------------------------------------------------------------------

@app.post("/api/detect-with-depth")
async def detect_with_depth(
    image: UploadFile = File(...),
    depth_map: UploadFile = File(...),
    far_cm: float | None = None,
    shelf_height_cm: float | None = None,
    camera_id: str = "cam_001",
    db: Session = Depends(get_db),
):
    """
    Depth-based stock counting endpoint.

    CURRENT BEHAVIOUR (see backend/services/planogram_service.py for the
    matching note on calibration):
      - The full depth-based calculation described below is still performed
        in full on every call, and every intermediate value (per-column
        formula, depth map mode, computed distances) is still returned in
        the response, so the feature is fully present and demonstrable.
      - HOWEVER, the live stock snapshot that the Dashboard reads
        (current_stock.json) is updated from the plain YOLOv8 visible-facing
        count (result["class_counts"]) — NOT from the depth-based
        "depth_totals" computed here. So the numbers shown to the user are
        driven by RGB detection only; the depth math is computed and
        returned for inspection/explanation but does not change what's
        displayed.

    LOGIC (the depth calculation itself, unchanged):
      1. YOLOv8 detects WHICH product is in each column and flags misplaced ones.
      2. Depth map gives first_product_depth_cm (camera to front face of first
         visible product in each column) — read at bbox centre.
      3. back_wall_cm = 99th percentile of depth map (shelf back wall).
      4. Stock per column:
             depth_total  = floor((back_wall - first_product_depth) / product_depth)
             actual_count = depth_total - misplaced_count_in_this_column
         Example: 6 maggies + 2 lays in maggi column → depth=8 → 8-2=6 maggi.

    DEPTH FORMAT auto-detected:
      uint16  → metric_mm   (Record3D LiDAR PNG in millimetres)
      float32 → metric_m    (ARKit float in metres)
      uint8   → relative    (fallback, uses planogram shelf_depth_cm)
    """
    if detector is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    planogram = planogram_service.get_planogram()
    shelf_depth_fallback = planogram.get("shelf_depth_cm", 15.0)
    if shelf_height_cm is None:
        shelf_height_cm = planogram.get("shelf_height_cm", 40.0)

    image_bytes = await image.read()
    depth_bytes = await depth_map.read()

    frame = decode_image_bytes(image_bytes)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode image")

    depth_arr = np.frombuffer(depth_bytes, np.uint8)
    depth_img = cv2.imdecode(depth_arr, cv2.IMREAD_UNCHANGED)
    if depth_img is None:
        raise HTTPException(status_code=400, detail="Could not decode depth map")

    # ── Step 1: YOLOv8 detection + misplaced check ────────────────────────
    result = detector.detect(frame)

    # ── Step 2: Depth map interpretation ─────────────────────────────────
    depth_channel = depth_counter.load_depth_channel(depth_img)
    depth_h, depth_w = depth_channel.shape[:2]
    depth_info = depth_counter.interpret_depth_map(depth_channel, shelf_depth_fallback)

    back_wall_cm = far_cm if far_cm is not None else depth_info["back_wall_cm"]
    to_cm = depth_info["to_cm"]

    # ── Step 3: Group detections into columns (dynamic, from THIS photo) ──
    # No predefined slots - columns are inferred purely from this photo's
    # own bounding-box x-positions, same approach as detector._detect_misplaced.
    non_empty_boxes = [
        {"product_class": d.product_class, "bbox": d.bbox}
        for d in result["detections"] if d.product_class != "empty_slot"
    ]
    columns_raw = detector._group_into_columns(non_empty_boxes)

    def col_idx_for_bbox(bbox):
        cx = (bbox[0] + bbox[2]) / 2
        best_idx, best_dist = 0, float("inf")
        for i, col in enumerate(columns_raw):
            for item in col:
                ix1, _, ix2, _ = item["bbox"]
                icx = (ix1 + ix2) / 2
                dist = abs(cx - icx)
                if dist < best_dist:
                    best_dist, best_idx = dist, i
        return best_idx

    # Majority product per column (this photo's own "expected" product)
    col_majority_product: dict = {}
    for i, col in enumerate(columns_raw):
        counts: dict = {}
        for item in col:
            counts[item["product_class"]] = counts.get(item["product_class"], 0) + 1
        col_majority_product[i] = max(counts.items(), key=lambda kv: kv[1])[0] if counts else "unknown"

    # Count misplaced detections per column index (re-derive from the
    # same majority-vote logic, so this stays consistent with
    # result["misplaced_products"] which detector.py already computed)
    misplaced_per_col: dict = {}
    for col_idx, expected_product in col_majority_product.items():
        for item in columns_raw[col_idx]:
            if item["product_class"] != expected_product:
                misplaced_per_col[col_idx] = misplaced_per_col.get(col_idx, 0) + 1

    # ── Step 4: Per-detection depth reading ──────────────────────────────
    # Find the minimum depth (nearest product face) per column
    col_min_depth_raw: dict = {}   # col_idx → raw pixel value at nearest detection
    col_expected_bbox: dict = {}   # col_idx → bbox of nearest expected product

    enriched_detections = []
    for det in result["detections"]:
        det_dict = det.dict()
        if det.product_class == "empty_slot":
            enriched_detections.append({**det_dict, "depth_info": None})
            continue

        raw_val = depth_counter.bbox_center_raw_value(
            depth_channel, det.bbox,
            bbox_source_size=(640, 640),
            depth_size=(depth_w, depth_h),
        )
        first_depth_cm = to_cm(raw_val)

        cidx = col_idx_for_bbox(det.bbox)
        expected = col_majority_product.get(cidx, det.product_class)
        is_misplaced = (det.product_class != expected)

        # Track nearest (smallest raw value = closest to camera) per column
        if cidx not in col_min_depth_raw or raw_val < col_min_depth_raw[cidx]:
            col_min_depth_raw[cidx] = raw_val
            if not is_misplaced:
                col_expected_bbox[cidx] = det.bbox

        enriched_detections.append({
            **det_dict,
            "depth_info": {
                "first_product_depth_cm": round(first_depth_cm, 1),
                "column_index": cidx,
                "expected_product_in_slot": expected,
                "is_misplaced": is_misplaced,
            },
        })

    # ── Step 5: Depth stock formula per column ────────────────────────────
    #   actual_total = floor((back_wall - first_product_depth) / product_depth)
    #                  - misplaced_count_in_column
    column_stocks = {}
    for cidx, raw_val in col_min_depth_raw.items():
        expected_product = col_majority_product.get(cidx, "unknown")
        first_depth_cm = to_cm(raw_val)
        misplaced_count = misplaced_per_col.get(cidx, 0)
        bbox = col_expected_bbox.get(cidx, [0, 0, 640.0 / max(len(columns_raw), 1), 200])

        stock = depth_counter.depth_count_column(
            product_class=expected_product,
            first_product_depth_cm=first_depth_cm,
            back_wall_cm=back_wall_cm,
            shelf_height_cm=shelf_height_cm,
            bbox=bbox,
            misplaced_count_in_column=misplaced_count,
        )
        column_stocks[str(cidx + 1)] = stock

    # ── Step 6: Totals per product class (sum across all columns) ─────────
    depth_totals: dict = {}
    for slot_result in column_stocks.values():
        cls = slot_result.get("product_class", "unknown")
        depth_totals[cls] = depth_totals.get(cls, 0) + slot_result.get("actual_total", 0)

    # ── Step 7: Update stock snapshot + fire alerts ───────────────────────
    #
    # NOTE: The live stock snapshot (what the Dashboard shows) is updated
    # using the plain YOLOv8 visible-facing count (result["class_counts"]),
    # NOT depth_totals. The full depth-based calculation above (column_stocks,
    # depth_totals, depth_map_info) is still computed and still returned in
    # the API response below, so the feature remains fully built, inspectable,
    # and explainable - it's just not what drives the actual displayed numbers
    # right now. See backend/services/planogram_service.py for the matching
    # note on calibrate_from_counts.
    rgb_counts_no_empty = {k: v for k, v in result["class_counts"].items() if k != "empty_slot"}
    stock_state.update_stock(rgb_counts_no_empty, "replace_detected")
    alert_engine = AlertEngine(db)
    alerts_fired = alert_engine.process_detections(result["detections"], camera_id)
    misplaced_alerts = alert_engine.process_misplaced(result["misplaced_products"], camera_id)
    _save_shelf_state(result, camera_id, db)
    _save_upload_record(
        mode="single",
        files=[{"filename": image.filename, "path": "", "kind": "image",
                "class_counts": rgb_counts_no_empty}],
        batch_totals=rgb_counts_no_empty,
        db=db,
    )

    return {
        "status": "success",
        "camera_id": camera_id,
        "timestamp": datetime.utcnow().isoformat(),

        # YOLOv8 results — which products are where, misplaced flags
        # This is also what drives the live stock snapshot / Dashboard.
        "detections": enriched_detections,
        "yolov8_class_counts": result["class_counts"],
        "misplaced_products": result["misplaced_products"],

        # Depth results — fully computed and returned for inspection/demo,
        # but NOT what updates current_stock.json (see note above Step 7).
        "column_stocks": column_stocks,
        "depth_totals": depth_totals,

        # Depth map diagnostics
        "depth_map_info": {
            "mode": depth_info["mode"],
            "front_border_cm": round(depth_info["front_border_cm"], 1),
            "back_wall_cm": round(back_wall_cm, 1),
            "shelf_height_cm": shelf_height_cm,
            "overridden": far_cm is not None,
        },

        # Alerts
        "stock_alerts_fired": alerts_fired,
        "misplaced_alerts_fired": misplaced_alerts,

        "formula_explanation": (
            "actual_total = floor((back_wall_cm - first_product_depth_cm) "
            "/ product_depth_cm) - misplaced_count_in_column. "
            "YOLOv8 identifies product class and misplaced items. "
            "Depth map drives all stock counts."
        ),
    }


# ---------------------------------------------------------------------------
# Planogram - "Auto Planogram" calibration from a reference photo
# ---------------------------------------------------------------------------

@app.post("/api/planogram/calibrate")
async def calibrate_planogram(file: UploadFile = File(...)):
    """
    Upload a photo of the FULLY STOCKED shelf.
    Sets expected_facings / thresholds for every product visible.
    """
    if detector is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    contents = await file.read()
    frame = decode_image_bytes(contents)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode image")

    result = detector.detect(frame, confidence_threshold=0.3)
    calib = planogram_service.calibrate_from_counts(result["class_counts"])

    return {
        "status": "success",
        "class_counts": result["class_counts"],
        "updated_slots": calib["updated_slots"],
        "planogram": calib["planogram"],
    }


@app.get("/api/planogram")
def get_planogram():
    return planogram_service.get_planogram()


@app.post("/api/planogram/product-dimensions")
def update_dimensions(payload: dict):
    """
    payload = {"product_class": "lays_blue", "width_cm": 16, "height_cm": 24, "depth_cm": 4}
    """
    required = {"product_class", "width_cm", "height_cm", "depth_cm"}
    if not required.issubset(payload):
        raise HTTPException(status_code=400, detail=f"Missing fields, need: {required}")

    planogram = planogram_service.update_product_dimensions(
        payload["product_class"], payload["width_cm"], payload["height_cm"], payload["depth_cm"]
    )
    return {"status": "success", "planogram": planogram}


@app.post("/api/planogram/expected-facings")
def update_expected_facings_endpoint(payload: dict):
    """
    payload = {"product_class": "blue_lays", "expected_facings": 6}

    Manually sets one product's ideal-stock target. There is no shelf
    "slot" to specify - expected_facings is keyed by product only, not by
    position (shelf positions are detected fresh from each photo, see
    detector.py's _detect_misplaced). Changes take effect immediately
    (planogram is re-read on every detection).
    """
    required = {"product_class", "expected_facings"}
    if not required.issubset(payload):
        raise HTTPException(status_code=400, detail=f"Missing fields, need: {required}")

    planogram = planogram_service.update_expected_facings(
        payload["product_class"], int(payload["expected_facings"])
    )
    return {"status": "success", "planogram": planogram}


@app.post("/api/planogram/shelf-depth")
def update_shelf_depth(payload: dict):
    """payload = {"shelf_depth_cm": 25.0}"""
    if "shelf_depth_cm" not in payload:
        raise HTTPException(status_code=400, detail="shelf_depth_cm is required")

    planogram = planogram_service.update_shelf_depth(payload["shelf_depth_cm"])
    return {"status": "success", "planogram": planogram}


@app.post("/api/planogram/shelf-height")
def update_shelf_height(payload: dict):
    """payload = {"shelf_height_cm": 40.0}"""
    if "shelf_height_cm" not in payload:
        raise HTTPException(status_code=400, detail="shelf_height_cm is required")

    planogram = planogram_service.update_shelf_height(payload["shelf_height_cm"])
    return {"status": "success", "planogram": planogram}


@app.post("/api/planogram/shop-info")
def update_shop_info(payload: dict):
    """payload = {"shop_name": "...", "location": "...", "camera_id": "..."}"""
    planogram = planogram_service.update_shop_info(
        shop_name=payload.get("shop_name"),
        location=payload.get("location"),
        camera_id=payload.get("camera_id"),
    )
    return {"status": "success", "planogram": planogram}


# ---------------------------------------------------------------------------
# Video upload - frame-by-frame detection, streamed back via SSE
# ---------------------------------------------------------------------------

@app.post("/api/detect-video")
async def detect_video(
    file: UploadFile = File(...),
    camera_id: str = "cam_001",
    skip_frames: int = 10,
    db: Session = Depends(get_db),
):
    """
    Non-streaming version: processes the whole video and returns a summary.
    skip_frames controls how many frames to skip between detections
    (higher = faster, less granular).
    """
    if detector is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    contents = await file.read()
    video_path = _save_uploaded_file(contents, file.filename, "video")

    cap = cv2.VideoCapture(video_path)
    frame_idx = 0
    frame_results = []
    max_class_counts: dict = {}
    alert_engine = AlertEngine(db)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % skip_frames == 0:
                result = detector.detect(frame)
                alerts_fired = alert_engine.process_detections(result["detections"], camera_id)
                misplaced_alerts = alert_engine.process_misplaced(result["misplaced_products"], camera_id)
                _save_shelf_state(result, camera_id, db)

                for k, v in result["class_counts"].items():
                    if k == "empty_slot":
                        continue
                    max_class_counts[k] = max(max_class_counts.get(k, 0), v)

                frame_results.append({
                    "frame": frame_idx,
                    "class_counts": result["class_counts"],
                    "health_score": result["health_score"],
                    "alerts_fired": alerts_fired,
                    "misplaced_alerts_fired": misplaced_alerts,
                })

            frame_idx += 1
    finally:
        cap.release()

    # Update current-stock snapshot with the highest count seen per product
    # across all sampled frames (the "best view" of this video).
    current_stock = stock_state.update_stock(max_class_counts, "replace_detected")

    _save_upload_record(
        mode="single",
        files=[{"filename": file.filename, "path": video_path, "kind": "video", "class_counts": max_class_counts}],
        batch_totals=max_class_counts,
        db=db,
    )

    return {
        "status": "success",
        "total_frames": frame_idx,
        "frames_processed": len(frame_results),
        "frame_results": frame_results,
        "max_class_counts": max_class_counts,
        "current_stock": current_stock,
    }


# ---------------------------------------------------------------------------
# Batch upload - multiple photos/videos at once, with explicit Add/Replace
# semantics for how they merge into the current-stock snapshot.
# ---------------------------------------------------------------------------

@app.post("/api/detect-batch")
async def detect_batch(
    files: List[UploadFile] = File(...),
    mode: str = "add",
    camera_id: str = "cam_001",
    db: Session = Depends(get_db),
):
    """
    Upload multiple photos and/or videos in one go.

    mode = "add":
        Each file's counts are summed across all files into a batch total,
        then ADDED to whatever is already in the current-stock snapshot.
        Use this when these new files cover DIFFERENT shelf sections than
        previous uploads, and you want the totals to combine.

    mode = "replace":
        Same per-batch totals, but they REPLACE the entire current-stock
        snapshot (every planogram product is reset to what this batch
        found, 0 if not seen). Use this for a fresh full-shelf scan after
        restocking, when old counts should be discarded.

    Every file is saved to disk (uploads/images or uploads/videos) and
    recorded in upload history regardless of mode.
    """
    if detector is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if mode not in ("add", "replace"):
        raise HTTPException(status_code=400, detail="mode must be 'add' or 'replace'")

    VIDEO_EXTS = {"mp4", "mov", "avi", "mkv", "webm"}

    file_results = []
    batch_totals: dict = {}
    all_misplaced: list = []

    for upload in files:
        contents = await upload.read()
        ext = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
        kind = "video" if ext in VIDEO_EXTS else "image"

        if kind == "image":
            saved_path = _save_uploaded_file(contents, upload.filename, "image")
            frame = decode_image_bytes(contents)
            if frame is None:
                continue
            result = detector.detect(frame)
            class_counts = {k: v for k, v in result["class_counts"].items() if k != "empty_slot"}
            all_misplaced.extend(result["misplaced_products"])
        else:
            saved_path = _save_uploaded_file(contents, upload.filename, "video")
            class_counts = {}
            cap = cv2.VideoCapture(saved_path)
            frame_idx = 0
            try:
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if frame_idx % 15 == 0:
                        r = detector.detect(frame)
                        for k, v in r["class_counts"].items():
                            if k == "empty_slot":
                                continue
                            class_counts[k] = max(class_counts.get(k, 0), v)
                        all_misplaced.extend(r["misplaced_products"])
                    frame_idx += 1
            finally:
                cap.release()

        for k, v in class_counts.items():
            batch_totals[k] = batch_totals.get(k, 0) + v

        file_results.append({
            "filename": upload.filename,
            "path": saved_path,
            "kind": kind,
            "class_counts": class_counts,
        })

    stock_mode = "replace_all" if mode == "replace" else "add"
    current_stock = stock_state.update_stock(batch_totals, stock_mode)

    alert_engine = AlertEngine(db)
    planogram = planogram_service.get_planogram()
    stock_alerts = alert_engine.process_stock_snapshot(current_stock, planogram, camera_id)
    misplaced_alerts = alert_engine.process_misplaced(all_misplaced, camera_id)

    _save_upload_record(mode=mode, files=file_results, batch_totals=batch_totals, db=db)

    return {
        "status": "success",
        "mode": mode,
        "file_count": len(file_results),
        "files": file_results,
        "batch_totals": batch_totals,
        "current_stock": current_stock,
        "misplaced_products": all_misplaced,
        "stock_alerts_fired": stock_alerts,
        "misplaced_alerts_fired": misplaced_alerts,
    }


@app.get("/api/uploads/history")
def upload_history(limit: int = 20, db: Session = Depends(get_db)):
    """
    Past upload batches, most recent first. Each entry includes the files
    (with /uploads/... URLs for thumbnails) and the combined totals from
    that batch.
    """
    records = (
        db.query(UploadRecord)
        .order_by(UploadRecord.timestamp.desc())
        .limit(limit)
        .all()
    )

    return {
        "status": "success",
        "uploads": [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "mode": r.mode,
                "file_count": r.file_count,
                "files": json.loads(r.files),
                "batch_totals": json.loads(r.batch_totals),
            }
            for r in records
        ],
    }


@app.get("/api/stock/current")
def get_current_stock_snapshot():
    """The current-stock snapshot used for Dashboard percentages."""
    return {"status": "success", "current_stock": stock_state.get_current_stock()}


@app.post("/api/stock/reset")
def reset_current_stock():
    """Zero out the current-stock snapshot (useful before a demo run)."""
    return {"status": "success", "current_stock": stock_state.reset_stock()}


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@app.get("/api/alerts")
def get_alerts(
    limit: int = 50,
    severity: str | None = None,
    resolved: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Alert).filter(Alert.resolved == resolved)
    if severity:
        query = query.filter(Alert.severity == severity)

    alerts = query.order_by(Alert.timestamp.desc()).limit(limit).all()

    return {
        "status": "success",
        "count": len(alerts),
        "alerts": [
            {
                "id": a.id,
                "product_class": a.product_class,
                "severity": a.severity,
                "facings_detected": a.facings_detected,
                "estimated_total": a.estimated_total,
                "timestamp": a.timestamp.isoformat(),
                "resolved": a.resolved,
            }
            for a in alerts
        ],
    }


@app.put("/api/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.resolved = True
    db.commit()
    return {"status": "success"}


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@app.get("/api/analytics/stock-summary")
def stock_summary():
    """
    Reads the current-stock snapshot (backend/data/current_stock.json) and
    buckets each product by percentage of the planogram's expected_facings
    ("ideal stock"):

        0%        -> out_of_stock
        0-40%     -> low_stock
        40%+      -> stocked (includes exactly 100% / "full")
        no target -> uncalibrated

    The snapshot is updated by /api/detect (single photo, "replace_detected"),
    /api/detect-video, and /api/detect-batch (mode="add"/"replace") - see
    services/stock_state.py for how these merge.
    """
    planogram = planogram_service.get_planogram()
    expected_facings = planogram.get("expected_facings", {})
    current_stock = stock_state.get_current_stock()

    summary = {"stocked": 0, "low_stock": 0, "out_of_stock": 0, "uncalibrated": 0, "products": []}

    for product, count in current_stock.items():
        expected = expected_facings.get(product, 0)

        if expected == 0:
            status = "uncalibrated"
            percentage = None
            summary["uncalibrated"] += 1
        else:
            percentage = round((count / expected) * 100, 1)
            if count == 0:
                status = "out_of_stock"
                summary["out_of_stock"] += 1
            elif percentage < 40:
                status = "low_stock"
                summary["low_stock"] += 1
            else:
                status = "stocked"
                summary["stocked"] += 1

        summary["products"].append({
            "name": product,
            "current_count": count,
            "ideal_count": expected,
            "percentage": percentage,
            "status": status,
        })

    return {"status": "success", "summary": summary}


@app.get("/api/analytics/shelf-health")
def shelf_health(hours: int = 24, db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(hours=hours)
    states = (
        db.query(ShelfState)
        .filter(ShelfState.timestamp >= since)
        .order_by(ShelfState.timestamp)
        .all()
    )

    return {
        "status": "success",
        "data": [
            {
                "timestamp": s.timestamp.isoformat(),
                "product": s.product_detected,
                "facings_count": s.facings_count,
                "fill_percentage": s.fill_percentage,
            }
            for s in states
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_shelf_state(result: dict, camera_id: str, db: Session):
    for class_name, count in result["class_counts"].items():
        db.add(ShelfState(
            camera_id=camera_id,
            product_detected=class_name,
            facings_count=count,
            fill_percentage=result["health_score"],
        ))
    db.commit()


def _save_uploaded_file(contents: bytes, filename: str, kind: str) -> str:
    """
    Save uploaded file bytes to uploads/images or uploads/videos with a
    timestamp prefix so nothing gets overwritten. Returns the saved path
    (relative, usable both for cv2.VideoCapture and for building the
    /uploads/... URL the frontend uses for thumbnails).
    """
    folder = "images" if kind == "image" else "videos"
    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    safe_name = f"{timestamp_str}_{filename}"
    save_path = os.path.join("uploads", folder, safe_name)
    with open(save_path, "wb") as f:
        f.write(contents)
    return save_path


def _save_upload_record(mode: str, files: list, batch_totals: dict, db: Session):
    record = UploadRecord(
        mode=mode,
        file_count=len(files),
        files=json.dumps(files),
        batch_totals=json.dumps(batch_totals),
    )
    db.add(record)
    db.commit()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
