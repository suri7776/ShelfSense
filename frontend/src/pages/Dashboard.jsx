// src/pages/Dashboard.jsx
import React, { useState, useEffect } from "react";
import { Boxes, TrendingDown, AlertTriangle, HelpCircle, ArrowLeftRight } from "lucide-react";
import { apiGet } from "../services/api";

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [summaryRes, alertsRes] = await Promise.all([
          apiGet("/api/analytics/stock-summary"),
          apiGet("/api/alerts?limit=8&resolved=false"),
        ]);
        if (cancelled) return;

        setSummary(summaryRes.summary || null);
        setAlerts(Array.isArray(alertsRes.alerts) ? alertsRes.alerts : []);
        setError(null);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    const interval = setInterval(load, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  const products = summary?.products || [];
  const lowStockAlerts = alerts.filter((a) => a.severity === "low" || a.severity === "empty");
  const misplacedAlerts = alerts.filter((a) => a.severity === "misplaced");

  return (
    <div>
      <h1 className="font-display text-3xl font-bold mb-1">Dashboard</h1>
      <p className="text-muted mb-6">Real-time shelf monitoring overview</p>

      {error && (
        <div className="mb-4 p-3 rounded bg-rust/10 border border-rust text-rust text-sm">
          Could not reach backend: {error}. Make sure the FastAPI server is running on port 8000.
        </div>
      )}

      {loading ? (
        <p className="text-muted">Loading...</p>
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <StatCard icon={Boxes} label="Stocked" value={summary?.stocked ?? 0} tag="tag-sage" valueColor="text-sage" />
            <StatCard icon={TrendingDown} label="Low Stock" value={summary?.low_stock ?? 0} tag="tag-amber" valueColor="text-amber" />
            <StatCard icon={AlertTriangle} label="Out of Stock" value={summary?.out_of_stock ?? 0} tag="tag-rust" valueColor="text-rust" />
            <StatCard icon={HelpCircle} label="Uncalibrated" value={summary?.uncalibrated ?? 0} tag="tag-muted" valueColor="text-muted" />
          </div>

          {summary?.uncalibrated > 0 && (
            <div className="mb-6 p-4 rounded-lg bg-amber/10 border border-amber text-sand text-sm">
              {summary.uncalibrated} product(s) haven't been calibrated yet. Go to{" "}
              <a href="/planogram" className="underline font-semibold text-amber">Planogram</a> and upload a photo of the
              fully-stocked shelf to set ideal stock levels.
            </div>
          )}

          {/* Current stock levels */}
          <div className="bg-ink-light border border-ink-lighter rounded-lg p-5 mb-6">
            <h2 className="font-display text-lg font-semibold mb-4">Current Stock Levels</h2>
            {products.length === 0 ? (
              <p className="text-muted text-sm">No detections yet. Run a detection from Live Shelf or Upload.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted text-xs uppercase tracking-wider border-b border-ink-lighter">
                      <th className="py-2 pr-4 font-medium">Product</th>
                      <th className="py-2 pr-4 font-medium">Ideal Stock</th>
                      <th className="py-2 pr-4 font-medium">Current Count</th>
                      <th className="py-2 pr-4 font-medium">Percentage</th>
                      <th className="py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.map((p) => (
                      <tr key={p.name} className="border-b border-ink-lighter/50">
                        <td className="py-2.5 pr-4 font-medium">{p.name}</td>
                        <td className="py-2.5 pr-4 font-mono text-muted">{p.ideal_count || "—"}</td>
                        <td className="py-2.5 pr-4 font-mono">{p.current_count}</td>
                        <td className="py-2.5 pr-4 font-mono">
                          {p.percentage !== null ? `${p.percentage}%` : "—"}
                        </td>
                        <td className="py-2.5">
                          <StatusBadge status={p.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Low stock alerts */}
          <div className="bg-ink-light border border-ink-lighter rounded-lg p-5 mb-6">
            <h2 className="font-display text-lg font-semibold mb-3">Stock Alerts</h2>
            {lowStockAlerts.length === 0 ? (
              <p className="text-muted text-sm">No low-stock or out-of-stock alerts.</p>
            ) : (
              <div className="space-y-2">
                {lowStockAlerts.map((a) => (
                  <div key={a.id} className="shelf-tag tag-rust flex items-center justify-between px-4 py-2.5">
                    <div>
                      <p className="font-medium">{a.product_class}</p>
                      <p className="text-xs text-muted">{new Date(a.timestamp).toLocaleString()}</p>
                    </div>
                    <StatusBadge status={a.severity === "empty" ? "out_of_stock" : "low_stock"} />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Misplaced product alerts */}
          <div className="bg-ink-light border border-ink-lighter rounded-lg p-5">
            <h2 className="font-display text-lg font-semibold mb-3 flex items-center gap-2">
              <ArrowLeftRight size={18} /> Misplaced Products
            </h2>
            {misplacedAlerts.length === 0 ? (
              <p className="text-muted text-sm">No misplaced products detected.</p>
            ) : (
              <div className="space-y-2">
                {misplacedAlerts.map((a) => (
                  <div key={a.id} className="shelf-tag tag-amber flex items-center justify-between px-4 py-2.5">
                    <div>
                      <p className="font-medium">{a.message}</p>
                      <p className="text-xs text-muted">{new Date(a.timestamp).toLocaleString()}</p>
                    </div>
                    <span className="px-2 py-1 rounded text-xs font-semibold bg-amber/20 text-amber">
                      MISPLACED
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, tag, valueColor }) {
  return (
    <div className={`shelf-tag ${tag} p-4`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-muted text-xs uppercase tracking-wider font-medium">{label}</p>
          <p className={`font-mono text-3xl font-bold ${valueColor}`}>{value}</p>
        </div>
        <Icon className={valueColor} size={26} />
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const styles = {
    stocked: "bg-sage/20 text-sage",
    low_stock: "bg-amber/20 text-amber",
    out_of_stock: "bg-rust/20 text-rust",
    uncalibrated: "bg-muted/20 text-muted",
  };
  const labels = {
    stocked: "STOCKED",
    low_stock: "LOW STOCK",
    out_of_stock: "OUT OF STOCK",
    uncalibrated: "UNCALIBRATED",
  };
  return (
    <span className={`px-2 py-1 rounded text-xs font-semibold ${styles[status] || styles.uncalibrated}`}>
      {labels[status] || (status || "unknown").toUpperCase()}
    </span>
  );
}
