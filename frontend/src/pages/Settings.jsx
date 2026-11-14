// src/pages/Settings.jsx
import React, { useState, useEffect } from "react";
import { Save, Boxes } from "lucide-react";
import { apiGet, apiPost } from "../services/api";

export default function Settings() {
  const [planogram, setPlanogram] = useState(null);
  const [shopName, setShopName] = useState("");
  const [location, setLocation] = useState("");
  const [cameraId, setCameraId] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiGet("/api/planogram")
      .then((p) => {
        setPlanogram(p);
        setShopName(p.shop_name || "");
        setLocation(p.location || "");
        setCameraId(p.camera_id || "");
      })
      .catch((e) => setError(e.message));
  }, []);

  const save = async () => {
    await apiPost("/api/planogram/shop-info", {
      shop_name: shopName,
      location,
      camera_id: cameraId,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div>
      <h1 className="font-display text-3xl font-bold mb-1">Settings</h1>
      <p className="text-muted mb-6">Shop details and app information</p>

      {error && (
        <div className="mb-4 p-3 rounded bg-rust/10 border border-rust text-rust text-sm">
          {error}
        </div>
      )}

      <div className="bg-ink-light border border-ink-lighter rounded-lg p-5 mb-6">
        <h2 className="font-display text-lg font-semibold mb-4">Shop Details</h2>
        <div className="space-y-4 max-w-md">
          <div>
            <label className="block text-xs text-muted mb-1 font-medium uppercase tracking-wider">Shop Name</label>
            <input
              type="text"
              value={shopName}
              onChange={(e) => setShopName(e.target.value)}
              className="w-full bg-ink border border-ink-lighter rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1 font-medium uppercase tracking-wider">Location</label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full bg-ink border border-ink-lighter rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1 font-medium uppercase tracking-wider">Camera ID</label>
            <input
              type="text"
              value={cameraId}
              onChange={(e) => setCameraId(e.target.value)}
              className="w-full bg-ink border border-ink-lighter rounded px-3 py-2"
            />
          </div>
          <button
            onClick={save}
            className="bg-amber hover:bg-amber-dark text-ink font-display font-semibold px-4 py-2 rounded-lg
                       flex items-center gap-2 transition-colors"
          >
            <Save size={16} /> Save
          </button>
          {saved && <p className="text-sage text-sm">Saved.</p>}
        </div>
      </div>

      <div className="shelf-tag tag-amber p-5">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-md bg-amber flex items-center justify-center">
            <Boxes size={18} className="text-ink" />
          </div>
          <h2 className="font-display text-lg font-semibold">About ShelfSense</h2>
        </div>
        <p className="text-sm text-muted leading-relaxed">
          AI-powered retail shelf monitoring. Detects products with YOLOv8, compares
          counts against a configurable planogram, and raises alerts for low stock,
          out-of-stock slots, and misplaced products.
        </p>
        <p className="text-xs text-muted mt-3">
          Stock-level layout, ideal counts, and product dimensions are managed on the{" "}
          <a href="/planogram" className="underline font-semibold text-amber">Planogram</a> page.
        </p>
      </div>
    </div>
  );
}
