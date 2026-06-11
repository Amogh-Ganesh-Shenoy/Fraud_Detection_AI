"use client";

// components/GaugeChart.tsx
// Pure display component — renders a semicircle gauge for the ensemble_score.
// Receives score (0.0–1.0) and decision from dashboard state (sourced from
// POST /score → phase6/ensemble.py). No API calls or state management here.

import { RadialBarChart, RadialBar, ResponsiveContainer } from "recharts";
import { Decision } from "@/types";

// ── Props ─────────────────────────────────────────────────────────────────────
// score: ensemble_score from ScoreResponse — the weighted fraud probability (0.0–1.0)
// decision: final_decision from ScoreResponse — controls the gauge fill colour
interface GaugeChartProps {
  score:    number;
  decision: Decision;
}

// ── Decision colour map ───────────────────────────────────────────────────────
// Maps each Decision to a hex colour for the Recharts RadialBar fill
// Consistent with APPROVE=green, CHALLENGE=yellow, BLOCK=red convention
const DECISION_COLOUR: Record<Decision, string> = {
  APPROVE:   "#4ade80",   // green-400
  CHALLENGE: "#facc15",   // yellow-400
  BLOCK:     "#f87171",   // red-400
};

// ── Decision label styles ─────────────────────────────────────────────────────
// Tailwind classes for the decision label rendered below the score number
// Mirrors the badge classes used in ResultCard for visual consistency
const DECISION_LABEL: Record<Decision, string> = {
  APPROVE:   "text-green-400",
  CHALLENGE: "text-yellow-400",
  BLOCK:     "text-red-400",
};

// ── Threshold marker positions ────────────────────────────────────────────────
// APPROVE_MAX=0.30, CHALLENGE_MAX=0.45 from phase6/ensemble.py
// Rendered as small tick marks on the gauge track so the user can see
// where the decision boundaries sit relative to the current score
const THRESHOLDS = [
  { value: 0.30, label: "0.30" },
  { value: 0.45, label: "0.45" },
];

export default function GaugeChart({ score, decision }: GaugeChartProps) {

  // ── Gauge fill calculation ────────────────────────────────────────────────
  // Recharts RadialBarChart uses startAngle/endAngle to draw a semicircle arc.
  // We map the 180° semicircle (startAngle=180, endAngle=0) to the score range.
  // A score of 0.0 fills nothing; 1.0 fills the full semicircle.
  const fillColour  = DECISION_COLOUR[decision];
  const labelColour = DECISION_LABEL[decision];

  // ── Recharts data format ──────────────────────────────────────────────────
  // RadialBarChart expects an array — we pass two entries:
  // [0] background track (full arc, grey), [1] filled arc (score value)
  // The `value` field maps to the percentage of the arc to fill (0–100)
  const data = [
    { name: "track", value: 100, fill: "#1f2937" },   // gray-800 background ring
    { name: "score", value: score * 100, fill: fillColour },
  ];

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 shadow-xl flex flex-col items-center">

      {/* ── Title ──────────────────────────────────────────────────────────── */}
      <h2 className="text-lg font-semibold text-white tracking-tight mb-4">
        Risk Gauge
      </h2>

      {/* ── Gauge + centre label ────────────────────────────────────────────── */}
      {/* ResponsiveContainer fills parent width; height is fixed for semicircle */}
      {/* The centre label is absolutely positioned over the chart SVG          */}
      <div className="relative w-full" style={{ height: 200 }}>

        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="100%"
            innerRadius="60%"
            outerRadius="100%"
            startAngle={180}
            endAngle={0}
            data={data}
            barSize={18}
          >
            {/* Background track — always full 180° arc in gray */}
            <RadialBar dataKey="value" background={false} isAnimationActive={false} />
          </RadialBarChart>
        </ResponsiveContainer>

        {/* ── Centre overlay — score number + decision label ──────────────── */}
        {/* Positioned at the flat edge of the semicircle (bottom centre)      */}
        {/* score displayed as percentage; decision label colour-coded          */}
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-6">
          <p className={`text-4xl font-black tracking-tight ${labelColour}`}>
            {(score * 100).toFixed(1)}%
          </p>
          <p className={`text-xs font-bold uppercase tracking-widest mt-0.5 ${labelColour}`}>
            {decision}
          </p>
        </div>

      </div>

      {/* ── Threshold markers legend ────────────────────────────────────────── */}
      {/* Shows where APPROVE/CHALLENGE/BLOCK boundaries sit on the 0.0–1.0 scale */}
      {/* Values sourced from phase6/ensemble.py: APPROVE_MAX=0.30, CHALLENGE_MAX=0.45 */}
      <div className="flex justify-between w-full mt-4 px-2">
        <div className="text-center">
          <div className="w-2 h-2 rounded-full bg-green-400 mx-auto mb-1" />
          <p className="text-xs text-gray-500">0.00</p>
          <p className="text-xs text-green-500">APPROVE</p>
        </div>
        <div className="text-center">
          <div className="w-2 h-2 rounded-full bg-yellow-400 mx-auto mb-1" />
          <p className="text-xs text-gray-500">0.30</p>
          <p className="text-xs text-yellow-500">CHALLENGE</p>
        </div>
        <div className="text-center">
          <div className="w-2 h-2 rounded-full bg-red-400 mx-auto mb-1" />
          <p className="text-xs text-gray-500">0.45</p>
          <p className="text-xs text-red-500">BLOCK</p>
        </div>
      </div>

      {/* ── Score context line ──────────────────────────────────────────────── */}
      {/* Reminds the user what the number represents without them needing to   */}
      {/* cross-reference ResultCard — keeps the gauge self-contained           */}
      <p className="text-xs text-gray-600 mt-3 text-center">
        Weighted ensemble score · RF 35% · Rule 50% · Z-Score 15%
      </p>

    </div>
  );
}