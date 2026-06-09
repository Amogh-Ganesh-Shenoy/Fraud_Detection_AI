"use client";

// components/ProfileCard.tsx
// Pure display component — renders the selected user's behavioral baseline.
// Data flows from GET /users/{user_id}/profile → ScoreForm → onProfile()
// callback → dashboard state → passed down here as a prop. No API calls made.

import { UserProfile } from "@/types";
import { User, MapPin, Monitor, Clock } from "lucide-react";

// ── Props ─────────────────────────────────────────────────────────────────────
// profile: UserProfile — behavioral baseline from behavior_profiles table
// Built by Phase 1 generate_behavior_profiles() from historical transaction data
interface ProfileCardProps {
  profile: UserProfile;
}

// ── Login hour formatter ──────────────────────────────────────────────────────
// Converts the typical_login_hour integer (0–23) to a readable 12-hour format
// e.g. 14 → "2:00 PM", 9 → "9:00 AM"
const formatHour = (hour: number): string => {
  const period = hour >= 12 ? "PM" : "AM";
  const h      = hour % 12 === 0 ? 12 : hour % 12;
  return `${h}:00 ${period}`;
};

// ── Profile field definitions ─────────────────────────────────────────────────
// Each field has an icon, label, and a value formatter function
// Keeps the render section clean — add new fields here without touching JSX
const PROFILE_FIELDS = (profile: UserProfile) => [
  {
    icon:  <MapPin size={14} className="text-blue-400" />,
    label: "Usual Location",
    value: profile.usual_location,
  },
  {
    icon:  <Monitor size={14} className="text-blue-400" />,
    label: "Typical Device",
    value: profile.typical_device.charAt(0).toUpperCase() + profile.typical_device.slice(1),
  },
  {
    icon:  <Clock size={14} className="text-blue-400" />,
    label: "Typical Login",
    value: formatHour(profile.typical_login_hour),
  },
];

export default function ProfileCard({ profile }: ProfileCardProps) {

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 shadow-xl">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      {/* Icon + title make it clear this is user-specific context             */}
      {/* not a transaction result — helps distinguish from ResultCard          */}
      <div className="flex items-center gap-2 mb-5">
        <div className="w-8 h-8 rounded-full bg-blue-900/40 border border-blue-700 flex items-center justify-center">
          <User size={14} className="text-blue-400" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-white tracking-tight leading-none">
            User Baseline
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Behavioral profile from historical transactions
          </p>
        </div>
      </div>

      {/* ── Avg Transaction Amount — primary metric ───────────────────────── */}
      {/* Displayed prominently as the most decision-relevant baseline value   */}
      {/* Sourced from behavior_profiles.avg_transaction_amount (Phase 1)      */}
      <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 mb-4">
        <p className="text-xs text-gray-500 uppercase tracking-widest mb-1">
          Avg Transaction Amount
        </p>
        <p className="text-2xl font-black text-white tracking-tight">
          AED{" "}
          <span className="text-blue-400">
            {profile.avg_transaction_amount.toLocaleString("en-AE", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </span>
        </p>
        <p className="text-xs text-gray-600 mt-1">
          HIGH_AMOUNT rule fires if transaction exceeds 1.5× this value
        </p>
      </div>

      {/* ── Remaining profile fields ─────────────────────────────────────── */}
      {/* Location, device, login hour — each with an icon and label          */}
      {/* Values sourced from behavior_profiles table built in Phase 1         */}
      <div className="space-y-3">
        {PROFILE_FIELDS(profile).map(({ icon, label, value }) => (
          <div
            key={label}
            className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0"
          >
            <div className="flex items-center gap-2">
              {icon}
              <span className="text-xs text-gray-500 uppercase tracking-wider">
                {label}
              </span>
            </div>
            <span className="text-sm text-white font-medium">
              {value}
            </span>
          </div>
        ))}
      </div>

      {/* ── Context note ────────────────────────────────────────────────────── */}
      {/* Reminds the user that deviations from this profile trigger risk rules */}
      {/* Connects the profile data to the scoring logic in phase3/risk_engine  */}
      <p className="text-xs text-gray-600 mt-4 pt-3 border-t border-gray-800">
        Deviations from this baseline trigger risk rules in the scoring engine.
      </p>

    </div>
  );
}