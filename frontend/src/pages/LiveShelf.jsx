// src/pages/LiveShelf.jsx
import React, { useState, useRef } from "react";
import { Camera, Loader2, Layers, Info } from "lucide-react";
import { apiPostFile, API_BASE } from "../services/api";

export default function LiveShelf() {
  const [preview, setPreview] = useState(null);
  const [file, setFile] = useState(null);
  const [depthFile, setDepthFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showOverride, setShowOverride] = useState(false);
  const [overrideNearCm, setOverrideNearCm] = useState("");
  const [overrideFarCm, setOverrideFarCm] = useState("");
  const canvasRef = useRef(null);
  const imgRef = useRef(null);

  const handleFile = (f) => {
    setFile(f);
    setResult(null);
    setError(null);
    setPreview(URL.createObjectURL(f));
  };

  const handleDetect = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      let res;
      if (depthFile) {
        const formData = new FormData();
        formData.append("image", file);
        formData.append("depth_map", depthFile);
        // Normally nothing is sent here - front/back distances are read
        // automatically from the depth map. Only send overrides if the
        // person explicitly opened "Advanced" and entered values.
        const params = {};
        if (overrideNearCm !== "") params.near_cm = overrideNearCm;
        if (overrideFarCm !== "") params.far_cm = overrideFarCm;
        const query = new URLSearchParams(params).toString();
        const r = await fetch(`${API_BASE}/api/detect-with-depth${query ? `?${query}` : ""}`, {
          method: "POST",
          body: formData,
        });
        if (!r.ok) throw new Error(`Request failed: ${r.status}`);
        res = await r.json();
      } else {
        res = await apiPostFile("/api/detect", file);
      }
      if (res.status !== "success") throw new Error(res.detail || "Detection failed");
      setResult(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };


  const onImageLoad = () => {
    if (!result || !canvasRef.current || !imgRef.current) return;
    drawBoxes();
  };

  const drawBoxes = () => {
    const img = imgRef.current;
    const canvas = canvasRef.current;
    if (!img || !canvas || !result) return;

    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const scaleX = img.naturalWidth / 640;
    const scaleY = img.naturalHeight / 640;

    result.detections.forEach((d) => {
      const [x1, y1, x2, y2] = d.bbox;
      const color = d.product_class === "empty_slot" ? "#D1654A" : "#8FB573";
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1 * scaleX, y1 * scaleY, (x2 - x1) * scaleX, (y2 - y1) * scaleY);

      ctx.fillStyle = color;
      ctx.font = "14px Inter, sans-serif";
      ctx.fillText(
        `${d.product_class} ${(d.confidence * 100).toFixed(0)}%`,
        x1 * scaleX,
        Math.max(12, y1 * scaleY - 4)
      );
    });
  };

  React.useEffect(() => {
    if (result) drawBoxes();
  }, [result]);

  return (
    <div>
      <h1 className="font-display text-3xl font-bold mb-1">Live Shelf</h1>
      <p className="text-muted mb-6">Capture or upload a single shelf photo to detect products</p>

      <div className="grid md:grid-cols-2 gap-6">
        <div>
          <label className="block border-2 border-dashed border-ink-lighter rounded-lg p-8 text-center cursor-pointer hover:border-amber transition-colors">
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={(e) => e.target.files[0] && handleFile(e.target.files[0])}
            />
            <Camera className="mx-auto mb-2 text-muted" size={32} />
            <p className="text-sm text-muted">Click to capture or select an image</p>
          </label>

          {preview && (
            <div className="relative mt-4 inline-block">
              <img
                ref={imgRef}
                src={preview}
                alt="preview"
                className="max-w-full rounded-lg"
                onLoad={onImageLoad}
              />
              <canvas ref={canvasRef} className="absolute top-0 left-0 max-w-full" />
            </div>
          )}

          {/* Optional depth map upload (3D Scanner App) */}
          <details className="mt-4 bg-ink-light border border-ink-lighter rounded-lg p-3">
            <summary className="cursor-pointer text-sm font-medium flex items-center gap-2 text-muted">
              <Layers size={16} /> Optional: add depth map (3D Scanner App)
            </summary>
            <div className="mt-3 space-y-3">
              <label className="block border border-dashed border-ink-lighter rounded p-3 text-center cursor-pointer hover:border-amber">
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => e.target.files[0] && setDepthFile(e.target.files[0])}
                />
                <p className="text-xs text-muted">
                  {depthFile ? depthFile.name : "Click to select depth map image"}
                </p>
              </label>

              {depthFile && (
                <div>
                  <button
                    type="button"
                    onClick={() => setShowOverride((v) => !v)}
                    className="text-xs text-muted underline"
                  >
                    {showOverride ? "Hide advanced override" : "Advanced: override front/back distance"}
                  </button>
                  {showOverride && (
                    <div className="grid grid-cols-2 gap-3 mt-2">
                      <div>
                        <label className="text-xs text-muted">Front border override (cm)</label>
                        <input
                          type="number"
                          placeholder="auto"
                          value={overrideNearCm}
                          onChange={(e) => setOverrideNearCm(e.target.value)}
                          className="w-full bg-ink border border-ink-lighter rounded px-2 py-1 text-sm mt-1"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-muted">Back wall override (cm)</label>
                        <input
                          type="number"
                          placeholder="auto"
                          value={overrideFarCm}
                          onChange={(e) => setOverrideFarCm(e.target.value)}
                          className="w-full bg-ink border border-ink-lighter rounded px-2 py-1 text-sm mt-1"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              <p className="text-xs text-muted flex items-start gap-1">
                <Info size={12} className="mt-0.5 flex-shrink-0" />
                Front/back shelf distances are read automatically from the depth map.
                Depth-based counts are ESTIMATES assuming products are stacked
                front-to-back within each column - not an exact physical count.
              </p>
            </div>
          </details>

          <button
            onClick={handleDetect}
            disabled={!file || loading}
            className="mt-4 w-full bg-amber hover:bg-amber-dark disabled:bg-ink-lighter disabled:text-muted disabled:cursor-not-allowed
                       text-ink font-display font-semibold py-2.5 rounded-lg flex items-center justify-center gap-2 transition-colors"
          >
            {loading ? <Loader2 className="animate-spin" size={18} /> : null}
            {loading ? "Detecting..." : depthFile ? "Detect with Depth" : "Detect Products"}
          </button>

          {error && (
            <div className="mt-3 p-3 rounded bg-rust/10 border border-rust text-rust text-sm">
              {error}
            </div>
          )}
        </div>

        <div>
          <h2 className="font-display text-lg font-semibold mb-3">Results</h2>
          {!result ? (
            <p className="text-muted text-sm">Run a detection to see results here.</p>
          ) : (
            <div className="space-y-3">

              {/* ── DEPTH TOTALS (primary result when depth map used) ── */}
              {result.depth_totals ? (
                <div className="shelf-tag tag-sage p-4">
                  <p className="text-xs uppercase tracking-widest text-muted mb-2">
                    Total Stock (Depth Formula)
                  </p>
                  <div className="space-y-1">
                    {Object.entries(result.depth_totals).map(([cls, total]) => (
                      <div key={cls} className="flex justify-between text-sm">
                        <span className="font-medium">{cls}</span>
                        <span className="font-mono font-bold text-sage text-lg">{total}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="shelf-tag tag-sage p-4">
                  <p className="text-sm text-muted">Shelf Health Score</p>
                  <p className="font-mono text-3xl font-bold text-sage">{result.health_score}%</p>
                </div>
              )}

              {/* ── DEPTH MAP INFO ── */}
              {result.depth_map_info && (
                <div className="bg-ink-light border border-ink-lighter rounded-lg p-3 text-xs space-y-1">
                  <p className="font-semibold text-muted mb-1">Depth Map Info</p>
                  <p>Mode: <span className={`font-mono font-bold ${result.depth_map_info.mode === "metric_mm" || result.depth_map_info.mode === "metric_m" ? "text-sage" : "text-amber"}`}>
                    {result.depth_map_info.mode}
                  </span>
                  {result.depth_map_info.mode === "relative_8bit" &&
                    <span className="text-amber ml-1">(fallback — no metric data in depth map)</span>}
                  </p>
                  <p>Front border (camera → shelf front): <span className="font-mono">{result.depth_map_info.front_border_cm} cm</span></p>
                  <p>Back wall (camera → shelf back): <span className="font-mono">{result.depth_map_info.back_wall_cm} cm</span></p>
                  <p>Shelf height used: <span className="font-mono">{result.depth_map_info.shelf_height_cm} cm</span></p>
                </div>
              )}

              {/* ── PER-COLUMN FORMULA BREAKDOWN ── */}
              {result.column_stocks && Object.keys(result.column_stocks).length > 0 && (
                <div className="bg-ink-light border border-ink-lighter rounded-lg p-4">
                  <p className="text-sm font-semibold mb-3">Per-Column Calculation</p>
                  <div className="space-y-2">
                    {Object.entries(result.column_stocks).map(([slotNum, cs]) => (
                      <div key={slotNum} className="bg-ink rounded p-3 text-xs">
                        <div className="flex justify-between items-start mb-1">
                          <span className="font-bold text-paper text-sm">{cs.product_class}</span>
                          <span className="font-mono font-bold text-sage text-base">{cs.actual_total}</span>
                        </div>
                        <p className="text-muted font-mono leading-5">{cs.formula}</p>
                        {cs.misplaced_in_column > 0 && (
                          <p className="text-amber mt-1">
                            ⚠ {cs.misplaced_in_column} misplaced product(s) subtracted
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-muted mt-3 leading-5">{result.formula_explanation}</p>
                </div>
              )}

              {/* ── YOLOV8 DETECTION (what's visible — for reference) ── */}
              <div className="bg-ink-light border border-ink-lighter rounded-lg p-4">
                <p className="text-sm text-muted mb-2">
                  YOLOv8 Visible Detections
                  <span className="ml-2 text-xs">(used to identify products + misplaced)</span>
                </p>
                <div className="space-y-1">
                  {Object.entries(result.yolov8_class_counts || result.class_counts || {}).map(([cls, count]) => (
                    <div key={cls} className="flex justify-between text-sm">
                      <span>{cls}</span>
                      <span className="font-mono">{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* ── MISPLACED PRODUCTS ── */}
              {result.misplaced_products?.length > 0 && (
                <div className="shelf-tag tag-amber p-4">
                  <p className="text-sm font-semibold text-amber mb-2">Misplaced Products</p>
                  {result.misplaced_products.map((m, i) => (
                    <p key={i} className="text-sm">{m.message}</p>
                  ))}
                </div>
              )}

              {/* ── STOCK ALERTS ── */}
              {result.stock_alerts_fired?.length > 0 && (
                <div className="shelf-tag tag-rust p-4">
                  <p className="text-sm font-semibold text-rust mb-2">Stock Alerts</p>
                  {result.stock_alerts_fired.map((a) => (
                    <p key={a.id} className="text-sm">{a.message}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
