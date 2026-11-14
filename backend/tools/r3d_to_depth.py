#!/usr/bin/env python3
"""
r3d_to_depth.py - Convert a Record3D (.r3d) export into an RGB photo +
16-bit depth PNG (millimeters) pair, ready for ShelfSense's
/api/detect-with-depth endpoint.

BACKGROUND
----------
A .r3d file is actually a ZIP archive. It typically contains:
  - "metadata"          : a JSON text file with capture info (frame
                           width/height, intrinsics, etc.)
  - "rgbd/<frame>.jpg"   : the color image for each frame
  - "rgbd/<frame>.depth" : the depth map for each frame, as LZFSE-compressed
                           float32 data (one value per pixel, in METERS)
  - "rgbd/<frame>.conf"  : (optional) per-pixel confidence map

This script extracts one frame's color image as-is, and converts its
depth map from float32 meters into a 16-bit PNG in millimeters - which
is exactly the "metric_mm" format that ShelfSense's depth_counter.py
auto-detects (see backend/services/depth_counter.py).

USAGE
-----
    # First, list what's actually inside the file (do this first!):
    python r3d_to_depth.py shelf_scan.r3d --list

    # Then convert frame 0 (default) to a color/depth pair:
    python r3d_to_depth.py shelf_scan.r3d --out shelf

    # This produces:
    #   shelf_rgb.jpg     <- upload as "image" to /api/detect-with-depth
    #   shelf_depth.png   <- upload as "depth_map" to /api/detect-with-depth

    # Convert a different frame (e.g. the 10th captured frame):
    python r3d_to_depth.py shelf_scan.r3d --frame 10 --out shelf

REQUIREMENTS
------------
    pip install pillow numpy --break-system-packages

    Depth decompression needs an LZFSE decoder. Try, in order:
        pip install pyliblzfse --break-system-packages
    If that fails to build on Windows (it needs a C compiler), try:
        pip install liblzfse-python --break-system-packages

    If NEITHER installs, run with --list first and send the output plus
    the error message back - the .depth files may already be stored
    uncompressed in your specific export, in which case this script can
    skip decompression entirely (there's a fallback path for this below).

TROUBLESHOOTING
----------------
If this script errors out, run with --list and share the output - the
exact file names and metadata keys can vary slightly between Record3D
versions, and this script can be adjusted quickly once we see the real
structure of your file.
"""

import argparse
import json
import sys
import zipfile

import numpy as np
from PIL import Image

# Try a few possible LZFSE decoder packages - names vary by platform.
_lzfse_decompress = None
for _modname in ("liblzfse", "lzfse"):
    try:
        _mod = __import__(_modname)
        if hasattr(_mod, "decompress"):
            _lzfse_decompress = _mod.decompress
            break
    except ImportError:
        continue


def list_contents(zf, meta):
    print("=== metadata ===")
    print(json.dumps(meta, indent=2)[:2000])
    print()
    print("=== files in archive (first 30) ===")
    for name in zf.namelist()[:30]:
        info = zf.getinfo(name)
        print(f"  {name}  ({info.file_size} bytes, compressed {info.compress_size})")
    total = len(zf.namelist())
    if total > 30:
        print(f"  ... and {total - 30} more")


def load_metadata(zf) -> dict:
    for candidate in ("metadata", "metadata.json"):
        if candidate in zf.namelist():
            with zf.open(candidate) as f:
                return json.load(f)
    return {}


def find_frame_files(zf, frame: int):
    """
    Return (color_name, depth_name, conf_name_or_None) for the requested
    frame index, trying a few common naming conventions.
    """
    names = set(zf.namelist())
    candidates = [
        (f"rgbd/{frame}.jpg", f"rgbd/{frame}.depth", f"rgbd/{frame}.conf"),
        (f"rgbd/{frame:06d}.jpg", f"rgbd/{frame:06d}.depth", f"rgbd/{frame:06d}.conf"),
        (f"{frame}.jpg", f"{frame}.depth", f"{frame}.conf"),
        (f"color/{frame:06d}.jpg", f"depth/{frame:06d}.png", None),
    ]
    for color, depth, conf in candidates:
        if color in names and depth in names:
            return color, depth, (conf if conf in names else None)

    raise FileNotFoundError(
        f"Could not find frame {frame} in the archive using common naming "
        f"patterns. Run with --list to see the actual file names, then "
        f"tell Claude what they look like so this script can be adjusted."
    )


def decompress_depth_bytes(raw: bytes, width: int, height: int) -> np.ndarray:
    """
    Return a (height, width) float32 array of depth values in METERS.
    """
    expected_size = width * height * 4  # float32

    # Try LZFSE decompression first (the normal case for .r3d files)
    if _lzfse_decompress is not None:
        try:
            decompressed = _lzfse_decompress(raw)
            if len(decompressed) == expected_size:
                return np.frombuffer(decompressed, dtype="<f4").reshape(height, width)
        except Exception:
            pass  # fall through to "already uncompressed" check below

    # Fallback: maybe the bytes are already raw float32 (no compression)
    if len(raw) == expected_size:
        return np.frombuffer(raw, dtype="<f4").reshape(height, width)

    raise ValueError(
        f"Depth data is {len(raw)} bytes; expected {expected_size} bytes "
        f"for a {width}x{height} float32 array (with or without LZFSE "
        f"compression). The depth resolution in metadata may not match "
        f"the actual file - run with --list and check the metadata block."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("r3d_file", help="Path to the .r3d file exported from Record3D")
    parser.add_argument("--frame", type=int, default=0, help="Frame index to extract (default: 0, the first frame)")
    parser.add_argument("--out", default="shelf", help="Output filename prefix (default: 'shelf')")
    parser.add_argument("--list", action="store_true", help="Just print the archive contents and metadata, then exit")
    args = parser.parse_args()

    with zipfile.ZipFile(args.r3d_file) as zf:
        meta = load_metadata(zf)

        if args.list:
            list_contents(zf, meta)
            return

        # Depth resolution: try a few common metadata key names, falling
        # back to the well-known iPhone LiDAR depth resolution (256x192)
        width = meta.get("dw") or meta.get("depthWidth") or meta.get("w") or 256
        height = meta.get("dh") or meta.get("depthHeight") or meta.get("h") or 192

        color_name, depth_name, conf_name = find_frame_files(zf, args.frame)
        print(f"Color file: {color_name}")
        print(f"Depth file: {depth_name}  ({width}x{height} expected)")

        color_bytes = zf.read(color_name)
        depth_bytes = zf.read(depth_name)

    # Save the color image as-is
    rgb_path = f"{args.out}_rgb.jpg"
    with open(rgb_path, "wb") as f:
        f.write(color_bytes)
    print(f"Wrote {rgb_path}")

    # Decompress + convert depth: meters (float32) -> millimeters (uint16)
    depth_m = decompress_depth_bytes(depth_bytes, width, height)
    depth_mm = np.clip(depth_m * 1000.0, 0, 65535).astype(np.uint16)

    depth_path = f"{args.out}_depth.png"
    Image.fromarray(depth_mm).save(depth_path)
    print(f"Wrote {depth_path}")

    # Sanity-check numbers - these should look like real shelf distances
    nonzero = depth_mm[depth_mm > 0]
    if nonzero.size > 0:
        front_cm = np.percentile(nonzero, 1) / 10.0
        back_cm = np.percentile(nonzero, 99) / 10.0
        print()
        print(f"Sanity check (these should look like real distances to your shelf):")
        print(f"  front_border_cm ~= {front_cm:.1f} cm")
        print(f"  back_wall_cm    ~= {back_cm:.1f} cm")
        print()
        print(f"Upload {rgb_path} as 'image' and {depth_path} as 'depth_map'")
        print(f"to /api/detect-with-depth (Live Shelf -> optional depth map section).")
    else:
        print("WARNING: depth map is all zeros - something went wrong with decoding.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        print("\nRun with --list and share the output so this can be fixed.", file=sys.stderr)
        sys.exit(1)
