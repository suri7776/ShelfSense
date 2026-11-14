// src/App.jsx
import React from "react";
import { BrowserRouter, Routes, Route, NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Camera,
  UploadCloud,
  Bell,
  LayoutGrid,
  Settings as SettingsIcon,
  Boxes,
  LogOut,
} from "lucide-react";

import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import LiveShelf from "./pages/LiveShelf";
import Upload from "./pages/Upload";
import Alerts from "./pages/Alerts";
import Planogram from "./pages/Planogram";
import SettingsPage from "./pages/Settings";
import RequireAuth from "./components/RequireAuth";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/live", label: "Live Shelf", icon: Camera },
  { to: "/upload", label: "Upload", icon: UploadCloud },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/planogram", label: "Planogram", icon: LayoutGrid },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

function Sidebar() {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("shelfsense_user");
    navigate("/");
  };

  return (
    <nav className="flex md:flex-col md:w-60 md:h-screen bg-ink-light border-r border-ink-lighter md:fixed top-0 left-0
                     fixed bottom-0 left-0 right-0 md:bottom-auto justify-around md:justify-start z-20">
      <div className="hidden md:flex items-center gap-2 px-5 pt-6 pb-8">
        <div className="w-8 h-8 rounded-md bg-amber flex items-center justify-center">
          <Boxes size={18} className="text-ink" />
        </div>
        <div>
          <h1 className="font-display font-semibold text-base leading-tight">ShelfSense</h1>
          <p className="text-xs text-muted">AI Shelf Monitor</p>
        </div>
      </div>

      <div className="md:px-3 md:flex-1 flex md:flex-col w-full justify-around md:justify-start md:gap-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `relative flex flex-col md:flex-row items-center gap-1 md:gap-3 px-3 py-2.5 md:rounded-md text-xs md:text-sm
               font-medium transition-colors ${
                isActive
                  ? "text-ink bg-amber md:before:hidden"
                  : "text-muted hover:text-paper hover:bg-ink-lighter"
              }`
            }
          >
            <Icon size={20} />
            <span>{label}</span>
          </NavLink>
        ))}
      </div>

      <div className="hidden md:block px-3 pb-6 mt-auto">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium
                     text-muted hover:text-paper hover:bg-ink-lighter transition-colors"
        >
          <LogOut size={18} />
          <span>Log out</span>
        </button>
      </div>
    </nav>
  );
}

function AppLayout({ children }) {
  return (
    <div className="min-h-screen bg-ink text-paper font-body">
      <Sidebar />
      <main className="md:ml-60 p-4 md:p-8 pb-20 md:pb-8">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route
          path="/dashboard"
          element={<RequireAuth><AppLayout><Dashboard /></AppLayout></RequireAuth>}
        />
        <Route
          path="/live"
          element={<RequireAuth><AppLayout><LiveShelf /></AppLayout></RequireAuth>}
        />
        <Route
          path="/upload"
          element={<RequireAuth><AppLayout><Upload /></AppLayout></RequireAuth>}
        />
        <Route
          path="/alerts"
          element={<RequireAuth><AppLayout><Alerts /></AppLayout></RequireAuth>}
        />
        <Route
          path="/planogram"
          element={<RequireAuth><AppLayout><Planogram /></AppLayout></RequireAuth>}
        />
        <Route
          path="/settings"
          element={<RequireAuth><AppLayout><SettingsPage /></AppLayout></RequireAuth>}
        />
      </Routes>
    </BrowserRouter>
  );
}
