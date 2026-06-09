"use client";

// app/dashboard/page.tsx
// Main application view — rendered after successful login at /dashboard.
// Orchestrates all components, holds shared state, and passes data down.
// On mount: verifies JWT token exists and fetches metrics for the Analytics tab.

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken, clearToken, getMetrics } from "@/lib/api";
import { ScoreResponse, MetricsResponse } from "@/types";
import { ShieldCheck, LogOut, BarChart2, Zap } from "lucide-react";

// ── Component imports — all built in Phase 7 ──────────────────────────────────
// Each component is self-contained; dashboard wires them together via props
// ProfileCard removed — ScoreForm already displays the baseline profile inline
import ScoreForm    from "@/components/ScoreForm";
import ResultCard   from "@/components/ResultCard";
import GaugeChart   from "@/components/GaugeChart";
import AlertTable   from "@/components/AlertTable";
import MetricsPanel from "@/components/MetricsPanel";
import FeatureBar   from "@/components/FeatureBar";

// ── Tab type ──────────────────────────────────────────────────────────────────
// Controls which tab panel is visible — Score (play mode) or Analytics
type Tab = "score" | "analytics";

export default function DashboardPage() {

  // ── Router — used for redirect on missing token or logout ─────────────────
  const router = useRouter();

  // ── Shared state ──────────────────────────────────────────────────────────
  // result: populated by ScoreForm via onResult() — passed to ResultCard + GaugeChart
  // metrics: fetched on mount from GET /metrics — passed to FeatureBar
  // profile state removed — ScoreForm handles profile display internally
  const [result,    setResult]    = useState<ScoreResponse | null>(null);
  const [metrics,   setMetrics]   = useState<MetricsResponse | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("score");

  // ── Auth check + metrics fetch on mount ───────────────────────────────────
  // Redirects to login if no token found — protects the dashboard route
  // Also pre-fetches metrics so FeatureBar and MetricsPanel load instantly
  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/");
      return;
    }

    // Fetch metrics once on mount — passed as prop to FeatureBar
    // MetricsPanel fetches its own data internally
    getMetrics()
      .then(setMetrics)
      .catch(() => console.error("Failed to load metrics on dashboard mount."));
  }, []);

  // ── Logout handler ────────────────────────────────────────────────────────
  // Clears the JWT token from localStorage via clearToken() in lib/api.ts
  // then redirects back to the login page at /
  const handleLogout = () => {
    clearToken();
    router.push("/");
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-950 text-white">

      {/* ── Top navigation bar ───────────────────────────────────────────── */}
      {/* Contains branding on the left and logout button on the right       */}
      {/* Sticky at the top — content scrolls beneath it                     */}
      <header className="sticky top-0 z-10 bg-gray-900 border-b border-gray-700 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">

          {/* Branding */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-900/40 border border-blue-700 flex items-center justify-center">
              <ShieldCheck size={16} className="text-blue-400" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-white tracking-tight leading-none">
                UAE Fraud Detection AI
              </h1>
              <p className="text-xs text-gray-500 mt-0.5">Phase 7 Dashboard</p>
            </div>
          </div>

          {/* Logout button — calls clearToken() + redirects to / */}
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg px-4 py-2 transition-colors"
          >
            <LogOut size={14} />
            Logout
          </button>

        </div>
      </header>

      {/* ── Tab bar ──────────────────────────────────────────────────────── */}
      {/* Score tab: play mode — submit transactions and see results          */}
      {/* Analytics tab: model metrics, alert history, feature importances    */}
      <div className="bg-gray-900 border-b border-gray-700 px-6">
        <div className="max-w-7xl mx-auto flex gap-1">

          {/* Score tab */}
          <button
            onClick={() => setActiveTab("score")}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "score"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            <Zap size={14} />
            Score
          </button>

          {/* Analytics tab */}
          <button
            onClick={() => setActiveTab("analytics")}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "analytics"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            <BarChart2 size={14} />
            Analytics
          </button>

        </div>
      </div>

      {/* ── Main content area ─────────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-6 py-6">

        {/* ════════════════════════════════════════════════════════════════ */}
        {/* SCORE TAB                                                        */}
        {/* Left column: ScoreForm only                                      */}
        {/* Right column: GaugeChart + ResultCard (shown after first score)  */}
        {/* ════════════════════════════════════════════════════════════════ */}
        {activeTab === "score" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* ── Left column ──────────────────────────────────────────── */}
            {/* ScoreForm is self-contained — handles user selection,        */}
            {/* baseline profile display, and scoring internally             */}
            <div className="flex flex-col gap-6">
              <ScoreForm
                onResult={setResult}
                onProfile={() => {}}
              />
            </div>

            {/* ── Right column ─────────────────────────────────────────── */}
            {/* Empty state shown before first score — guides the user       */}
            {/* GaugeChart + ResultCard appear once result is available      */}
            <div className="flex flex-col gap-6">
              {result ? (
                <>
                  {/* GaugeChart — semicircle showing ensemble_score        */}
                  {/* score + decision sourced from ScoreResponse            */}
                  <GaugeChart
                    score={result.ensemble_score}
                    decision={result.final_decision}
                  />

                  {/* ResultCard — full breakdown of all model outputs       */}
                  {/* receives the complete ScoreResponse object             */}
                  <ResultCard result={result} />
                </>
              ) : (
                // ── Empty state — shown before any transaction is scored ──
                // Guides the user to fill in the form on the left
                <div className="flex flex-col items-center justify-center h-full min-h-64 bg-gray-900 border border-dashed border-gray-700 rounded-2xl p-8 text-center">
                  <div className="w-12 h-12 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center mb-4">
                    <Zap size={20} className="text-gray-600" />
                  </div>
                  <p className="text-gray-500 font-medium mb-1">
                    No result yet
                  </p>
                  <p className="text-sm text-gray-600">
                    Fill in the transaction form and click{" "}
                    <span className="text-gray-400">Run Ensemble Score</span>{" "}
                    to see results here.
                  </p>
                </div>
              )}
            </div>

          </div>
        )}

        {/* ════════════════════════════════════════════════════════════════ */}
        {/* ANALYTICS TAB                                                    */}
        {/* AlertTable: full width at top                                    */}
        {/* MetricsPanel + FeatureBar: side by side below                   */}
        {/* ════════════════════════════════════════════════════════════════ */}
        {activeTab === "analytics" && (
          <div className="flex flex-col gap-6">

            {/* AlertTable — fetches its own data from GET /alerts           */}
            {/* Displays 10 most recent alerts from the alerts table         */}
            <AlertTable />

            {/* Bottom row — MetricsPanel and FeatureBar side by side        */}
            {/* MetricsPanel fetches its own data from GET /metrics          */}
            {/* FeatureBar receives feature_importances from dashboard state  */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

              <MetricsPanel />

              {/* FeatureBar only renders once metrics have loaded           */}
              {/* feature_importances sourced from MetricsResponse on mount  */}
              {metrics ? (
                <FeatureBar importances={metrics.feature_importances} />
              ) : (
                <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 flex items-center justify-center min-h-48">
                  <p className="text-sm text-gray-600">Loading feature importances...</p>
                </div>
              )}

            </div>

          </div>
        )}

      </main>

    </div>
  );
}