# ShelfSense - UI Overhaul & New Stock Logic (Complete Package)

This zip contains the **ENTIRE project**, including your trained model
(`best.pt`) and your real `planogram.json` (with blue_lays/thumps_up and
your ruler measurements). Nothing else to copy in - just extract and run.

## How to apply

1. **Delete your old `ShelfSense_Final` folder** entirely.
2. Extract this zip - it creates a `ShelfSense_Final/` folder. Move/rename
   it to `C:\Users\Asus\Desktop\ShelfSense_Final` (or wherever you keep it).
3. Open Command Prompt (not PowerShell), activate your venv from inside the
   project root, and run:
   ```
   pip install -r requirements.txt
   ```
   (this adds `pillow-heif` and `Pillow` for HEIC support - everything else
   should already be installed)
4. Start as usual:
   ```
   python -m uvicorn backend.main:app --reload --port 8000
   ```
   ```
   cd frontend
   npm install
   npm run dev
   ```

That's it - no files to preserve or merge.

## What's new

### 1. Landing page (`/`)
ShelfSense branding, tagline, a short "how it works" section, and a login
form. **This is a demo build - any non-empty username/password logs you in.**
After login you land on `/dashboard`. Logging out (sidebar button) sends you
back here.

### 2. New sidebar
Dashboard, Live Shelf, Upload, Alerts, Planogram, Settings - exactly as
requested. (The old separate Video and Analytics pages were folded into
Upload and Dashboard.)

### 3. New stock-status logic (the core change)
Status is now based on **percentage of ideal stock** (set via Planogram):

| Facings vs ideal | Status |
|---|---|
| 0% | **Out of Stock** |
| 0% - 40% | **Low Stock** |
| 40% - 100%+ | **Stocked** (no alert - this is "show nothing") |
| no ideal set yet | **Uncalibrated** |

This replaced the old `low_stock_threshold` / `critical_threshold` /
"critical" severity system entirely.

### 4. Dashboard
- Four stat cards: Stocked / Low Stock / Out of Stock / Uncalibrated
- **Current Stock Levels** table: Product | Ideal Stock | Current Count | Percentage | Status
- **Stock Alerts** section (low stock / out of stock)
- **Misplaced Products** section (see below)

### 5. Misplaced-product detection (new)
If a product is detected in a shelf column that the Planogram says should
hold a *different* product, it's flagged immediately, e.g.:

> "maggi_small found in blue_lays's slot (slot 3)"

**How it works**: the frame is divided into as many equal-width columns as
you have planogram slots (left to right, by `slot_number`). Each detection's
column is compared to that slot's assigned product. This is a v1 heuristic -
it assumes your camera sees the shelf roughly straight-on with slots in a
left-to-right row. If your layout is different, the Planogram page lets you
reassign which product belongs in which slot/column.

### 6. Planogram page (new) - "change one value, everything updates"
- **Auto-calibrate from photo** (moved here from Settings) - upload a
  fully-stocked shelf photo, sets ideal stock counts automatically
- **Shelf Layout table** - for each slot: which product is assigned (dropdown,
  affects misplaced-detection) and its ideal stock count (editable)
- **Shelf Depth** - editable, used for capacity estimates
- **Product Dimensions table** - width/height/depth per product (moved from Settings)

All of these write directly to `planogram.json`, which is re-read on every
detection - so changes are live immediately, no restart needed.

### 7. Upload page (new) - replaces old Live Shelf + Video pages for files
Accepts images (jpg, jpeg, png, heic, heif, webp, bmp) and videos (mp4, mov,
avi, mkv, webm). Auto-detects which based on file extension and routes to
the right endpoint. HEIC support requires `pillow-heif` (added to
requirements.txt).

### 8. Live Shelf page
Kept as the dedicated "single photo, right now" page (works well with phone
camera capture - `capture="environment"` opens the camera directly on
mobile). Still has the optional depth-map upload from the earlier update.

### 9. Settings page (simplified)
Now just shop name / location / camera ID, plus an "About" card. Stock
configuration moved to Planogram.

### 10. Multi-file upload with Add / Replace stock modes (new)

The Upload page now accepts **multiple files at once** (photos and/or
videos, mixed) and asks how they should affect "current stock":

- **Add to current stock** - use when these new files cover *different*
  shelf sections than what you've already uploaded. Their counts are
  summed and ADDED on top of the existing snapshot.
- **Replace current stock (fresh scan)** - use after restocking. Every
  product's count is reset to 0, then set from what these files show.
  Anything not visible in this batch is treated as 0.

This solves exactly the two cases you described:
- *Case 1 (keep old + new)*: upload the new photos in **Add** mode.
- *Case 2 (forget old, restocked)*: upload the new photos in **Replace** mode.

**Under the hood**: there's now a single "current stock" snapshot file at
`backend/data/current_stock.json` - `{product_class: count}`. This is what
the Dashboard percentage table reads. It's updated by:
- `/api/detect` (single photo, Live Shelf) → `replace_detected`: only the
  products seen in that one photo are updated, others untouched
- `/api/detect-video` → `replace_detected`, using the max count seen across
  sampled frames
- `/api/detect-batch` (new, multi-file Upload) → `add` or `replace_all`
  depending on the mode you pick

New endpoints: `POST /api/detect-batch` (multipart `files[]` + `?mode=add|replace`),
`GET /api/stock/current`, `POST /api/stock/reset` (zero everything - handy
before a demo), `GET /api/uploads/history`.

### 11. Persistent upload history (new)

Every photo/video you upload (single or batch) is saved to
`uploads/images/` or `uploads/videos/` with a timestamp prefix, and recorded
in the database (`UploadRecord` table). The bottom of the Upload page shows
an "Upload History" section with thumbnails, mode, and the counts found in
each batch - served via a new static mount at `/uploads/...`.


## Backend changes summary

- `services/stock_state.py` (NEW): the current-stock snapshot
  (`backend/data/current_stock.json`), with `replace_detected` / `add` /
  `replace_all` update modes - see "Multi-file upload" section above.
- `models/database.py`: added `UploadRecord` table for upload history.
- `detector.py`: `_severity()` rewritten to percentage-based thresholds (40%
  constant `LOW_STOCK_PCT`). New `_detect_misplaced()` method.
- `alerts.py`: removed "critical" severity; added `process_misplaced()` -
  misplaced alerts fire immediately (no 2-frame debounce, since a misplaced
  item is visually obvious in one frame). Added `process_stock_snapshot()`
  for batch-upload alerts.
- `main.py`: all detection endpoints now also return `misplaced_products`
  and `misplaced_alerts_fired`. `/api/analytics/stock-summary` rewritten to
  read the current-stock snapshot, with `current_count` / `ideal_count` /
  `percentage` / `status` fields. New endpoints: `POST /api/detect-batch`,
  `GET /api/uploads/history`, `GET /api/stock/current`, `POST /api/stock/reset`,
  `POST /api/planogram/slot`, `POST /api/planogram/shelf-depth`,
  `POST /api/planogram/shop-info`. Added `decode_image_bytes()` helper for
  HEIC support across all upload endpoints, and a static mount at `/uploads`.
- `planogram_service.py`: added `update_slot()`, `update_shelf_depth()`,
  `update_shop_info()`.

## Known limitation to mention in your demo/report

The misplaced-product detection uses an **equal-width column heuristic**.
It's a clean, explainable v1 that works well for a straight-on shop shelf
photo with products arranged in a left-to-right row matching your planogram
slot order. For irregular layouts (multiple rows, angled cameras), it would
need a more advanced spatial mapping - good "future work" material.
