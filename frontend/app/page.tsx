"use client";

// app/page.tsx
// Login page — the entry point of the application at localhost:3000.
// Calls POST /login via lib/api.ts → login() with the user's credentials.
// On success, saves the JWT token via saveToken() and redirects to /dashboard.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, saveToken } from "@/lib/api";
import { ShieldCheck } from "lucide-react";

export default function LoginPage() {

  // ── State ─────────────────────────────────────────────────────────────────
  // username/password: form field values submitted to POST /login
  // loading: disables button while the API call is in flight
  // error: shown below the form if credentials are rejected
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  // ── Router — used to redirect to /dashboard after successful login ────────
  // Next.js App Router hook — replaces window.location for client navigation
  const router = useRouter();

  // ── Handle login submission ───────────────────────────────────────────────
  // Calls POST /login via lib/api.ts → login(username, password)
  // Credentials are validated against DASHBOARD_USERNAME + DASHBOARD_PASSWORD
  // in api/dependencies.py — on success a signed JWT is returned
  const handleLogin = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await login(username, password);
      // Save JWT token to localStorage via saveToken() in lib/api.ts
      // All subsequent API calls will attach this as Authorization: Bearer <token>
      saveToken(response.access_token);
      router.push("/dashboard");
    } catch {
      setError("Invalid username or password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ── Handle Enter key — submits the form without a button click ────────────
  // Attached to the password field so the user can log in without the mouse
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleLogin();
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">

      {/* ── Login card ───────────────────────────────────────────────────── */}
      <div className="w-full max-w-md">

        {/* ── Branding ─────────────────────────────────────────────────────── */}
        {/* Shield icon + project name — establishes context before credentials */}
        {/* No data is sourced here — purely visual identity                   */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-blue-900/40 border border-blue-700 flex items-center justify-center mb-4 shadow-lg shadow-blue-900/30">
            <ShieldCheck size={28} className="text-blue-400" />
          </div>
          <h1 className="text-2xl font-black text-white tracking-tight">
            UAE Fraud Detection AI
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Sign in to access the dashboard
          </p>
        </div>

        {/* ── Form card ────────────────────────────────────────────────────── */}
        <div className="bg-gray-900 border border-gray-700 rounded-2xl p-8 shadow-xl">

          {/* ── Username field ──────────────────────────────────────────────── */}
          {/* Value compared against DASHBOARD_USERNAME in api/dependencies.py  */}
          <div className="mb-4">
            <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              autoComplete="username"
              className="w-full bg-gray-800 border border-gray-600 text-white rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-600 transition-colors"
            />
          </div>

          {/* ── Password field ──────────────────────────────────────────────── */}
          {/* Value compared against DASHBOARD_PASSWORD in api/dependencies.py  */}
          {/* Enter key triggers handleLogin so user doesn't need to click       */}
          <div className="mb-6">
            <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter password"
              autoComplete="current-password"
              className="w-full bg-gray-800 border border-gray-600 text-white rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-600 transition-colors"
            />
          </div>

          {/* ── Error message ───────────────────────────────────────────────── */}
          {/* Shown when POST /login returns 401 — wrong credentials            */}
          {error && (
            <div className="bg-red-900/40 border border-red-700 text-red-300 text-sm rounded-lg px-4 py-3 mb-5">
              {error}
            </div>
          )}

          {/* ── Submit button ───────────────────────────────────────────────── */}
          {/* Disabled while loading to prevent double submission               */}
          {/* On success: saveToken() + router.push("/dashboard")               */}
          <button
            onClick={handleLogin}
            disabled={loading || !username || !password}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-blue-900 disabled:text-blue-400 text-white font-semibold rounded-lg py-3 text-sm transition-colors"
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>

        </div>

        {/* ── Footer note ──────────────────────────────────────────────────── */}
        {/* Reminds the user where credentials come from — useful during dev    */}
        <p className="text-xs text-gray-600 text-center mt-4">
          Credentials are set in your <span className="font-mono text-gray-500">.env</span> file
        </p>

      </div>
    </div>
  );
}