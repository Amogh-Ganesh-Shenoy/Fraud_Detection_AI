"use client";

// components/MetricsPanel.tsx
// Fetches and displays evaluation metrics for all 4 models from GET /metrics.
// Data flows from the static values in api/main.py → get_metrics() which
// returns phase5, zscore, random_forest, and ensemble ModelMetrics objects.

import { useState, useEffect } from "react";
import { getMetrics } from "@/lib/api";
import { MetricsResponse, ModelMetrics } from "@/types";

// ── Model row definitions ─────────────────────────────────────────────────────
// Defines display order, labels, and which rows to highlight as best performers
// Keys match the MetricsResponse fields returned by GET /metrics
const MODEL_ROWS: {
  key:       keyof Omit<MetricsResponse, "feature_importances">;
  label:     string;
  highlight: boolean;
}[] = [
  { key: "phase5",        label: "Phase 5 — Rule Engine", highlight: false },
  { key: "zscore",        label: "Z-Score Anomaly",        highlight: false },
  { key: "random_forest", label: "Random Forest",          highlight: true  },
  { key: "ensemble",      label: "Ensemble (Final)",       highlight: true  },
];

// ── Metric formatter ──────────────────────────────────────────────────────────
// Converts 0.0–1.0 metric values to percentage strings for display
// AUC is optional (null for Z-Score and Ensemble) — rendered as "—" if absent
const fmtMetric = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return "—";
  return `${(val * 100).toFixed(1)}%`;
};

// ── Metric cell colour ────────────────────────────────────────────────────────
// Colour-codes each metric value based on performance thresholds
// Green ≥ 90%, Yellow ≥ 70%, Red < 70% — helps identify weak models at a glance
const metricColour = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return "text-gray-500";
  if (val >= 0.90) return "text-green-400";
  if (val >= 0.70) return "text-yellow-400";
  return "text-red-400";
};

export default function MetricsPanel() {

  // ── State ─────────────────────────────────────────────────────────────────
  // metrics: full MetricsResponse from GET /metrics — contains all 4 models
  // loading/error: UX feedback while the fetch is in progress
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  // ── Fetch metrics on mount ────────────────────────────────────────────────
  // Calls GET /metrics via lib/api.ts → getMetrics()
  // Returns static evaluation results from phase5 batch sim + phase6 models
  // feature_importances is also in the response but used by FeatureBar, not here
  useEffect(() => {
    getMetrics()
      .then((data) => {
        setMetrics(data);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load metrics.");
        setLoading(false);
      });
  }, []);

  // ── Loading state ─────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-white mb-4 tracking-tight">
          Model Performance
        </h2>
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-10 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────────────────────
  if (error || !metrics) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-white mb-4 tracking-tight">
          Model Performance
        </h2>
        <div className="bg-red-900/40 border border-red-700 text-red-300 text-sm rounded-lg px-4 py-3">
          {error ?? "No metrics available."}
        </div>
      </div>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 shadow-xl">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      {/* Subtitle reminds the user these are offline evaluation results        */}
      {/* not live scores — sourced from phase5 batch sim + phase6 evaluation   */}
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-white tracking-tight">
          Model Performance
        </h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Evaluated on the full UAE transaction dataset
        </p>
      </div>

      {/* ── Metrics Table ───────────────────────────────────────────────────── */}
      {/* Four rows — one per model; RF and Ensemble rows highlighted in blue   */}
      {/* Columns: Model, Precision, Recall, F1, AUC                            */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">

          {/* ── Column headers ───────────────────────────────────────────── */}
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left text-xs text-gray-500 uppercase tracking-wider pb-3 pr-4">
                Model
              </th>
              <th className="text-right text-xs text-gray-500 uppercase tracking-wider pb-3 pr-4">
                Precision
              </th>
              <th className="text-right text-xs text-gray-500 uppercase tracking-wider pb-3 pr-4">
                Recall
              </th>
              <th className="text-right text-xs text-gray-500 uppercase tracking-wider pb-3 pr-4">
                F1
              </th>
              <th className="text-right text-xs text-gray-500 uppercase tracking-wider pb-3">
                AUC
              </th>
            </tr>
          </thead>

          {/* ── Model rows ───────────────────────────────────────────────── */}
          {/* highlight=true rows get a subtle blue left border + bg tint     */}
          {/* to visually distinguish the best performing models              */}
          <tbody className="divide-y divide-gray-800">
            {MODEL_ROWS.map(({ key, label, highlight }) => {
              const m = metrics[key] as ModelMetrics;

              return (
                <tr
                  key={key}
                  className={`transition-colors ${
                    highlight
                      ? "bg-blue-950/20 hover:bg-blue-950/40"
                      : "hover:bg-gray-800/50"
                  }`}
                >

                  {/* Model name — highlighted rows get a blue left border */}
                  <td className={`py-3 pr-4 ${highlight ? "border-l-2 border-blue-500 pl-3" : ""}`}>
                    <span className={`font-medium ${highlight ? "text-white" : "text-gray-400"}`}>
                      {label}
                    </span>
                    {highlight && (
                      <span className="ml-2 text-xs text-blue-400 bg-blue-900/40 border border-blue-700 px-2 py-0.5 rounded-full">
                        best
                      </span>
                    )}
                  </td>

                  {/* Precision — colour coded by threshold */}
                  <td className={`py-3 pr-4 text-right font-mono font-semibold ${metricColour(m.precision)}`}>
                    {fmtMetric(m.precision)}
                  </td>

                  {/* Recall — colour coded by threshold */}
                  <td className={`py-3 pr-4 text-right font-mono font-semibold ${metricColour(m.recall)}`}>
                    {fmtMetric(m.recall)}
                  </td>

                  {/* F1 — colour coded by threshold */}
                  <td className={`py-3 pr-4 text-right font-mono font-semibold ${metricColour(m.f1)}`}>
                    {fmtMetric(m.f1)}
                  </td>

                  {/* AUC — optional; Z-Score and Ensemble return null */}
                  <td className={`py-3 text-right font-mono font-semibold ${metricColour(m.auc)}`}>
                    {fmtMetric(m.auc)}
                  </td>

                </tr>
              );
            })}
          </tbody>

        </table>
      </div>

      {/* ── Legend ──────────────────────────────────────────────────────────── */}
      {/* Explains the colour coding so the table is self-explanatory           */}
      {/* Thresholds chosen to match typical ML performance benchmarks          */}
      <div className="flex items-center gap-4 mt-5 pt-4 border-t border-gray-800">
        <p className="text-xs text-gray-600 mr-1">Colour scale:</p>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-green-400" />
          <span className="text-xs text-gray-500">≥ 90%</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-yellow-400" />
          <span className="text-xs text-gray-500">≥ 70%</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-red-400" />
          <span className="text-xs text-gray-500">&lt; 70%</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-gray-500" />
          <span className="text-xs text-gray-500">N/A</span>
        </div>
      </div>

    </div>
  );
}