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
    0.30 – 0.60 → CHALLENGE
    0.60+       → BLOCK
"""

# Standard library imports
import sqlite3
import os

from dotenv import load_dotenv

# Import all three models — ensemble orchestrates them, not replaces them
from phase3.risk_engine import score_transaction
from phase6.zscore_model import score_zscore
from phase6.random_forest_model import predict_single

# Load DB_PATH from .env — consistent with all other phase files
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/fraud.db")

# ── Weights — must sum to 1.0 ─────────────────────────────────────────────────
# Random Forest carries most weight — best recall on this dataset
# Rule engine second — strong precision and domain-encoded fraud knowledge
# Z-Score least — limited to amount signal only, weak on synthetic data
RF_WEIGHT    = 0.50
RULE_WEIGHT  = 0.35
ZSCORE_WEIGHT = 0.15

# ── Normalisation denominators ────────────────────────────────────────────────
# Rule engine scores are uncapped (can exceed 100 when multiple rules fire)
# We use 150 as the normalisation ceiling to safely handle combined rule scores
# Z-score threshold is 2.5 but scores can go higher — we use 5.0 as ceiling
RULE_MAX   = 150.0
ZSCORE_MAX = 5.0

# ── Ensemble decision thresholds ──────────────────────────────────────────────
# Applied to the final weighted score (0.0-1.0)
# CHALLENGE_MAX lowered from 0.60 → 0.45 to improve Recall at the cost of
# some Precision — false negatives (missed fraud) are more costly than
# false positives (blocked legitimate transactions) in fraud detection
APPROVE_MAX   = 0.30
CHALLENGE_MAX = 0.45
# Anything above CHALLENGE_MAX → BLOCK


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

# Opens a connection to the SQLite database.
# row_factory = sqlite3.Row lets us access columns by name
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# NORMALISATION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def normalise_rule_score(risk_score: float) -> float:
    """
    Converts the rule engine risk_score (0-150+) to a 0.0-1.0 scale.
    Divides by RULE_MAX (150) and clamps to 1.0 so scores above 150
    don't break the weighted average.

    Source: phase3/risk_engine.py → score_transaction() → risk_score
    """
    return min(risk_score / RULE_MAX, 1.0)


def normalise_zscore(anomaly_score: float) -> float:
    """
    Converts the Z-score anomaly_score (unbounded float) to a 0.0-1.0 scale.
    Divides by ZSCORE_MAX (5.0) and clamps between 0.0 and 1.0.
    Negative Z-scores (amount below average) are floored at 0.0 —
    they are not fraud signals in this model.

    Source: phase6/zscore_model.py → score_zscore() → anomaly_score
    """
    return max(0.0, min(anomaly_score / ZSCORE_MAX, 1.0))


# ══════════════════════════════════════════════════════════════════════════════
# DECISION MAPPING
# ══════════════════════════════════════════════════════════════════════════════

def get_ensemble_decision(ensemble_score: float) -> str:
    """
    Maps the normalised ensemble score (0.0-1.0) to a final decision string.
    Uses wider CHALLENGE band than rule engine to reflect combined model confidence.

    0.00 – 0.30 → APPROVE   (low combined risk)
    0.30 – 0.60 → CHALLENGE (elevated combined risk — request OTP/verification)
    0.60+       → BLOCK     (high combined risk — stop transaction)
    """
    if ensemble_score <= APPROVE_MAX:
        return "APPROVE"
    elif ensemble_score <= CHALLENGE_MAX:
        return "CHALLENGE"
    else:
        return "BLOCK"


# ══════════════════════════════════════════════════════════════════════════════
# CORE ENSEMBLE FUNCTION — score a single transaction through all 3 models
# ══════════════════════════════════════════════════════════════════════════════

def ensemble_score(transaction_id: str, session_id: str, user_id: str) -> dict | None:
    """
    Orchestrates all 3 models for a single transaction and combines
    their outputs into one final decision.

    Flow:
        1. Call rule engine   → risk_score + reason_codes
        2. Call Z-score model → anomaly_score + is_anomaly
        3. Call Random Forest → fraud_probability + feature values
        4. Normalise all 3 scores to 0.0-1.0
        5. Apply weighted average → ensemble_score
        6. Map ensemble_score → final decision

    Args:
        transaction_id: UUID of the transaction to score
        session_id:     UUID of the session (needed by rule engine)
        user_id:        UUID of the account owner (needed by Z-score and RF)

    Returns:
        Full result dict with all 3 model outputs + ensemble decision,
        or None if any model fails critically
    """

    # ── Step 1: Run the rule engine (Phase 3) ─────────────────────────────────
    # score_transaction() pulls transaction + session + behavior_profile from DB,
    # applies 9 rules, writes an alert to the alerts table, and returns a dict
    # with risk_score, decision, and reason_codes
    rule_result = score_transaction(transaction_id, session_id)

    if not rule_result:
        print(f"[ENSEMBLE] Rule engine failed for {transaction_id}")
        return None

    # Extract the raw risk score and reason codes from the rule engine result
    risk_score   = rule_result["risk_score"]
    reason_codes = rule_result["reason_codes"]

    # ── Step 2: Run the Z-score anomaly model (Phase 6) ───────────────────────
    # score_zscore() pulls transaction amount and behavior_profile from DB,
    # calculates std deviation from transaction history, and returns
    # anomaly_score (raw Z value) and is_anomaly (bool)
    zscore_result = score_zscore(transaction_id, user_id)

    # Z-score failure is non-critical — default to 0.0 (no anomaly signal)
    # so the ensemble can still produce a decision from the other two models
    if not zscore_result:
        print(f"[ENSEMBLE] Z-score failed for {transaction_id} — defaulting to 0.0")
        anomaly_score = 0.0
        is_anomaly    = False
    else:
        anomaly_score = zscore_result["anomaly_score"]
        is_anomaly    = zscore_result["is_anomaly"]

    # ── Step 3: Run the Random Forest classifier (Phase 6) ───────────────────
    # predict_single() loads the saved random_forest.pkl, engineers the same
    # 8 features as training, and returns fraud_probability (0.0-1.0)
    rf_result = predict_single(transaction_id, user_id)

    # RF failure is non-critical — default to 0.0 so ensemble still works
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
    norm_rf     = fraud_probability  # already 0.0-1.0, no change needed

    # ── Step 5: Weighted average → single ensemble score ──────────────────────
    # RF gets most weight (0.50), rule engine second (0.35), Z-score least (0.15)
    # Weights sum to 1.0 so the result stays on a 0.0-1.0 scale
    final_score = (
        (norm_rf     * RF_WEIGHT)    +
        (norm_rule   * RULE_WEIGHT)  +
        (norm_zscore * ZSCORE_WEIGHT)
    )

    # ── Step 6: Map ensemble score to final decision ──────────────────────────
    # Thresholds: 0.0-0.30 APPROVE | 0.30-0.60 CHALLENGE | 0.60+ BLOCK
    final_decision = get_ensemble_decision(final_score)

    # ── Build and return the full result dict ─────────────────────────────────
    # Contains everything needed for the dashboard tab and audit trail
    return {
        # Identity
        "transaction_id":    transaction_id,
        "user_id":           user_id,

        # Rule engine outputs
        "risk_score":        risk_score,
        "rule_decision":     rule_result["decision"],
        "reason_codes":      reason_codes,
        "norm_rule":         round(norm_rule, 4),

        # Z-score outputs
        "anomaly_score":     round(anomaly_score, 4),
        "is_anomaly":        is_anomaly,
        "norm_zscore":       round(norm_zscore, 4),

        # Random Forest outputs
        "fraud_probability": fraud_probability,
        "rf_features":       rf_features,
        "norm_rf":           round(norm_rf, 4),

        # Ensemble outputs
        "ensemble_score":    round(final_score, 4),
        "final_decision":    final_decision,

        # Individual model weights used (useful for dashboard display)
        "weights": {
            "random_forest": RF_WEIGHT,
            "rule_engine":   RULE_WEIGHT,
            "zscore":        ZSCORE_WEIGHT,
        }
    }


# ══════════════════════════════════════════════════════════════════════════════
# BATCH EVALUATION — run ensemble across all transactions and measure performance
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_ensemble() -> dict:
    """
    Runs the ensemble across every transaction in the DB and evaluates
    the final_decision against fraud_labels ground truth.
    Prints full metrics for comparison against Phase 5 and individual models.

    Note: This is slow — it runs all 3 models per transaction.
    For 1,100 transactions expect ~30-60 seconds.
    """
    conn = get_db()

    # Pull every transaction with its session_id and user_id —
    # all three are required to call ensemble_score()
    rows = conn.execute("""
        SELECT t.transaction_id, t.session_id, a.user_id
        FROM transactions t
        JOIN accounts a ON t.account_id = a.account_id
    """).fetchall()

    # Pull ground truth labels for evaluation
    # fraud_labels was populated by Phase 1 generate_fraud_labels()
    labels = conn.execute("""
        SELECT transaction_id, is_fraud FROM fraud_labels
    """).fetchall()
    conn.close()

    # Build lookup dict: transaction_id → is_fraud (0 or 1)
    label_map = {r["transaction_id"]: r["is_fraud"] for r in labels}

    # Run ensemble on every transaction and tally confusion matrix counts
    TP = FP = FN = TN = 0
    total = 0

    for row in rows:
        tid        = row["transaction_id"]
        session_id = row["session_id"]
        user_id    = row["user_id"]

        # Skip transactions with no ground truth label
        if tid not in label_map:
            continue

        result = ensemble_score(tid, session_id, user_id)
        if not result:
            continue

        # Map final_decision to binary prediction —
        # BLOCK = predicted fraud, APPROVE/CHALLENGE = predicted legitimate
        predicted_fraud = result["final_decision"] == "BLOCK"
        actual_fraud    = bool(label_map[tid])

        if predicted_fraud and actual_fraud:
            TP += 1
        elif predicted_fraud and not actual_fraud:
            FP += 1
        elif not predicted_fraud and actual_fraud:
            FN += 1
        else:
            TN += 1

        total += 1

    # Calculate final metrics
    precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
    recall    = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    metrics = {
        "total":     total,
        "TP":        TP,
        "FP":        FP,
        "FN":        FN,
        "TN":        TN,
        "precision": round(precision, 4),
        "recall":    round(recall, 4),
        "f1":        round(f1, 4),
    }

    # Print full comparison across all models
    print("\n" + "=" * 55)
    print("  ENSEMBLE MODEL — EVALUATION RESULTS")
    print("=" * 55)
    print(f"  Total Scored   : {total}")
    print(f"  True Positives : {TP}")
    print(f"  False Positives: {FP}")
    print(f"  False Negatives: {FN}")
    print(f"  True Negatives : {TN}")
    print(f"  Precision      : {metrics['precision']}")
    print(f"  Recall         : {metrics['recall']}")
    print(f"  F1 Score       : {metrics['f1']}")
    print("=" * 55)
    print("\n  Model Comparison:")
    print("  Phase 5 Rule Engine: Precision 0.908 | Recall 0.690 | F1 0.784")
    print("  Z-Score Model:       Precision 0.571 | Recall 0.040 | F1 0.075")
    print("  Random Forest:       Precision 0.950 | Recall 0.950 | F1 0.950")
    print(f"  Ensemble:            Precision {metrics['precision']} | Recall {metrics['recall']} | F1 {metrics['f1']}")
    print("=" * 55 + "\n")

    return metrics


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT — run ensemble evaluation directly from terminal
# ══════════════════════════════════════════════════════════════════════════════

# When you run: python -m phase6.ensemble
# this evaluates the full ensemble across all 1,100 transactions
if __name__ == "__main__":
    evaluate_ensemble()