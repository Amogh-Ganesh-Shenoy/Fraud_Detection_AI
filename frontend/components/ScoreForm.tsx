"use client";

// components/ScoreForm.tsx
// Interactive play mode form — user fills in transaction details and submits
// for full ensemble scoring. Calls POST /score via lib/api.ts → scoreTransaction().
// On success, passes the ScoreResponse up to the parent dashboard via onResult().

import { useState, useEffect } from "react";
import { getUsers, getUserProfile, scoreTransaction } from "@/lib/api";
import { UserSummary, UserProfile, ScoreRequest, ScoreResponse } from "@/types";

// ── Props ─────────────────────────────────────────────────────────────────────
// onResult: callback to parent dashboard — passes ScoreResponse up when scoring completes
// onProfile: callback to parent dashboard — passes UserProfile when user is selected
interface ScoreFormProps {
  onResult:  (result: ScoreResponse) => void;
  onProfile: (profile: UserProfile) => void;
}

// ── Transaction type options — mirrors transaction_type values in transactions table
const TRANSACTION_TYPES = [
  "online_purchase",
  "in_store",
  "bank_transfer",
  "atm_withdrawal",
  "bill_payment",
];

// ── Device type options — mirrors device_type values in sessions table
const DEVICE_TYPES = ["iPhone", "Android", "MacBook", "Windows PC", "iPad"];

export default function ScoreForm({ onResult, onProfile }: ScoreFormProps) {

  // ── State ──────────────────────────────────────────────────────────────────
  // Users list for the dropdown — fetched from GET /users on mount
  const [users, setUsers]           = useState<UserSummary[]>([]);
  // Selected user's behavioral profile — fetched when user changes
  const [profile, setProfile]       = useState<UserProfile | null>(null);
  // Loading and error states for UX feedback
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [submitted, setSubmitted]   = useState(false);

  // ── Form fields — mirrors ScoreRequest in types/index.ts ──────────────────
  const [formData, setFormData] = useState<ScoreRequest>({
    user_id:          "",
    amount:           0,
    merchant:         "",
    transaction_type: "online_purchase",
    location:         "",
    device_type:      "mobile",
    login_location:   "",
    vpn_detected:     false,
  });

  // ── Fetch users on mount — populates the user dropdown ────────────────────
  // Calls GET /users via lib/api.ts → getUsers()
  // Pulls user_id, full_name, city from users table
  useEffect(() => {
    getUsers()
      .then(setUsers)
      .catch(() => setError("Failed to load users."));
  }, []);

  // ── Fetch user profile when user_id changes ───────────────────────────────
  // Calls GET /users/{user_id}/profile via lib/api.ts → getUserProfile()
  // Pulls avg_transaction_amount, usual_location, typical_device, typical_login_hour
  // from behavior_profiles table and passes it up to parent via onProfile()
  useEffect(() => {
    if (!formData.user_id) return;
    getUserProfile(formData.user_id)
      .then((p) => {
        setProfile(p);
        onProfile(p);
      })
      .catch(() => setProfile(null));
  }, [formData.user_id]);

  // ── Handle text/select/number input changes ───────────────────────────────
  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      // Checkbox needs special handling — checked not value
      [name]: type === "checkbox"
        ? (e.target as HTMLInputElement).checked
        : type === "number"
        ? parseFloat(value) || 0
        : value,
    }));
  };

  // ── Handle form submission ────────────────────────────────────────────────
  // Calls POST /score via lib/api.ts → scoreTransaction()
  // Internally calls phase2/ingest.py and phase6/ensemble.py via api/main.py
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await scoreTransaction(formData);
      onResult(result);
      setSubmitted(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Scoring failed.");
    } finally {
      setLoading(false);
    }
  };

  // ── Reset form for a new transaction ─────────────────────────────────────
  const handleReset = () => {
    setSubmitted(false);
    setError(null);
    setFormData({
      user_id:          formData.user_id,
      amount:           0,
      merchant:         "",
      transaction_type: "online_purchase",
      location:         "",
      device_type:      "mobile",
      login_location:   "",
      vpn_detected:     false,
    });
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 shadow-xl">
      <h2 className="text-lg font-semibold text-white mb-1 tracking-tight">
        Transaction Simulator
      </h2>
      <p className="text-sm text-gray-400 mb-6">
        Submit a transaction to run it through the full ensemble model.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">

        {/* ── User Selector ─────────────────────────────────────────────── */}
        {/* Pulls from users table via GET /users */}
        <div>
          <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wider">
            Select User
          </label>
          <select
            name="user_id"
            value={formData.user_id}
            onChange={handleChange}
            required
            className="w-full bg-gray-800 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">— Choose a user —</option>
            {users.map((u) => (
              <option key={u.user_id} value={u.user_id}>
                {u.full_name} ({u.city})
              </option>
            ))}
          </select>
        </div>

        {/* ── Behavioral Profile Preview ────────────────────────────────── */}
        {/* Shown when a user is selected — pulls from behavior_profiles table */}
        {profile && (
          <div className="bg-gray-800 border border-gray-600 rounded-lg px-4 py-3 text-xs text-gray-300 space-y-1">
            <p className="text-gray-400 font-medium uppercase tracking-wider mb-2">Baseline Profile</p>
            <div className="grid grid-cols-2 gap-1">
              <span className="text-gray-500">Avg Spend</span>
              <span>AED {profile.avg_transaction_amount.toLocaleString()}</span>
              <span className="text-gray-500">Usual Location</span>
              <span>{profile.usual_location}</span>
              <span className="text-gray-500">Typical Device</span>
              <span className="capitalize">{profile.typical_device}</span>
              <span className="text-gray-500">Login Hour</span>
              <span>{profile.typical_login_hour}:00</span>
            </div>
          </div>
        )}

        {/* ── Amount ───────────────────────────────────────────────────── */}
        <div>
          <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wider">
            Amount (AED)
          </label>
          <input
            type="number"
            name="amount"
            value={formData.amount || ""}
            onChange={handleChange}
            required
            min={1}
            placeholder="e.g. 5000"
            className="w-full bg-gray-800 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* ── Merchant ─────────────────────────────────────────────────── */}
        <div>
          <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wider">
            Merchant
          </label>
          <input
            type="text"
            name="merchant"
            value={formData.merchant}
            onChange={handleChange}
            required
            placeholder="e.g. Amazon.ae"
            className="w-full bg-gray-800 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* ── Transaction Type ─────────────────────────────────────────── */}
        <div>
          <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wider">
            Transaction Type
          </label>
          <select
            name="transaction_type"
            value={formData.transaction_type}
            onChange={handleChange}
            className="w-full bg-gray-800 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {TRANSACTION_TYPES.map((t) => (
              <option key={t} value={t}>{t.replace("_", " ")}</option>
            ))}
          </select>
        </div>

        {/* ── Transaction Location ─────────────────────────────────────── */}
        <div>
          <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wider">
            Transaction Location
          </label>
          <input
            type="text"
            name="location"
            value={formData.location}
            onChange={handleChange}
            required
            placeholder="e.g. Dubai"
            className="w-full bg-gray-800 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* ── Login Location (Session) ──────────────────────────────────── */}
        <div>
          <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wider">
            Login Location
          </label>
          <input
            type="text"
            name="login_location"
            value={formData.login_location}
            onChange={handleChange}
            required
            placeholder="e.g. Abu Dhabi"
            className="w-full bg-gray-800 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* ── Device Type ──────────────────────────────────────────────── */}
        <div>
          <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wider">
            Device Type
          </label>
          <select
            name="device_type"
            value={formData.device_type}
            onChange={handleChange}
            className="w-full bg-gray-800 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {DEVICE_TYPES.map((d) => (
              <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
            ))}
          </select>
        </div>

        {/* ── VPN Detected Toggle ───────────────────────────────────────── */}
        {/* Boolean field — checkbox styled as a toggle */}
        {/* Maps to sessions.vpn_detected in the DB */}
        <div className="flex items-center justify-between bg-gray-800 border border-gray-600 rounded-lg px-4 py-3">
          <div>
            <p className="text-sm text-white font-medium">VPN Detected</p>
            <p className="text-xs text-gray-400">Was a VPN active during this session?</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              name="vpn_detected"
              checked={formData.vpn_detected}
              onChange={handleChange}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-600 peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:bg-blue-500 transition-colors after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full" />
          </label>
        </div>

        {/* ── Error Message ─────────────────────────────────────────────── */}
        {error && (
          <div className="bg-red-900/40 border border-red-700 text-red-300 text-sm rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        {/* ── Submit / Reset ────────────────────────────────────────────── */}
        {!submitted ? (
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-blue-900 disabled:text-blue-400 text-white font-semibold rounded-lg py-3 text-sm transition-colors"
          >
            {loading ? "Scoring..." : "Run Ensemble Score"}
          </button>
        ) : (
          <button
            type="button"
            onClick={handleReset}
            className="w-full bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg py-3 text-sm transition-colors"
          >
            Score Another Transaction
          </button>
        )}

      </form>
    </div>
  );
}