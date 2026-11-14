// src/pages/Alerts.jsx
import React, { useState, useEffect } from "react";
import { CheckCircle, ArrowLeftRight, TrendingDown, AlertTriangle } from "lucide-react";
import { apiGet, apiPut } from "../services/api";

const SEVERITIES = ["all", "low", "empty", "misplaced"];
const SEVERITY_LABELS = { all: "All", low: "Low Stock", empty: "Out of Stock", misplaced: "Misplaced" };

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [severity, setSeverity] = useState("all");
  const [error, setError] = useState(null);

  const load = async () => {
    try {
      const path = severity === "all"
        ? "/api/alerts?limit=50&resolved=false"
        : `/api/alerts?limit=50&resolved=false&severity=${severity}`;
      const res = await apiGet(path);
      setAlerts(Array.isArray(res.alerts) ? res.alerts : []);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [severity]);

  const resolve = async (id) => {
    await apiPut(`/api/alerts/${id}/resolve`);
    load();
  };

  return (
    <div>
      <h1 className="font-display text-3xl font-bold mb-1">Alerts</h1>
      <p className="text-muted mb-6">Low stock, out-of-stock, and misplaced product alerts</p>

      <div className="flex gap-2 mb-4 flex-wrap">
        {SEVERITIES.map((s) => (
          <button
            key={s}
            onClick={() => setSeverity(s)}
            className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
              severity === s ? "bg-amber text-ink" : "bg-ink-light text-muted hover:bg-ink-lighter"
            }`}
          >
            {SEVERITY_LABELS[s]}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-3 rounded bg-rust/10 border border-rust text-rust text-sm">
          {error}
        </div>
      )}

      {alerts.length === 0 ? (
        <p className="text-muted text-sm">No active alerts.</p>
      ) : (
        <div className="space-y-2">
          {alerts.map((a) => (
            <AlertRow key={a.id} alert={a} onResolve={() => resolve(a.id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function AlertRow({ alert: a, onResolve }) {
  const config = {
    low: { tag: "tag-amber", icon: TrendingDown, label: `LOW STOCK - ${a.facings_detected} facing(s) detected` },
    empty: { tag: "tag-rust", icon: AlertTriangle, label: "OUT OF STOCK" },
    misplaced: { tag: "tag-amber", icon: ArrowLeftRight, label: a.message || "MISPLACED PRODUCT" },
  };
  const { tag, icon: Icon, label } = config[a.severity] || { tag: "tag-muted", icon: AlertTriangle, label: a.severity?.toUpperCase() };

  return (
    <div className={`shelf-tag ${tag} flex items-center justify-between p-4`}>
      <div className="flex items-center gap-3">
        <Icon size={20} className="text-muted flex-shrink-0" />
        <div>
          <p className="font-semibold">{a.product_class}</p>
          <p className="text-sm text-muted">{label}</p>
          <p className="text-xs text-muted">{new Date(a.timestamp).toLocaleString()}</p>
        </div>
      </div>
      <button
        onClick={onResolve}
        className="flex items-center gap-1 text-sm text-sage hover:text-sage px-3 py-1 rounded border border-sage/40 hover:bg-sage/10 flex-shrink-0"
      >
        <CheckCircle size={16} /> Resolve
      </button>
    </div>
  );
}
