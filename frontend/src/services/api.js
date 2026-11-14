// src/services/api.js
// Single source of truth for the backend URL.
// Backend always runs on port 8000 (python -m uvicorn backend.main:app --port 8000).
// Frontend (Vite) may pick 5173/5174/... if a port is busy - that's fine,
// it does NOT need to match the backend port.

export const API_BASE = "http://localhost:8000";

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

export async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

export async function apiPostFile(path, file, extraParams = {}) {
  const formData = new FormData();
  formData.append("file", file);

  const query = new URLSearchParams(extraParams).toString();
  const url = `${API_BASE}${path}${query ? `?${query}` : ""}`;

  const res = await fetch(url, { method: "POST", body: formData });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

export async function apiPut(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: "PUT" });
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`);
  return res.json();
}
