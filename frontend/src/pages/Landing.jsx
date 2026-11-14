// src/pages/Landing.jsx
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Boxes, ScanLine, BellRing, LayoutGrid, ArrowRight } from "lucide-react";

const FEATURES = [
  {
    icon: ScanLine,
    title: "Detects what's on the shelf",
    body: "Points a trained vision model at a shelf photo and reads off every product, facing by facing.",
  },
  {
    icon: LayoutGrid,
    title: "Knows what should be there",
    body: "A planogram holds the ideal layout. Change one value and every percentage on the dashboard updates with it.",
  },
  {
    icon: BellRing,
    title: "Flags what needs attention",
    body: "Low stock, empty slots, and products sitting in the wrong spot are surfaced as alerts the moment they happen.",
  },
];

export default function Landing() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleLogin = (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("Enter a username and password to continue.");
      return;
    }
    // Local-only auth for this build: any non-empty credentials work.
    localStorage.setItem("shelfsense_user", username.trim());
    navigate("/dashboard");
  };

  return (
    <div className="min-h-screen bg-ink text-paper font-body">
      {/* Hero */}
      <header className="px-6 md:px-12 pt-16 pb-12 md:pt-24 md:pb-20 max-w-6xl mx-auto">
        <div className="flex items-center gap-3 mb-10">
          <div className="w-9 h-9 rounded-md bg-amber flex items-center justify-center">
            <Boxes size={20} className="text-ink" />
          </div>
          <span className="font-display font-semibold text-lg tracking-tight">ShelfSense</span>
        </div>

        <div className="grid md:grid-cols-2 gap-12 items-start">
          <div>
            <h1 className="font-display text-4xl md:text-6xl font-bold leading-[1.05] mb-6">
              Know what's on your
              <br />
              shelf, <span className="text-amber">before</span> you
              <br />
              walk over to check.
            </h1>
            <p className="text-muted text-lg leading-relaxed max-w-md">
              ShelfSense reads shelf photos with a trained vision model, compares
              them against your planogram, and tells you exactly what's low,
              what's out, and what's in the wrong place.
            </p>
          </div>

          {/* Login card */}
          <div className="shelf-tag tag-amber p-6 md:p-8 md:max-w-sm md:ml-auto w-full">
            <p className="font-display text-sm uppercase tracking-widest text-amber mb-1">
              Sign in
            </p>
            <h2 className="font-display text-2xl font-semibold mb-6">Open the dashboard</h2>

            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-xs text-muted mb-1 font-medium">Username</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="shop owner"
                  className="w-full bg-ink border border-ink-lighter rounded px-3 py-2 text-paper
                             focus:outline-none focus:ring-2 focus:ring-amber placeholder:text-muted/60"
                />
              </div>
              <div>
                <label className="block text-xs text-muted mb-1 font-medium">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-ink border border-ink-lighter rounded px-3 py-2 text-paper
                             focus:outline-none focus:ring-2 focus:ring-amber placeholder:text-muted/60"
                />
              </div>

              {error && <p className="text-rust text-sm">{error}</p>}

              <button
                type="submit"
                className="w-full bg-amber hover:bg-amber-dark text-ink font-display font-semibold
                           py-2.5 rounded flex items-center justify-center gap-2 transition-colors"
              >
                Continue <ArrowRight size={18} />
              </button>
            </form>

            <p className="text-xs text-muted mt-4">
              Demo build - any username and password will do.
            </p>
          </div>
        </div>
      </header>

      {/* About / features */}
      <section className="px-6 md:px-12 py-16 border-t border-ink-lighter max-w-6xl mx-auto">
        <p className="font-display text-sm uppercase tracking-widest text-amber mb-2">
          How it works
        </p>
        <h2 className="font-display text-2xl md:text-3xl font-semibold mb-10 max-w-2xl">
          One photo of a shelf, three things ShelfSense does with it.
        </h2>

        <div className="grid md:grid-cols-3 gap-5">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <div key={title} className="shelf-tag tag-sage p-5">
              <Icon className="text-sage mb-3" size={24} />
              <h3 className="font-display font-semibold text-base mb-2">{title}</h3>
              <p className="text-muted text-sm leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="px-6 md:px-12 py-8 border-t border-ink-lighter max-w-6xl mx-auto text-xs text-muted">
        ShelfSense - AI shelf monitoring · Major Project, B.Tech CS (AIML)
      </footer>
    </div>
  );
}
