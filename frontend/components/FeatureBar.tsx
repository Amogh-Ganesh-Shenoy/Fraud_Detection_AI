"use client";

// components/FeatureBar.tsx
// Pure display component — renders a horizontal bar chart of RF feature importances.
// Data flows from MetricsResponse.feature_importances fetched by the dashboard
// via GET /metrics, then passed down as a prop — no API calls made here.

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

// ── Props ─────────────────────────────────────────────────────────────────────
// importances: Record<string, number> — feature name → importance score (0.0–1.0)
// Sourced from MetricsResponse.feature_importances in api/main.py → get_metrics()
// Passed down from dashboard after getMetrics() resolves
interface FeatureBarProps {
  importances: Record<string, number>;
}

// ── Feature label map ─────────────────────────────────────────────────────────
// Converts snake_case keys from the API into readable display labels
// Keys match feature_importances keys in api/main.py exactly
const FEATURE_LABELS: Record<string, string> = {
  velocity_count:          "Transaction Velocity",
  amount_ratio:            "Amount vs Baseline",
  unusual_login_location:  "Unusual Login Location",
  vpn_flag:                "VPN Detected",
  hour_deviation:          "Login Hour Deviation",
  unusual_txn_location:    "Unusual Txn Location",
  login_txn_mismatch:      "Login / Txn Mismatch",
  new_device_flag:         "New Device",
};

// ── Bar colour by importance rank ─────────────────────────────────────────────
// Top 2 features get blue accent, next 2 get muted blue, rest get gray
// Visually groups features by contribution tier without overwhelming colour
const barColour = (index: number): string => {
  if (index < 2) return "#3b82f6";   // blue-500 — dominant features
  if (index < 4) return "#6366f1";   // indigo-500 — moderate features
  return "#374151";                  // gray-700 — minor features
};

// ── Custom tooltip ────────────────────────────────────────────────────────────
// Shows feature name + importance as a percentage on hover
// Recharts passes payload automatically when the bar is hovered
const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  return (
    <div className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-white font-medium mb-1">{item.label}</p>
      <p className="text-blue-400 font-mono">
        Importance: {(item.value * 100).toFixed(2)}%
      </p>
    </div>
  );
};

export default function FeatureBar({ importances }: FeatureBarProps) {

  // ── Transform importances into sorted chart data ──────────────────────────
  // Convert Record<string, number> to array, map to display labels,
  // sort highest → lowest importance so the most important feature is on top
  // Recharts reads `value` for bar length and `label` for the Y axis
  const chartData = Object.entries(importances)
    .map(([key, value]) => ({
      key,
      label: FEATURE_LABELS[key] ?? key,
      value,
    }))
    .sort((a, b) => b.value - a.value);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 shadow-xl">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      {/* Subtitle clarifies this is RF-specific — not an ensemble metric       */}
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-white tracking-tight">
          Feature Importances
        </h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Random Forest — contribution of each feature to fraud prediction
        </p>
      </div>

      {/* ── Horizontal Bar Chart ────────────────────────────────────────────── */}
      {/* layout="vertical" makes bars grow left→right with features on Y axis  */}
      {/* Height scales with number of features — 48px per bar for readability  */}
      <ResponsiveContainer width="100%" height={chartData.length * 48}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 0, right: 60, left: 0, bottom: 0 }}
          barCategoryGap="30%"
        >
          {/* Y axis — feature labels; width fixed to prevent truncation */}
          <YAxis
            dataKey="label"
            type="category"
            width={160}
            tick={{ fill: "#9ca3af", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />

          {/* X axis — importance values formatted as percentages */}
          <XAxis
            type="number"
            domain={[0, 1]}
            tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            tick={{ fill: "#6b7280", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />

          {/* Custom tooltip shown on bar hover */}
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "#1f2937" }} />

          {/* Bars — each coloured by rank tier; label shown at end of bar */}
          <Bar dataKey="value" radius={[0, 4, 4, 0]} label={{
            position: "right",
            formatter: (v: unknown) => typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "",
            fill: "#6b7280",
            fontSize: 11,
          }}>
            {chartData.map((_, index) => (
              <Cell key={index} fill={barColour(index)} />
            ))}
          </Bar>

        </BarChart>
      </ResponsiveContainer>

      {/* ── Colour tier legend ───────────────────────────────────────────────── */}
      {/* Explains the three colour tiers used to group features by contribution */}
      <div className="flex items-center gap-4 mt-4 pt-4 border-t border-gray-800">
        <p className="text-xs text-gray-600 mr-1">Contribution tier:</p>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm bg-blue-500" />
          <span className="text-xs text-gray-500">Dominant</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm bg-indigo-500" />
          <span className="text-xs text-gray-500">Moderate</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm bg-gray-700" />
          <span className="text-xs text-gray-500">Minor</span>
        </div>
      </div>

    </div>
  );
}