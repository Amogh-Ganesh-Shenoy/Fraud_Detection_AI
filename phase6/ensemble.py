"""
UAE Fraud Detection AI — Phase 6
Ensemble Model — Combines Rule Engine + Z-Score + Random Forest
Author: Amogh Ganesh Shenoy

How it works:
    Takes the output of all 3 models for a single transaction,
    normalises each score to a 0.0-1.0 scale, applies weighted
    aggregation, and produces a single final decision.

Weights:
    Random Forest  → 0.35  (best recall, 8 features, learned patterns)
    Rule Engine    → 0.50  (strong precision, domain knowledge)
    Z-Score        → 0.15  (weakest on this dataset, single feature)

Normalisation:
    fraud_probability  already 0.0-1.0  → no change needed
    risk_score         divide by 150     → clamped to 1.0
    anomaly_score      divide by 5.0     → clamped to 1.0

Final Decision Thresholds:
    0.0 – 0.30  → APPROVE
    0.30 – 0.35 → CHALLENGE
    0.35+       → BLOCK
"""

import pickle
import statistics
import numpy as np
import pandas as pd
from datetime import datetime

import os
from dotenv import load_dotenv

import psycopg
from psycopg.rows import dict_row

# Import all three models — ensemble orchestrates them, not replaces them
from phase3.risk_engine import score_transaction
from phase6.zscore_model import score_zscore
from phase6.random_forest_model import predict_single

MODEL_PATH = "phase6/random_forest.pkl"

load_dotenv()

# DATABASE_URL points to Render's managed PostgreSQL in production
# Loaded from .env locally, injected as environment variable on Render
DATABASE_URL = os.getenv("DATABASE_URL")

# ── Weights — must sum to 1.0 ─────────────────────────────────────────────────
# Random Forest carries most weight — best recall on this dataset
# Rule engine second — strong precision and domain-encoded fraud knowledge
# Z-Score least — limited to amount signal only, weak on synthetic data
RF_WEIGHT     = 0.35
RULE_WEIGHT   = 0.50
ZSCORE_WEIGHT = 0.15

# ── Normalisation denominators ────────────────────────────────────────────────
# Rule engine scores are uncapped — use 150 as safe normalisation ceiling
# Z-score threshold is 2.5 but scores can go higher — use 5.0 as ceiling
RULE_MAX   = 150.0
ZSCORE_MAX = 5.0

# ── Ensemble decision thresholds ──────────────────────────────────────────────
# CHALLENGE_MAX lowered to 0.35 to improve Recall — missed fraud is more
# costly than blocking a legitimate transaction in fraud detection
APPROVE_MAX   = 0.30
CHALLENGE_MAX = 0.35


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_db():
    # Connects to PostgreSQL using DATABASE_URL from environment
    # RealDictCursor returns rows as dicts — row["amount"] not row[0]
    # Used by ensemble_score() to update the alert decision after scoring
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
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
    0.30 – 0.35 → CHALLENGE
    0.35+       → BLOCK
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
        7. Update alerts table with ensemble final_decision

    Data sources (via called functions):
        phase3/risk_engine.py  — transactions, sessions, behavior_profiles, alerts
        phase6/zscore_model.py — transactions, accounts, behavior_profiles
        phase6/random_forest_model.py — transactions, sessions, behavior_profiles
    """

    # ── Step 1: Run the rule engine ───────────────────────────────────────────
    # Pulls transaction + session + behavior_profile, applies 7 rules,
    # writes alert to alerts table with rule engine decision,
    # returns risk_score + reason_codes
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

    # ── Step 7: Update alerts table with ensemble final decision ──────────────
    # score_transaction() writes the rule engine decision to alerts.
    # We overwrite it here so the alert table shows the final ensemble verdict
    # rather than the intermediate rule engine verdict.
    # Source: alerts table, keyed by transaction_id
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE alerts
            SET decision = %s
            WHERE transaction_id = %s
        """, (final_decision, transaction_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ENSEMBLE] Failed to update alert decision for {transaction_id}: {e}")

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
    Evaluates ensemble performance against fraud_labels ground truth.
    Offline only — not called at runtime. Does NOT write to alerts table.
    Pre-fetches all data in bulk queries — no per-transaction DB calls.

    Data sources:
        transactions      — amount, location, timestamp, session_id, account_id
        sessions          — vpn_detected, device_type, location, login_time
        behavior_profiles — avg_transaction_amount, usual_location,
                            typical_device, typical_login_hour
        accounts          — links transactions to users
        fraud_labels      — ground truth is_fraud label (0 or 1)
    """
    conn = get_db()
    cur  = conn.cursor()

    # Pull all transactions with account and user context in one query
    cur.execute("""
        SELECT t.transaction_id, t.account_id, t.session_id,
               t.amount, t.location AS txn_location, t.timestamp, a.user_id
        FROM transactions t
        JOIN accounts a ON t.account_id = a.account_id
    """)
    transactions = cur.fetchall()

    # Pull all sessions indexed by session_id
    cur.execute("""
        SELECT session_id, vpn_detected, device_type,
               location AS login_location, login_time
        FROM sessions
    """)
    sessions    = cur.fetchall()
    session_map = {s["session_id"]: s for s in sessions}

    # Pull all behavior profiles indexed by user_id
    cur.execute("""
        SELECT user_id, avg_transaction_amount, usual_location,
               typical_device, typical_login_hour
        FROM behavior_profiles
    """)
    profiles    = cur.fetchall()
    profile_map = {p["user_id"]: p for p in profiles}

    # Pull fraud labels indexed by transaction_id
    cur.execute("SELECT transaction_id, is_fraud FROM fraud_labels")
    labels    = cur.fetchall()
    label_map = {r["transaction_id"]: r["is_fraud"] for r in labels}

    # Pull all velocity counts in one bulk query — same as build_feature_matrix()
    cur.execute("""
        SELECT t1.transaction_id, COUNT(t2.transaction_id) AS cnt
        FROM transactions t1
        JOIN transactions t2 ON t1.account_id = t2.account_id
            AND t2.timestamp::timestamp >= t1.timestamp::timestamp - interval '10 minutes'
            AND t2.timestamp::timestamp <= t1.timestamp::timestamp + interval '10 minutes'
        GROUP BY t1.transaction_id
    """)
    velocity_rows = cur.fetchall()
    velocity_map  = {r["transaction_id"]: r["cnt"] for r in velocity_rows}

    # Pull all historical amounts per account for Z-score computation
    cur.execute("SELECT account_id, amount FROM transactions")
    all_amounts     = cur.fetchall()
    account_amounts = {}
    for r in all_amounts:
        account_amounts.setdefault(r["account_id"], []).append(float(r["amount"]))

    conn.close()

    # Load Random Forest model once — not per transaction
    import pickle
    if not os.path.exists(MODEL_PATH):
        print(f"[ENSEMBLE] Model not found at {MODEL_PATH}")
        return {}
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    feature_cols = [
        "amount_ratio", "vpn_flag", "new_device_flag",
        "unusual_login_location", "unusual_txn_location",
        "login_txn_mismatch", "hour_deviation", "velocity_count",
    ]

    # Build feature rows for all transactions in memory — no DB calls in loop
    feature_rows = []
    meta         = []

    for txn in transactions:
        tid        = txn["transaction_id"]
        user_id    = txn["user_id"]
        account_id = txn["account_id"]

        if tid not in label_map:
            continue

        session = session_map.get(txn["session_id"])
        profile = profile_map.get(user_id)

        if not session or not profile:
            continue

        avg          = float(profile["avg_transaction_amount"]) or 1.0
        amount_ratio = float(txn["amount"]) / avg
        vpn_flag     = int(session["vpn_detected"])
        new_device_flag = int(
            session["device_type"].lower() != profile["typical_device"].lower()
        )
        unusual_login_location = int(
            session["login_location"].strip().lower() !=
            profile["usual_location"].strip().lower()
        )
        unusual_txn_location = int(
            txn["txn_location"].strip().lower() !=
            profile["usual_location"].strip().lower()
        )
        login_txn_mismatch = int(
            session["login_location"].strip().lower() !=
            txn["txn_location"].strip().lower()
        )
        try:
            login_hour     = datetime.fromisoformat(str(session["login_time"])).hour
            hour_diff      = abs(login_hour - profile["typical_login_hour"])
            hour_deviation = min(hour_diff, 24 - hour_diff)
        except (ValueError, TypeError):
            hour_deviation = 0

        velocity_count = velocity_map.get(tid, 1)

        # Z-score computed in memory — no DB call
        amounts = [a for a in account_amounts.get(account_id, []) if a != float(txn["amount"])]
        avg_amount = avg
        if len(amounts) >= 3:
            import statistics
            std_dev = statistics.stdev(amounts)
        else:
            std_dev = avg_amount
        if std_dev == 0:
            std_dev = avg_amount if avg_amount > 0 else 1.0
        z_score    = (float(txn["amount"]) - avg_amount) / std_dev
        is_anomaly = z_score >= ZSCORE_MAX

        # Rule engine score computed in memory — no DB call, no alert write
        score = 0
        if session["vpn_detected"]:
            score += 20
        if float(txn["amount"]) / avg >= 4.3:
            score += 75
        elif float(txn["amount"]) / avg >= 3.6:
            score += 65
        elif float(txn["amount"]) / avg >= 2.9:
            score += 50
        elif float(txn["amount"]) / avg >= 2.2:
            score += 35
        elif float(txn["amount"]) / avg >= 1.5:
            score += 25
        if velocity_count > 3:
            score += 75

        feature_rows.append([
            amount_ratio, vpn_flag, new_device_flag,
            unusual_login_location, unusual_txn_location,
            login_txn_mismatch, hour_deviation, velocity_count,
        ])
        meta.append({
            "tid":        tid,
            "risk_score": score,
            "z_score":    z_score,
            "is_fraud":   label_map[tid],
        })

    # Batch RF prediction — one call for all transactions
    import numpy as np
    X                  = pd.DataFrame(feature_rows, columns=feature_cols)
    fraud_probabilities = model.predict_proba(X)[:, 1]

    TP = FP = FN = TN = 0

    for i, m in enumerate(meta):
        fraud_probability = fraud_probabilities[i]
        norm_rule         = min(m["risk_score"] / RULE_MAX, 1.0)
        norm_zscore       = max(0.0, min(m["z_score"] / ZSCORE_MAX, 1.0))
        norm_rf           = fraud_probability

        final_score    = (norm_rf * RF_WEIGHT) + (norm_rule * RULE_WEIGHT) + (norm_zscore * ZSCORE_WEIGHT)
        final_decision = get_ensemble_decision(final_score)

        predicted_fraud = final_decision == "BLOCK"
        actual_fraud    = bool(m["is_fraud"])

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