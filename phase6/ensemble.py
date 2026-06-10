"""
UAE Fraud Detection AI — Phase 6
Ensemble Model — Combines Rule Engine + Z-Score + Random Forest
Author: Amogh Ganesh Shenoy

How it works:
    Takes the output of all 3 models for a single transaction,
    normalises each score to a 0.0-1.0 scale, applies weighted
    aggregation, and produces a single final decision.

Weights:
    Random Forest  → 0.50  (best recall, 8 features, learned patterns)
    Rule Engine    → 0.35  (strong precision, domain knowledge)
    Z-Score        → 0.15  (weakest on this dataset, single feature)

Normalisation:
    fraud_probability  already 0.0-1.0  → no change needed
    risk_score         divide by 150     → clamped to 1.0
    anomaly_score      divide by 5.0     → clamped to 1.0

Final Decision Thresholds:
    0.0 – 0.30  → APPROVE
    0.30 – 0.45 → CHALLENGE
    0.45+       → BLOCK
"""

import os
from dotenv import load_dotenv

import psycopg2
import psycopg2.extras

# Import all three models — ensemble orchestrates them, not replaces them
from phase3.risk_engine import score_transaction
from phase6.zscore_model import score_zscore
from phase6.random_forest_model import predict_single

load_dotenv()

# DATABASE_URL points to Render's managed PostgreSQL in production
# Loaded from .env locally, injected as environment variable on Render
DATABASE_URL = os.getenv("DATABASE_URL")

# ── Weights — must sum to 1.0 ─────────────────────────────────────────────────
# Random Forest carries most weight — best recall on this dataset
# Rule engine second — strong precision and domain-encoded fraud knowledge
# Z-Score least — limited to amount signal only, weak on synthetic data
RF_WEIGHT     = 0.50
RULE_WEIGHT   = 0.35
ZSCORE_WEIGHT = 0.15

# ── Normalisation denominators ────────────────────────────────────────────────
# Rule engine scores are uncapped — use 150 as safe normalisation ceiling
# Z-score threshold is 2.5 but scores can go higher — use 5.0 as ceiling
RULE_MAX   = 150.0
ZSCORE_MAX = 5.0

# ── Ensemble decision thresholds ──────────────────────────────────────────────
# CHALLENGE_MAX lowered to 0.45 to improve Recall — missed fraud is more
# costly than blocking a legitimate transaction in fraud detection
APPROVE_MAX   = 0.30
CHALLENGE_MAX = 0.45


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_db():
    # Connects to PostgreSQL using DATABASE_URL from environment
    # RealDictCursor returns rows as dicts — row["amount"] not row[0]
    # Used only by evaluate_ensemble() for offline batch evaluation
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# NORMALISATION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def normalise_rule_score(risk_score: float) -> float:
    """
    Converts rule engine risk_score (0-150+) to 0.0-1.0 scale.
    Source: phase3/risk_engine.py → score_transaction() → risk_score
    """
    return min(risk_score / RULE_MAX, 1.0)


def normalise_zscore(anomaly_score: float) -> float:
    """
    Converts Z-score anomaly_score (unbounded) to 0.0-1.0 scale.
    Negative scores floored at 0.0 — not a fraud signal in this model.
    Source: phase6/zscore_model.py → score_zscore() → anomaly_score
    """
    return max(0.0, min(anomaly_score / ZSCORE_MAX, 1.0))


# ══════════════════════════════════════════════════════════════════════════════
# DECISION MAPPING
# ══════════════════════════════════════════════════════════════════════════════

def get_ensemble_decision(ensemble_score: float) -> str:
    """
    Maps normalised ensemble score (0.0-1.0) to a final decision string.
    0.00 – 0.30 → APPROVE
    0.30 – 0.45 → CHALLENGE
    0.45+       → BLOCK
    """
    if ensemble_score <= APPROVE_MAX:
        return "APPROVE"
    elif ensemble_score <= CHALLENGE_MAX:
        return "CHALLENGE"
    else:
        return "BLOCK"


# ══════════════════════════════════════════════════════════════════════════════
# CORE ENSEMBLE FUNCTION — called at runtime by api/main.py POST /score
# ══════════════════════════════════════════════════════════════════════════════

def ensemble_score(transaction_id: str, session_id: str, user_id: str) -> dict | None:
    """
    Orchestrates all 3 models for a single transaction and combines
    their outputs into one final decision.

    Flow:
        1. Call rule engine   → risk_score + reason_codes
        2. Call Z-score model → anomaly_score + is_anomaly
        3. Call Random Forest → fraud_probability
        4. Normalise all 3 scores to 0.0-1.0
        5. Apply weighted average → ensemble_score
        6. Map ensemble_score → final decision

    Data sources (via called functions):
        phase3/risk_engine.py  — transactions, sessions, behavior_profiles, alerts
        phase6/zscore_model.py — transactions, accounts, behavior_profiles
        phase6/random_forest_model.py — transactions, sessions, behavior_profiles
    """

    # ── Step 1: Run the rule engine ───────────────────────────────────────────
    # Pulls transaction + session + behavior_profile, applies 7 rules,
    # writes alert to alerts table, returns risk_score + reason_codes
    rule_result = score_transaction(transaction_id, session_id)

    if not rule_result:
        print(f"[ENSEMBLE] Rule engine failed for {transaction_id}")
        return None

    risk_score   = rule_result["risk_score"]
    reason_codes = rule_result["reason_codes"]

    # ── Step 2: Run the Z-score anomaly model ─────────────────────────────────
    # Pulls transaction amount and behavior_profile, computes std deviation
    # Returns anomaly_score (raw Z value) and is_anomaly (bool)
    zscore_result = score_zscore(transaction_id, user_id)

    if not zscore_result:
        print(f"[ENSEMBLE] Z-score failed for {transaction_id} — defaulting to 0.0")
        anomaly_score = 0.0
        is_anomaly    = False
    else:
        anomaly_score = zscore_result["anomaly_score"]
        is_anomaly    = zscore_result["is_anomaly"]

    # ── Step 3: Run the Random Forest classifier ──────────────────────────────
    # Loads random_forest.pkl, engineers 8 features, returns fraud_probability
    rf_result = predict_single(transaction_id, user_id)

    if not rf_result:
        print(f"[ENSEMBLE] Random Forest failed for {transaction_id} — defaulting to 0.0")
        fraud_probability = 0.0
        rf_features       = {}
    else:
        fraud_probability = rf_result["fraud_probability"]
        rf_features       = rf_result.get("features", {})

    # ── Step 4: Normalise all 3 scores to 0.0-1.0 ────────────────────────────
    # Each model outputs on a different scale — normalisation brings them
    # to a common unit so the weighted average is mathematically meaningful
    norm_rule   = normalise_rule_score(risk_score)
    norm_zscore = normalise_zscore(anomaly_score)
    norm_rf     = fraud_probability  # already 0.0-1.0

    # ── Step 5: Weighted average → single ensemble score ──────────────────────
    # Weights sum to 1.0 so result stays on 0.0-1.0 scale
    final_score = (
        (norm_rf     * RF_WEIGHT)    +
        (norm_rule   * RULE_WEIGHT)  +
        (norm_zscore * ZSCORE_WEIGHT)
    )

    # ── Step 6: Map ensemble score to final decision ──────────────────────────
    final_decision = get_ensemble_decision(final_score)

    return {
        "transaction_id":    transaction_id,
        "user_id":           user_id,
        "risk_score":        risk_score,
        "rule_decision":     rule_result["decision"],
        "reason_codes":      reason_codes,
        "norm_rule":         round(norm_rule, 4),
        "anomaly_score":     round(anomaly_score, 4),
        "is_anomaly":        is_anomaly,
        "norm_zscore":       round(norm_zscore, 4),
        "fraud_probability": fraud_probability,
        "rf_features":       rf_features,
        "norm_rf":           round(norm_rf, 4),
        "ensemble_score":    round(final_score, 4),
        "final_decision":    final_decision,
        "weights": {
            "random_forest": RF_WEIGHT,
            "rule_engine":   RULE_WEIGHT,
            "zscore":        ZSCORE_WEIGHT,
        }
    }


# ══════════════════════════════════════════════════════════════════════════════
# BATCH EVALUATION — offline only, not called at runtime
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_ensemble() -> dict:
    """
    Runs the ensemble across every transaction and evaluates against
    fraud_labels ground truth. Offline only — not called at runtime.
    """
    conn = get_db()
    cur  = conn.cursor()

    # Pull every transaction with session_id and user_id
    # Source: transactions + accounts tables
    cur.execute("""
        SELECT t.transaction_id, t.session_id, a.user_id
        FROM transactions t
        JOIN accounts a ON t.account_id = a.account_id
    """)
    rows = cur.fetchall()

    # Pull ground truth labels
    # Source: fraud_labels table, populated by Phase 1
    cur.execute("SELECT transaction_id, is_fraud FROM fraud_labels")
    labels = cur.fetchall()
    conn.close()

    label_map = {r["transaction_id"]: r["is_fraud"] for r in labels}

    TP = FP = FN = TN = 0

    for row in rows:
        tid        = row["transaction_id"]
        session_id = row["session_id"]
        user_id    = row["user_id"]

        if tid not in label_map:
            continue

        result = ensemble_score(tid, session_id, user_id)
        if not result:
            continue

        predicted_fraud = result["final_decision"] == "BLOCK"
        actual_fraud    = bool(label_map[tid])

        if predicted_fraud and actual_fraud:       TP += 1
        elif predicted_fraud and not actual_fraud: FP += 1
        elif not predicted_fraud and actual_fraud: FN += 1
        else:                                      TN += 1

    precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
    recall    = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    metrics = {
        "TP": TP, "FP": FP, "FN": FN, "TN": TN,
        "precision": round(precision, 4),
        "recall":    round(recall, 4),
        "f1":        round(f1, 4),
    }

    print("\n" + "=" * 55)
    print("  ENSEMBLE MODEL — EVALUATION RESULTS")
    print("=" * 55)
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print("=" * 55 + "\n")

    return metrics


if __name__ == "__main__":
    evaluate_ensemble()