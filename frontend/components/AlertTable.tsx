"use client";

// components/AlertTable.tsx
// Fetches and displays the 10 most recent fraud alerts from GET /alerts.
// Data flows from alerts + transactions tables in SQLite via api/main.py,
// returned as AlertSummary[] and rendered as a colour-coded table.

import { useState, useEffect } from "react";
import { getAlerts } from "@/lib/api";
import { AlertSummary, Decision } from "@/types";

// ── Decision badge styles ─────────────────────────────────────────────────────
// Maps decision string to Tailwind classes — consistent with project convention
// APPROVE=green, CHALLENGE=yellow, BLOCK=red (matches ResultCard + GaugeChart)
const DECISION_STYLES: Record<string, string> = {
  APPROVE:   "text-green-400 bg-green-900/40 border-green-700",
  CHALLENGE: "text-yellow-400 bg-yellow-900/40 border-yellow-700",
  BLOCK:     "text-red-400 bg-red-900/40 border-red-700",
};

// ── Timestamp formatter ───────────────────────────────────────────────────────
// Converts ISO timestamp string from alerts.timestamp to a readable format
// e.g. "2024-01-15T14:32:00" → "15 Jan 2024, 14:32"
const formatTimestamp = (ts: string): string => {
  try {
    const date = new Date(ts);
    return date.toLocaleString("en-GB", {
      day:    "2-digit",
      month:  "short",
      year:   "numeric",
      hour:   "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return ts;
  }
};

export default function AlertTable() {

  // ── State ─────────────────────────────────────────────────────────────────
  // alerts: AlertSummary[] fetched from GET /alerts on mount
  // loading/error: UX feedback while data is being fetched
  const [alerts, setAlerts]   = useState<AlertSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  // ── Fetch alerts on mount ─────────────────────────────────────────────────
  // Calls GET /alerts via lib/api.ts → getAlerts(10)
  // Joins alerts + transactions tables — returns risk_score, decision,
  // reason_codes (comma-space string), timestamp, amount, merchant, location
  useEffect(() => {
    getAlerts(10)
      .then((data) => {
        setAlerts(data);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load alerts.");
        setLoading(false);
      });
  }, []);

  // ── Loading state ─────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-white mb-4 tracking-tight">
          Recent Alerts
        </h2>
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="h-10 bg-gray-800 rounded-lg animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-white mb-4 tracking-tight">
          Recent Alerts
        </h2>
        <div className="bg-red-900/40 border border-red-700 text-red-300 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      </div>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 shadow-xl">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      {/* Alert count shown alongside title so user knows how many loaded      */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold text-white tracking-tight">
          Recent Alerts
        </h2>
        <span className="text-xs text-gray-500 bg-gray-800 border border-gray-700 px-3 py-1 rounded-full">
          {alerts.length} alerts
        </span>
      </div>

      {/* ── Empty state ─────────────────────────────────────────────────────── */}
      {alerts.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-8">
          No alerts found. Run a transaction in the Score tab to generate one.
        </p>
      ) : (

        // ── Table ────────────────────────────────────────────────────────────
        // Horizontally scrollable on small screens — overflow-x-auto
        // Each row sourced from AlertSummary: one row per alert record
        <div className="overflow-x-auto">
          <table className="w-full text-sm">

            {/* ── Column headers ─────────────────────────────────────────── */}
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left text-xs text-gray-500 uppercase tracking-wider pb-3 pr-4">
                  Timestamp
                </th>
                <th className="text-left text-xs text-gray-500 uppercase tracking-wider pb-3 pr-4">
                  Merchant
                </th>
                <th className="text-right text-xs text-gray-500 uppercase tracking-wider pb-3 pr-4">
                  Amount (AED)
                </th>
                <th className="text-left text-xs text-gray-500 uppercase tracking-wider pb-3 pr-4">
                  Location
                </th>
                <th className="text-center text-xs text-gray-500 uppercase tracking-wider pb-3 pr-4">
                  Decision
                </th>
                <th className="text-right text-xs text-gray-500 uppercase tracking-wider pb-3 pr-4">
                  Risk Score
                </th>
                <th className="text-left text-xs text-gray-500 uppercase tracking-wider pb-3">
                  Reason Codes
                </th>
              </tr>
            </thead>

            {/* ── Table rows — one per AlertSummary ──────────────────────── */}
            {/* reason_codes is a comma-space string from risk_engine.py      */}
            {/* split on ", " to render each code as an individual badge      */}
            <tbody className="divide-y divide-gray-800">
              {alerts.map((alert, index) => {

                // Split comma-space separated reason_codes string into array
                // e.g. "VPN_DETECTED, HIGH_AMOUNT" → ["VPN_DETECTED", "HIGH_AMOUNT"]
                const codes = alert.reason_codes
                  ? alert.reason_codes.split(", ").filter(Boolean)
                  : [];

                // Resolve badge style — fallback to gray if decision is unexpected
                const badgeStyle =
                  DECISION_STYLES[alert.decision] ??
                  "text-gray-400 bg-gray-800 border-gray-600";

                return (
                  <tr
                    key={index}
                    className="hover:bg-gray-800/50 transition-colors"
                  >

                    {/* Timestamp — formatted from ISO string */}
                    <td className="py-3 pr-4 text-gray-400 text-xs whitespace-nowrap font-mono">
                      {formatTimestamp(alert.timestamp)}
                    </td>

                    {/* Merchant name */}
                    <td className="py-3 pr-4 text-white font-medium whitespace-nowrap">
                      {alert.merchant}
                    </td>

                    {/* Amount — right-aligned, formatted with commas */}
                    <td className="py-3 pr-4 text-white text-right whitespace-nowrap font-mono">
                      {alert.amount.toLocaleString("en-AE", {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </td>

                    {/* Transaction location */}
                    <td className="py-3 pr-4 text-gray-300 whitespace-nowrap">
                      {alert.location}
                    </td>

                    {/* Decision badge — colour-coded pill */}
                    <td className="py-3 pr-4 text-center">
                      <span
                        className={`text-xs font-bold px-3 py-1 rounded-full border uppercase tracking-wider ${badgeStyle}`}
                      >
                        {alert.decision}
                      </span>
                    </td>

                    {/* Risk score — right-aligned integer */}
                    <td className="py-3 pr-4 text-right">
                      <span className="text-white font-mono font-semibold">
                        {alert.risk_score.toFixed(0)}
                      </span>
                    </td>

                    {/* Reason codes — each code as a small grey badge */}
                    <td className="py-3">
                      <div className="flex flex-wrap gap-1">
                        {codes.length > 0 ? (
                          codes.map((code, i) => (
                            <span
                              key={i}
                              className="text-xs px-2 py-0.5 rounded-full bg-gray-800 border border-gray-600 text-gray-400 whitespace-nowrap"
                            >
                              {code}
                            </span>
                          ))
                        ) : (
                          <span className="text-gray-600 text-xs">—</span>
                        )}
                      </div>
                    </td>

                  </tr>
                );
              })}
            </tbody>

          </table>
        </div>
      )}

    </div>
  );
}