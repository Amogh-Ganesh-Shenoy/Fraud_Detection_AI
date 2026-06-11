"""
UAE Fraud Detection AI — Phase 6
Z-Score Anomaly Detection Model
Author: Amogh Ganesh Shenoy

How it works:
    For each incoming transaction, calculate how many standard deviations
    the amount is from that user's historical average:

        Z = (transaction_amount - avg_amount) / std_deviation

    If Z exceeds the threshold (2.5), flag as anomaly.
"""

import statistics
import os
from datetime import datetime
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

load_dotenv()

# DATABASE_URL points to Render's managed PostgreSQL in production
# Loaded from .env locally, injected as environment variable on Render
DATABASE_URL = os.getenv("DATABASE_URL")

# Z-score threshold — anything 2.5 standard deviations above the user's
# mean amount is considered a statistical anomaly
ZSCORE_THRESHOLD = 2.5


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_db():
    # Connects to PostgreSQL using DATABASE_URL from environment
    # RealDictCursor returns rows as dicts — row["amount"] not row[0]
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# CORE Z-SCORE FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def score_zscore(transaction_id: str, user_id: str) -> dict | None:
    """
    Computes the Z-score anomaly score for a single transaction.
    Called by phase6/ensemble.py → ensemble_score() at runtime.

    Data sources:
        transactions    — transaction amount, account_id
        accounts        — links transaction to user
        behavior_profiles — user's avg_transaction_amount baseline
    """
    conn = get_db()

    try:
        cur = conn.cursor()

        # ── Step 1: Pull transaction amount ───────────────────────────────────
        # JOINs accounts to get account_id for historical amount lookup
        # Source: transactions + accounts tables
        cur.execute("""
            SELECT t.amount, a.account_id
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE t.transaction_id = %s
        """, (transaction_id,))
        txn = cur.fetchone()

        if not txn:
            print(f"[ZSCORE] Transaction {transaction_id} not found.")
            return None

        amount     = float (txn["amount"])
        account_id = txn["account_id"]

        # ── Step 2: Pull user's average amount from behavior_profiles ─────────
        # avg_transaction_amount was pre-computed by Phase 1
        # Source: behavior_profiles table, keyed by user_id
        cur.execute("""
            SELECT avg_transaction_amount
            FROM behavior_profiles
            WHERE user_id = %s
        """, (user_id,))
        profile = cur.fetchone()

        if not profile or not profile["avg_transaction_amount"]:
            print(f"[ZSCORE] No behavior profile found for user {user_id}.")
            return None

        avg_amount = float(profile["avg_transaction_amount"])

        # ── Step 3: Pull all historical amounts for std dev calculation ────────
        # Excludes the current transaction to avoid self-reference
        # Source: transactions table, filtered by account_id
        cur.execute("""
            SELECT amount
            FROM transactions
            WHERE account_id = %s
              AND transaction_id != %s
        """, (account_id, transaction_id))
        rows = cur.fetchall()

        historical_amounts = [float(r["amount"]) for r in rows]

        # ── Step 4: Compute std deviation — real if enough data, else fallback ─
        # Needs at least 3 values for a meaningful std deviation
        # Falls back to avg_amount as proxy for sparse users
        if len(historical_amounts) >= 3:
            std_dev        = statistics.stdev(historical_amounts)
            std_dev_source = "calculated"
        else:
            std_dev        = avg_amount
            std_dev_source = "fallback_avg"

        # Edge case: zero std dev means all amounts are identical
        # Fall back to avg_amount to avoid division by zero
        if std_dev == 0:
            std_dev        = avg_amount if avg_amount > 0 else 1.0
            std_dev_source = "fallback_avg"

        # ── Step 5: Compute Z-score and apply threshold ───────────────────────
        # High positive Z = unusually large transaction = statistical anomaly
        z_score    = (amount - avg_amount) / std_dev
        is_anomaly = z_score >= ZSCORE_THRESHOLD

        return {
            "transaction_id":  transaction_id,
            "user_id":         user_id,
            "amount":          round(amount, 2),
            "avg_amount":      round(avg_amount, 2),
            "std_dev":         round(std_dev, 2),
            "std_dev_source":  std_dev_source,
            "anomaly_score":   round(z_score, 4),
            "is_anomaly":      is_anomaly,
            "threshold":       ZSCORE_THRESHOLD,
        }

    except Exception as e:
        print(f"[ZSCORE ERROR] score_zscore failed for {transaction_id}: {e}")
        return None

    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# BATCH SCORING — offline evaluation only, not called at runtime
# ══════════════════════════════════════════════════════════════════════════════

def run_zscore_batch() -> list[dict]:
    """
    Scores every transaction in the database.
    Used for offline evaluation only — not called by any API endpoint.
    """
    conn = get_db()
    cur = conn.cursor()

    # Pull every transaction_id and its owning user_id
    # Source: transactions + accounts tables
    cur.execute("""
        SELECT t.transaction_id, a.user_id
        FROM transactions t
        JOIN accounts a ON t.account_id = a.account_id
    """)
    rows = cur.fetchall()
    conn.close()

    results = []
    for row in rows:
        result = score_zscore(row["transaction_id"], row["user_id"])
        if result:
            results.append(result)

    print(f"[ZSCORE] Scored {len(results)} transactions.")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# EVALUATION — offline only, not called at runtime
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_zscore() -> dict:
    """
    Evaluates Z-score model against fraud_labels ground truth.
    Offline only — not called at runtime.
    Pre-fetches all data in bulk — no per-transaction DB calls.
    """
    conn = get_db()
    cur  = conn.cursor()

    # Pull all transactions with account context
    cur.execute("""
        SELECT t.transaction_id, t.account_id, t.amount, a.user_id
        FROM transactions t
        JOIN accounts a ON t.account_id = a.account_id
    """)
    transactions = cur.fetchall()

    # Pull all behavior profiles indexed by user_id
    cur.execute("SELECT user_id, avg_transaction_amount FROM behavior_profiles")
    profiles    = cur.fetchall()
    profile_map = {p["user_id"]: p for p in profiles}

    # Pull all historical amounts per account for std dev calculation
    cur.execute("SELECT account_id, transaction_id, amount FROM transactions")
    all_amounts     = cur.fetchall()
    account_amounts = {}
    for r in all_amounts:
        account_amounts.setdefault(r["account_id"], []).append({
            "tid": r["transaction_id"],
            "amount": float(r["amount"])
        })

    # Pull fraud labels
    cur.execute("SELECT transaction_id, is_fraud FROM fraud_labels")
    labels    = cur.fetchall()
    label_map = {r["transaction_id"]: r["is_fraud"] for r in labels}

    conn.close()

    TP = FP = FN = TN = 0
    scored = 0

    for txn in transactions:
        tid        = txn["transaction_id"]
        user_id    = txn["user_id"]
        account_id = txn["account_id"]
        amount     = float(txn["amount"])

        if tid not in label_map:
            continue

        profile = profile_map.get(user_id)
        if not profile or not profile["avg_transaction_amount"]:
            continue

        avg_amount = float(profile["avg_transaction_amount"])

        # Historical amounts excluding current transaction
        historical = [
            r["amount"] for r in account_amounts.get(account_id, [])
            if r["tid"] != tid
        ]

        if len(historical) >= 3:
            std_dev = statistics.stdev(historical)
        else:
            std_dev = avg_amount

        if std_dev == 0:
            std_dev = avg_amount if avg_amount > 0 else 1.0

        z_score    = (amount - avg_amount) / std_dev
        is_anomaly = z_score >= ZSCORE_THRESHOLD

        scored += 1
        predicted_fraud = is_anomaly
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
        "total":     scored,
        "TP": TP, "FP": FP, "FN": FN, "TN": TN,
        "precision": round(precision, 4),
        "recall":    round(recall, 4),
        "f1":        round(f1, 4),
    }

    print("\n" + "=" * 50)
    print("  Z-SCORE MODEL — EVALUATION RESULTS")
    print("=" * 50)
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print("=" * 50 + "\n")

    return metrics


if __name__ == "__main__":
    evaluate_zscore()