// src/components/RequireAuth.jsx
import React from "react";
import { Navigate } from "react-router-dom";

export default function RequireAuth({ children }) {
  const user = localStorage.getItem("shelfsense_user");
  if (!user) {
    return <Navigate to="/" replace />;
  }
  return children;
}
