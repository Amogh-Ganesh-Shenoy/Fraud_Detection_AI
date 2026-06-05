# api/models.py
# Pydantic models for request validation and response serialisation.
# FastAPI uses these automatically — invalid requests are rejected before
# they reach any endpoint logic.

from pydantic import BaseModel
from enum import Enum
from typing import Optional


# ── Decision Enum ─────────────────────────────────────────────────────────────
# Restricts final_decision and rule_decision to only valid values.
# Any other string is rejected at the API boundary automatically by Pydantic.
class Decision(str, Enum):
    APPROVE   = "APPROVE"
    CHALLENGE = "CHALLENGE"
    BLOCK     = "BLOCK"


# ══════════════════════════════════════════════════════════════════════════════
# POST /score
# ══════════════════════════════════════════════════════════════════════════════

# ── Request Body ──────────────────────────────────────────────────────────────
# Fields the React frontend sends when submitting a transaction in play mode.
# user_id identifies whose behavior profile to compare against.
# Everything else maps directly to ingest_session() and ingest_transaction()
# in phase2/ingest.py.
class ScoreRequest(BaseModel):
    user_id:          str
    amount:           float
    merchant:         str
    transaction_type: str
    location:         str
    device_type:      str
    login_location:   str
    vpn_detected:     bool = False


# ── Response Body ─────────────────────────────────────────────────────────────
# All fields returned after running the full ensemble on a transaction.
# Sources:
#   risk_score, rule_decision, reason_codes → phase3/risk_engine.py
#   anomaly_score, is_anomaly              → phase6/zscore_model.py
#   fraud_probability                      → phase6/random_forest_model.py
#   norm_*, ensemble_score, final_decision → phase6/ensemble.py
# reason_codes is a list so React can .map() over it directly for badge rendering.
# weights is dict[str, float] matching ensemble.py's return format exactly.
class ScoreResponse(BaseModel):
    transaction_id:    str
    risk_score:        int
    rule_decision:     Decision
    anomaly_score:     float
    is_anomaly:        bool
    fraud_probability: float
    ensemble_score:    float
    final_decision:    Decision
    reason_codes:      list[str]
    norm_rule:         float
    norm_zscore:       float
    norm_rf:           float
    weights:           dict[str, float]


# ══════════════════════════════════════════════════════════════════════════════
# GET /users
# ══════════════════════════════════════════════════════════════════════════════

# ── Response Body ─────────────────────────────────────────────────────────────
# One entry per user returned for the dropdown selector in the React UI.
# Pulls from the users table: user_id, full_name, city.
class UserSummary(BaseModel):
    user_id:   str
    full_name: str
    city:      str


# ══════════════════════════════════════════════════════════════════════════════
# GET /users/{user_id}/profile
# ══════════════════════════════════════════════════════════════════════════════

# ── Response Body ─────────────────────────────────────────────────────────────
# Behavioral baseline for a single user, shown in the ProfileCard component.
# Pulls from behavior_profiles table.
class UserProfile(BaseModel):
    avg_transaction_amount: float
    usual_location:         str
    typical_device:         str
    typical_login_hour:     int


# ══════════════════════════════════════════════════════════════════════════════
# GET /alerts
# ══════════════════════════════════════════════════════════════════════════════

# ── Response Body ─────────────────────────────────────────────────────────────
# One entry per alert for the AlertTable component.
# Pulls from alerts JOIN transactions — reason_codes stored as str in alerts
# table (comma-separated) so we keep it as str here; React splits if needed.
class AlertSummary(BaseModel):
    risk_score:   int
    decision:     str
    reason_codes: str
    timestamp:    str
    amount:       float
    merchant:     str
    location:     str


# ══════════════════════════════════════════════════════════════════════════════
# GET /metrics
# ══════════════════════════════════════════════════════════════════════════════

# ── Nested metric blocks ──────────────────────────────────────────────────────
# Each model's evaluation results are grouped into their own sub-model.
# Optional fields handle models that don't have AUC (Z-Score, Ensemble).
class ModelMetrics(BaseModel):
    precision: float
    recall:    float
    f1:        float
    auc:       Optional[float] = None


# ── Response Body ─────────────────────────────────────────────────────────────
# Static Phase 5 and Phase 6 evaluation results — no recomputation on each call.
# feature_importances maps feature name → importance score from Random Forest.
# Values sourced from phase6/random_forest_model.py → evaluate_random_forest().
class MetricsResponse(BaseModel):
    phase5:               ModelMetrics
    zscore:               ModelMetrics
    random_forest:        ModelMetrics
    ensemble:             ModelMetrics
    feature_importances:  dict[str, float]


# ══════════════════════════════════════════════════════════════════════════════
# POST /session
# ══════════════════════════════════════════════════════════════════════════════

# ── Response Body ─────────────────────────────────────────────────────────────
# Returns the generated session_id after calling ingest_session()
# in phase2/ingest.py. Frontend passes this session_id into POST /score.
class SessionResponse(BaseModel):
    session_id: str