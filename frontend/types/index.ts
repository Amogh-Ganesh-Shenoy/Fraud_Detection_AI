// types/index.ts
// TypeScript interfaces for all data shapes flowing between React and FastAPI.
// These mirror the Pydantic models in api/models.py — any change to the API
// response shape must be reflected here to keep the frontend in sync.

// ── Decision Type ─────────────────────────────────────────────────────────────
// Mirrors the Decision enum in api/models.py.
// TypeScript union type restricts the value to only these three strings.
export type Decision = "APPROVE" | "CHALLENGE" | "BLOCK";


// ══════════════════════════════════════════════════════════════════════════════
// AUTH
// ══════════════════════════════════════════════════════════════════════════════

// Response from POST /login — JWT token stored in React state after login
export interface LoginResponse {
  access_token: string;
  token_type:   string;
}


// ══════════════════════════════════════════════════════════════════════════════
// POST /score
// ══════════════════════════════════════════════════════════════════════════════

// Request body sent by ScoreForm.tsx to POST /score
// Mirrors ScoreRequest in api/models.py
export interface ScoreRequest {
  user_id:          string;
  amount:           number;
  merchant:         string;
  transaction_type: string;
  location:         string;
  device_type:      string;
  login_location:   string;
  vpn_detected:     boolean;
}

// Response received from POST /score — displayed in ResultCard and GaugeChart
// Mirrors ScoreResponse in api/models.py
export interface ScoreResponse {
  transaction_id:    string;
  risk_score:        number;
  rule_decision:     Decision;
  anomaly_score:     number;
  is_anomaly:        boolean;
  fraud_probability: number;
  ensemble_score:    number;
  final_decision:    Decision;
  reason_codes:      string[];
  norm_rule:         number;
  norm_zscore:       number;
  norm_rf:           number;
  weights:           Record<string, number>;
}


// ══════════════════════════════════════════════════════════════════════════════
// GET /users
// ══════════════════════════════════════════════════════════════════════════════

// One entry in the user dropdown selector in play mode
// Mirrors UserSummary in api/models.py
export interface UserSummary {
  user_id:   string;
  full_name: string;
  city:      string;
}


// ══════════════════════════════════════════════════════════════════════════════
// GET /users/{user_id}/profile
// ══════════════════════════════════════════════════════════════════════════════

// Behavioral baseline displayed in ProfileCard.tsx
// Mirrors UserProfile in api/models.py
// Pulls from behavior_profiles table built by Phase 1
export interface UserProfile {
  avg_transaction_amount: number;
  usual_location:         string;
  typical_device:         string;
  typical_login_hour:     number;
}


// ══════════════════════════════════════════════════════════════════════════════
// GET /alerts
// ══════════════════════════════════════════════════════════════════════════════

// One row in the AlertTable.tsx component
// Mirrors AlertSummary in api/models.py
// reason_codes is a string here — comma separated as stored in alerts table
export interface AlertSummary {
  risk_score:   number;
  decision:     string;
  reason_codes: string;
  timestamp:    string;
  amount:       number;
  merchant:     string;
  location:     string;
}


// ══════════════════════════════════════════════════════════════════════════════
// GET /metrics
// ══════════════════════════════════════════════════════════════════════════════

// Evaluation metrics for a single model — used in MetricsPanel.tsx
// auc is optional because Z-Score and Ensemble don't have AUC values
export interface ModelMetrics {
  precision: number;
  recall:    number;
  f1:        number;
  auc?:      number;
}

// Full metrics response — contains all 4 models and feature importances
// Mirrors MetricsResponse in api/models.py
// feature_importances fed into FeatureBar.tsx
export interface MetricsResponse {
  phase5:              ModelMetrics;
  zscore:              ModelMetrics;
  random_forest:       ModelMetrics;
  ensemble:            ModelMetrics;
  feature_importances: Record<string, number>;
}


// ══════════════════════════════════════════════════════════════════════════════
// POST /session
// ══════════════════════════════════════════════════════════════════════════════

// Response from POST /session — session_id passed into POST /score
// Mirrors SessionResponse in api/models.py
export interface SessionResponse {
  session_id: string;
}