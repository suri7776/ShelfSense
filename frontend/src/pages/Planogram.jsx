// src/pages/Planogram.jsx
import React, { useState, useEffect } from "react";
import { UploadCloud, Loader2, Save, Info } from "lucide-react";
import { apiGet, apiPost, apiPostFile } from "../services/api";

export default function Planogram() {
  const [planogram, setPlanogram] = useState(null);
  const [error, setError] = useState(null);
  const [calibFile, setCalibFile] = useState(null);
  const [calibLoading, setCalibLoading] = useState(false);
  const [calibResult, setCalibResult] = useState(null);

  const load = () => {
    apiGet("/api/planogram")
      .then(setPlanogram)
      .catch((e) => setError(e.message));
  };

  useEffect(() => { load(); }, []);

  const handleCalibrate = async () => {
    if (!calibFile) return;
    setCalibLoading(true);
    setError(null);
    try {
      const res = await apiPostFile("/api/planogram/calibrate", calibFile);
      setCalibResult(res);
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setCalibLoading(false);
    }
  };

  if (!planogram && !error) {
    return <p className="text-muted">Loading planogram...</p>;
  }

  const productNames = Object.keys(planogram?.product_dimensions || {}).filter(
    (p) => p !== "empty_slot"
  );
  const expectedFacings = planogram?.expected_facings || {};

  return (
    <div>
      <h1 className="font-display text-3xl font-bold mb-1">Planogram</h1>
      <p className="text-muted mb-6">
        This is the single source of truth for ideal stock targets, product dimensions, and shelf
        depth. There are no fixed shelf positions here — which product is in which physical spot
        is read fresh from each photo at detection time, not stored as a layout. Any change here
        is picked up immediately by Dashboard, Alerts, and detection.
      </p>

      {error && (
        <div className="mb-4 p-3 rounded bg-rust/10 border border-rust text-rust text-sm">
          {error}
        </div>
      )}

      {/* Auto calibration */}
      <div className="bg-ink-light border border-ink-lighter rounded-lg p-5 mb-6">
        <h2 className="font-display text-lg font-semibold mb-1">Auto-calibrate from photo</h2>
        <p className="text-sm text-muted mb-4">
          Upload a photo of the shelf when it is <strong>fully stocked</strong>. This sets the
          "ideal stock" (100%) target for every product.
        </p>

        <label className="block border-2 border-dashed border-ink-lighter rounded-lg p-6 text-center cursor-pointer hover:border-amber mb-3">
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => e.target.files[0] && setCalibFile(e.target.files[0])}
          />
          <UploadCloud className="mx-auto mb-2 text-muted" size={28} />
          <p className="text-sm text-muted">{calibFile ? calibFile.name : "Click to select full-shelf photo"}</p>
        </label>

        <button
          onClick={handleCalibrate}
          disabled={!calibFile || calibLoading}
          className="w-full bg-amber hover:bg-amber-dark disabled:bg-ink-lighter disabled:text-muted disabled:cursor-not-allowed
                     text-ink font-display font-semibold py-2.5 rounded-lg flex items-center justify-center gap-2 transition-colors"
        >
          {calibLoading ? <Loader2 className="animate-spin" size={18} /> : null}
          {calibLoading ? "Calibrating..." : "Calibrate from Photo"}
        </button>

        {calibResult && (
          <div className="mt-4 p-3 bg-ink rounded text-sm">
            <p className="font-semibold mb-2">Updated {calibResult.updated_slots.length} product(s):</p>
            {calibResult.updated_slots.map((s) => (
              <p key={s.product} className="font-mono text-xs">{s.product}: ideal stock = {s.expected_facings}</p>
            ))}
          </div>
        )}
      </div>

      {/* Ideal stock per product */}
      <div className="bg-ink-light border border-ink-lighter rounded-lg p-5 mb-6">
        <h2 className="font-display text-lg font-semibold mb-1">Ideal Stock</h2>
        <p className="text-sm text-muted mb-4 flex items-start gap-1">
          <Info size={14} className="mt-0.5 flex-shrink-0" />
          Target quantity per product, used for Dashboard percentages and Low/Out-of-Stock alerts.
          Not tied to any shelf position.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted text-xs uppercase tracking-wider border-b border-ink-lighter">
                <th className="py-2 pr-4 font-medium">Product</th>
                <th className="py-2 font-medium">Ideal Stock (facings)</th>
              </tr>
            </thead>
            <tbody>
              {productNames.map((name) => (
                <ExpectedFacingsRow
                  key={name}
                  productClass={name}
                  value={expectedFacings[name] ?? 0}
                  onSaved={load}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Shelf depth */}
      <div className="bg-ink-light border border-ink-lighter rounded-lg p-5 mb-6">
        <h2 className="font-display text-lg font-semibold mb-1">Shelf Depth</h2>
        <p className="text-sm text-muted mb-3">
          Front-to-back depth of the shelf in cm. Used for the capacity-based "estimated total" calculation.
        </p>
        <ShelfDepthEditor value={planogram.shelf_depth_cm} onSaved={load} />
      </div>

      {/* Product dimensions */}
      <div className="bg-ink-light border border-ink-lighter rounded-lg p-5">
        <h2 className="font-display text-lg font-semibold mb-1">Product Dimensions (cm)</h2>
        <p className="text-sm text-muted mb-4">
          Used to estimate total stock (facings x shelf-depth / product-depth). Measure with a ruler.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted text-xs uppercase tracking-wider border-b border-ink-lighter">
                <th className="py-2 pr-4 font-medium">Product</th>
                <th className="py-2 pr-4 font-medium">Width</th>
                <th className="py-2 pr-4 font-medium">Height</th>
                <th className="py-2 font-medium">Depth</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(planogram.product_dimensions || {})
                .filter(([name]) => name !== "empty_slot")
                .map(([name, dims]) => (
                  <tr key={name} className="border-b border-ink-lighter/50">
                    <td className="py-2.5 pr-4 font-medium">
                      {name}
                      {dims._placeholder && (
                        <span className="ml-2 text-xs text-amber">(placeholder - please update)</span>
                      )}
                    </td>
                    <DimCell productClass={name} field="width_cm" dims={dims} onSaved={load} />
                    <DimCell productClass={name} field="height_cm" dims={dims} onSaved={load} />
                    <DimCell productClass={name} field="depth_cm" dims={dims} onSaved={load} />
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ExpectedFacingsRow({ productClass, value, onSaved }) {
  const [ideal, setIdeal] = useState(value);
  const [saved, setSaved] = useState(false);

  useEffect(() => setIdeal(value), [value]);

  const save = async () => {
    await apiPost("/api/planogram/expected-facings", {
      product_class: productClass,
      expected_facings: parseInt(ideal, 10) || 0,
    });
    setSaved(true);
    onSaved();
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <tr className="border-b border-ink-lighter/50">
      <td className="py-2.5 pr-4 font-medium">{productClass}</td>
      <td className="py-2.5 flex items-center gap-2">
        <input
          type="number"
          value={ideal}
          onChange={(e) => setIdeal(e.target.value)}
          className="w-20 bg-ink border border-ink-lighter rounded px-2 py-1 font-mono"
        />
        <button onClick={save} className="text-muted hover:text-amber">
          <Save size={16} />
        </button>
        {saved && <span className="text-xs text-sage">Saved</span>}
      </td>
    </tr>
  );
}

function ShelfDepthEditor({ value, onSaved }) {
  const [val, setVal] = useState(value);
  const [saved, setSaved] = useState(false);

  useEffect(() => setVal(value), [value]);

  const save = async () => {
    await apiPost("/api/planogram/shelf-depth", { shelf_depth_cm: parseFloat(val) });
    setSaved(true);
    onSaved();
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        value={val}
        onChange={(e) => setVal(e.target.value)}
        className="w-28 bg-ink border border-ink-lighter rounded px-2 py-1 font-mono"
      />
      <span className="text-sm text-muted">cm</span>
      <button onClick={save} className="text-muted hover:text-amber">
        <Save size={16} />
      </button>
      {saved && <span className="text-xs text-sage">Saved</span>}
    </div>
  );
}

function DimCell({ productClass, field, dims, onSaved }) {
  const [val, setVal] = useState(dims[field]);
  const [saved, setSaved] = useState(false);

  useEffect(() => setVal(dims[field]), [dims, field]);

  const save = async () => {
    await apiPost("/api/planogram/product-dimensions", {
      product_class: productClass,
      width_cm: field === "width_cm" ? parseFloat(val) : dims.width_cm,
      height_cm: field === "height_cm" ? parseFloat(val) : dims.height_cm,
      depth_cm: field === "depth_cm" ? parseFloat(val) : dims.depth_cm,
    });
    setSaved(true);
    onSaved();
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <td className="py-2.5 pr-4">
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={val}
          onChange={(e) => setVal(e.target.value)}
          className="w-20 bg-ink border border-ink-lighter rounded px-2 py-1 font-mono"
        />
        <button onClick={save} className="text-muted hover:text-amber">
          <Save size={16} />
        </button>
        {saved && <span className="text-xs text-sage">Saved</span>}
      </div>
    </td>
  );
}
