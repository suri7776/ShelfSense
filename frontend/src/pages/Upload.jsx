// src/pages/Upload.jsx
import React, { useState, useRef } from "react";
import { UploadCloud, Loader2, Film, Image as ImageIcon, X, PlusCircle, RefreshCcw, Info } from "lucide-react";
import { API_BASE } from "../services/api";

const IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "heic", "heif", "webp", "bmp"];
const VIDEO_EXTENSIONS = ["mp4", "mov", "avi", "mkv", "webm"];

function getFileKind(file) {
  const ext = file.name.split(".").pop().toLowerCase();
  if (IMAGE_EXTENSIONS.includes(ext)) return "image";
  if (VIDEO_EXTENSIONS.includes(ext)) return "video";
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  return null;
}

export default function Upload() {
  const [files, setFiles] = useState([]); // [{file, kind}]
  const [mode, setMode] = useState("add");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const inputRef = useRef(null);

  const addFiles = (fileList) => {
    const accepted = [];
    const rejected = [];
    Array.from(fileList).forEach((f) => {
      const kind = getFileKind(f);
      if (kind) accepted.push({ file: f, kind });
      else rejected.push(f.name);
    });
    if (rejected.length) {
      setError(`Unsupported file type, skipped: ${rejected.join(", ")}`);
    } else {
      setError(null);
    }
    setFiles((prev) => [...prev, ...accepted]);
    setResult(null);
  };

  const removeFile = (idx) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleProcess = async () => {
    if (files.length === 0) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const formData = new FormData();
      files.forEach(({ file }) => formData.append("files", file));
      const url = `${API_BASE}/api/detect-batch?mode=${mode}`;
      const res = await fetch(url, { method: "POST", body: formData });
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      const data = await res.json();
      if (data.status !== "success") throw new Error(data.detail || "Processing failed");
      setResult(data);
      setFiles([]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="font-display text-3xl font-bold mb-1">Upload</h1>
      <p className="text-muted mb-6">
        Upload one or more shelf photos and/or videos. Supported: JPEG, PNG, HEIC (iPhone), MP4, MOV.
      </p>

      <div className="grid md:grid-cols-2 gap-6">
        <div>
          {/* Mode selector */}
          <div className="mb-4">
            <p className="text-sm font-medium mb-2">How should these files update current stock?</p>
            <div className="grid grid-cols-1 gap-2">
              <button
                onClick={() => setMode("add")}
                className={`text-left p-3 rounded-lg border transition-colors ${
                  mode === "add" ? "border-amber bg-amber/10" : "border-ink-lighter bg-ink-light hover:border-amber/50"
                }`}
              >
                <div className="flex items-center gap-2 font-medium mb-1">
                  <PlusCircle size={16} className={mode === "add" ? "text-amber" : "text-muted"} />
                  Add to current stock
                </div>
                <p className="text-xs text-muted">
                  These photos cover NEW or ADDITIONAL sections of the shelf. Counts found here will
                  be added on top of whatever is already recorded.
                </p>
              </button>

              <button
                onClick={() => setMode("replace")}
                className={`text-left p-3 rounded-lg border transition-colors ${
                  mode === "replace" ? "border-amber bg-amber/10" : "border-ink-lighter bg-ink-light hover:border-amber/50"
                }`}
              >
                <div className="flex items-center gap-2 font-medium mb-1">
                  <RefreshCcw size={16} className={mode === "replace" ? "text-amber" : "text-muted"} />
                  Replace current stock (fresh scan)
                </div>
                <p className="text-xs text-muted">
                  These photos are a full re-scan after restocking. Old counts are discarded - every
                  product's count is reset based only on what's found in these files.
                </p>
              </button>
            </div>
          </div>

          {/* File picker */}
          <label className="block border-2 border-dashed border-ink-lighter rounded-lg p-6 text-center cursor-pointer hover:border-amber transition-colors">
            <input
              ref={inputRef}
              type="file"
              accept="image/*,video/*,.heic,.heif"
              multiple
              className="hidden"
              onChange={(e) => e.target.files.length && addFiles(e.target.files)}
            />
            <UploadCloud className="mx-auto mb-2 text-muted" size={28} />
            <p className="text-sm text-muted">Click to add photos or videos (you can select multiple)</p>
          </label>

          {/* Selected files list */}
          {files.length > 0 && (
            <div className="mt-3 space-y-1.5">
              {files.map((f, i) => (
                <div key={i} className="flex items-center justify-between bg-ink-light border border-ink-lighter rounded px-3 py-2 text-sm">
                  <div className="flex items-center gap-2 truncate">
                    {f.kind === "video" ? <Film size={14} className="text-muted flex-shrink-0" /> : <ImageIcon size={14} className="text-muted flex-shrink-0" />}
                    <span className="truncate">{f.file.name}</span>
                  </div>
                  <button onClick={() => removeFile(i)} className="text-muted hover:text-rust flex-shrink-0 ml-2">
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <button
            onClick={handleProcess}
            disabled={files.length === 0 || loading}
            className="mt-4 w-full bg-amber hover:bg-amber-dark disabled:bg-ink-lighter disabled:text-muted disabled:cursor-not-allowed
                       text-ink font-display font-semibold py-2.5 rounded-lg flex items-center justify-center gap-2 transition-colors"
          >
            {loading ? <Loader2 className="animate-spin" size={18} /> : <UploadCloud size={18} />}
            {loading ? "Processing..." : `Process ${files.length || ""} file${files.length === 1 ? "" : "s"}`.trim()}
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
            <p className="text-muted text-sm">Process some files to see results here.</p>
          ) : (
            <BatchResults result={result} />
          )}
        </div>
      </div>

      <UploadHistory />
    </div>
  );
}

function BatchResults({ result }) {
  return (
    <div className="space-y-3">
      <div className="bg-ink-light border border-ink-lighter rounded-lg p-4 flex items-center gap-2 text-sm">
        <Info size={16} className="text-amber flex-shrink-0" />
        <span>
          Processed {result.file_count} file(s) in <strong>{result.mode}</strong> mode.
        </span>
      </div>

      <div className="bg-ink-light border border-ink-lighter rounded-lg p-4">
        <p className="text-sm text-muted mb-2">Combined totals from this batch</p>
        <div className="space-y-1">
          {Object.entries(result.batch_totals).map(([cls, count]) => (
            <div key={cls} className="flex justify-between text-sm">
              <span>{cls}</span>
              <span className="font-mono font-semibold">{count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="shelf-tag tag-sage p-4">
        <p className="text-sm text-muted mb-2">Current stock snapshot (after this update)</p>
        <div className="space-y-1">
          {Object.entries(result.current_stock).map(([cls, count]) => (
            <div key={cls} className="flex justify-between text-sm">
              <span>{cls}</span>
              <span className="font-mono font-semibold text-sage">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {result.misplaced_products?.length > 0 && (
        <div className="shelf-tag tag-amber p-4">
          <p className="text-sm font-semibold text-amber mb-2">Misplaced products</p>
          {result.misplaced_products.map((m, i) => (
            <p key={i} className="text-sm">{m.message}</p>
          ))}
        </div>
      )}

      {result.stock_alerts_fired?.length > 0 && (
        <div className="shelf-tag tag-rust p-4">
          <p className="text-sm font-semibold text-rust mb-2">Stock alerts</p>
          {result.stock_alerts_fired.map((a) => (
            <p key={a.id} className="text-sm">{a.message}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function UploadHistory() {
  const [history, setHistory] = useState(null);
  const [error, setError] = useState(null);

  React.useEffect(() => {
    fetch(`${API_BASE}/api/uploads/history?limit=10`)
      .then((r) => r.json())
      .then((d) => setHistory(d.uploads || []))
      .catch((e) => setError(e.message));
  }, []);

  // Reload after the page mounts and whenever a batch finishes (simple polling)
  React.useEffect(() => {
    const interval = setInterval(() => {
      fetch(`${API_BASE}/api/uploads/history?limit=10`)
        .then((r) => r.json())
        .then((d) => setHistory(d.uploads || []))
        .catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="mt-8">
      <h2 className="font-display text-lg font-semibold mb-3">Upload History</h2>
      {error && <p className="text-rust text-sm">{error}</p>}
      {!history ? (
        <p className="text-muted text-sm">Loading...</p>
      ) : history.length === 0 ? (
        <p className="text-muted text-sm">No uploads yet.</p>
      ) : (
        <div className="space-y-3">
          {history.map((h) => (
            <div key={h.id} className="bg-ink-light border border-ink-lighter rounded-lg p-4">
              <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                    h.mode === "replace" ? "bg-amber/20 text-amber" : h.mode === "add" ? "bg-sage/20 text-sage" : "bg-muted/20 text-muted"
                  }`}>
                    {h.mode === "single" ? "SINGLE" : h.mode.toUpperCase()}
                  </span>
                  <span className="text-sm text-muted">{h.file_count} file(s)</span>
                </div>
                <span className="text-xs text-muted">{new Date(h.timestamp).toLocaleString()}</span>
              </div>

              <div className="flex gap-2 overflow-x-auto pb-1">
                {h.files.map((f, i) => (
                  f.kind === "image" ? (
                    <img
                      key={i}
                      src={`${API_BASE}/${f.path.replace(/\\/g, "/")}`}
                      alt={f.filename}
                      title={f.filename}
                      className="h-16 w-16 object-cover rounded border border-ink-lighter flex-shrink-0"
                    />
                  ) : (
                    <div key={i} className="h-16 w-16 flex items-center justify-center rounded border border-ink-lighter bg-ink flex-shrink-0" title={f.filename}>
                      <Film size={20} className="text-muted" />
                    </div>
                  )
                ))}
              </div>

              {Object.keys(h.batch_totals).length > 0 && (
                <p className="text-xs text-muted mt-2">
                  {Object.entries(h.batch_totals).map(([k, v]) => `${k}: ${v}`).join(" · ")}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
