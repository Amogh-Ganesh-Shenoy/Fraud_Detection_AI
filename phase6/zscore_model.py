"""
UAE Fraud Detection AI — Phase 6
Z-Score Anomaly Detection Model
Author: Amogh Ganesh Shenoy

How it works:
    For each incoming transaction, calculate how many standard deviations
    the amount is from that user's historical average:

        Z = (transaction_amount - avg_amount) / std_deviation

    If Z exceeds the threshold (2.5), flag as anomaly.

Fallback:
    If a user has fewer than 3 historical transactions, std deviation
    cannot be meaningfully computed. avg_amount is used as a proxy std dev.
    This will be refined as more transaction data accumulates per user.

Returns:
    {
        "anomaly_score":  float,   # raw Z-score
        "is_anomaly":     bool,    # True if Z >= threshold
        "threshold":      float,   # threshold used (2.5)
        "avg_amount":     float,   # user's historical average
        "std_dev":        float,   # std dev used (real or fallback)
        "std_dev_source": str,     # "calculated" or "fallback_avg"
        "transaction_id": str,
        "user_id":        str,
    }
"""

# Standard library imports for DB access, maths, and env loading
import sqlite3
import statistics
import os
from dotenv import load_dotenv

# Load environment variables from .env file (DB_PATH lives there)
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/fraud.db")

# The Z-score threshold: anything 2.5 standard deviations above the user's
# mean amount is considered a statistical anomaly and flagged for review
ZSCORE_THRESHOLD = 2.5


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

# Opens a connection to the SQLite database.
# row_factory = sqlite3.Row means results come back as named dicts
# (e.g. row["amount"]) instead of positional tuples (row[0])
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# CORE Z-SCORE FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def score_zscore(transaction_id: str, user_id: str) -> dict | None:
    """
    Computes the Z-score anomaly score for a single transaction.

    Steps:
        1. Fetch transaction amount from transactions table
        2. Fetch user avg_transaction_amount from behavior_profiles
        3. Fetch all historical amounts from transactions for this user
           to compute real std deviation
        4. If fewer than 3 historical transactions, fall back to
           avg_amount as std dev proxy
        5. Compute Z-score and flag if >= ZSCORE_THRESHOLD

    Args:
        transaction_id: UUID of the transaction to score
        user_id:        UUID of the user (account owner)

    Returns:
        Result dict or None on error
    """
    conn = get_db()

    try:
        # ── Step 1: Pull the transaction amount from the transactions table ───
        # We JOIN accounts so we can also get the account_id, which is needed
        # later to fetch the user's full transaction history for std dev calc
        txn = conn.execute("""
            SELECT t.amount, a.account_id
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE t.transaction_id = ?
        """, (transaction_id,)).fetchone()

        # If the transaction doesn't exist in the DB, bail out early
        if not txn:
            print(f"[ZSCORE] Transaction {transaction_id} not found.")
            return None

        amount     = txn["amount"]
        account_id = txn["account_id"]

        # ── Step 2: Pull the user's average amount from behavior_profiles ─────
        # behavior_profiles stores a pre-computed avg_transaction_amount
        # per user — this was built in Phase 1 generate_behavior_profiles()
        profile = conn.execute("""
            SELECT avg_transaction_amount
            FROM behavior_profiles
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        # If no profile exists for this user we cannot compute a Z-score
        if not profile or not profile["avg_transaction_amount"]:
            print(f"[ZSCORE] No behavior profile found for user {user_id}.")
            return None

        avg_amount = profile["avg_transaction_amount"]

        # ── Step 3: Pull ALL historical amounts for this account ──────────────
        # We pull every past transaction for this account (excluding the current
        # one) so we can compute a real standard deviation from actual history.
        # This gives us a per-user spread, not a global one.
        rows = conn.execute("""
            SELECT amount
            FROM transactions
            WHERE account_id = ?
              AND transaction_id != ?
        """, (account_id, transaction_id)).fetchall()

        # Convert the query rows into a plain Python list of floats
        historical_amounts = [r["amount"] for r in rows]

        # ── Step 4: Compute std deviation — real if enough data, else fallback ─
        # statistics.stdev() needs at least 2 values, but 3+ gives a
        # meaningful spread. With 1-2 values the result is too noisy to trust.
        if len(historical_amounts) >= 3:
            # Real std deviation calculated from the user's transaction history
            std_dev        = statistics.stdev(historical_amounts)
            std_dev_source = "calculated"
        else:
            # Fallback: not enough history to compute a real std dev.
            # We use avg_amount as a proxy — it's not statistically perfect
            # but it keeps the model functional for new/sparse users.
            # As transaction history grows, this path will be hit less often.
            std_dev        = avg_amount
            std_dev_source = "fallback_avg"

        # Edge case: if all historical transactions are the exact same amount,
        # std dev comes out as 0 — division by zero would crash the Z-score.
        # Fall back to avg_amount as a safe non-zero denominator.
        if std_dev == 0:
            std_dev        = avg_amount if avg_amount > 0 else 1.0
            std_dev_source = "fallback_avg"

        # ── Step 5: Compute Z-score and apply threshold ───────────────────────
        # Z = (current amount - user average) / standard deviation
        # A high positive Z means this transaction is unusually large
        # compared to what this user normally spends — statistical anomaly
        z_score    = (amount - avg_amount) / std_dev
        is_anomaly = z_score >= ZSCORE_THRESHOLD

        # Return everything ensemble.py will need to make a combined decision
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
        # Always close the DB connection whether we succeeded or hit an error
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# BATCH SCORING — score every transaction in the DB
# ══════════════════════════════════════════════════════════════════════════════

def run_zscore_batch() -> list[dict]:
    """
    Scores every transaction in the database.
    Used for evaluation and comparison against Phase 5 baseline.

    Returns:
        List of result dicts, one per transaction
    """
    conn = get_db()

    # Pull every transaction_id and its owning user_id by joining
    # transactions → accounts so we have the user_id for behavior_profiles lookup
    rows = conn.execute("""
        SELECT t.transaction_id, a.user_id
        FROM transactions t
        JOIN accounts a ON t.account_id = a.account_id
    """).fetchall()

    conn.close()

    # Score each transaction one at a time using score_zscore()
    # and collect all results into a list for evaluation
    results = []
    for row in rows:
        result = score_zscore(row["transaction_id"], row["user_id"])
        if result:
            results.append(result)

    print(f"[ZSCORE] Scored {len(results)} transactions.")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# EVALUATION — compare Z-score predictions against ground truth labels
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_zscore() -> dict:
    """
    Runs batch scoring and evaluates against fraud_labels ground truth.
    Prints and returns a metrics dict for comparison against Phase 5 baseline.

    Metrics:
        Precision = TP / (TP + FP)  — of everything flagged, how many were real fraud
        Recall    = TP / (TP + FN)  — of all real fraud, how many did we catch
        F1        = 2 * P * R / (P + R)  — harmonic mean of both
    """
    conn = get_db()

    # Pull the ground truth from fraud_labels — this is what Phase 1 generated.
    # is_fraud = 1 means it's a known fraud transaction, 0 means legitimate.
    labels = conn.execute("""
        SELECT transaction_id, is_fraud FROM fraud_labels
    """).fetchall()
    conn.close()

    # Build a lookup dict: transaction_id → is_fraud (0 or 1)
    # This lets us quickly check the true label for any transaction
    label_map = {r["transaction_id"]: r["is_fraud"] for r in labels}

    # Run the Z-score model across every transaction in the DB
    results = run_zscore_batch()

    # Compare each prediction against the ground truth label
    # and tally up the 4 possible outcomes:
    #   TP = flagged as anomaly AND actually fraud      (correct catch)
    #   FP = flagged as anomaly BUT actually legitimate (false alarm)
    #   FN = not flagged BUT actually fraud             (missed fraud)
    #   TN = not flagged AND actually legitimate        (correct clear)
    TP = FP = FN = TN = 0

    for result in results:
        tid            = result["transaction_id"]
        predicted_fraud = result["is_anomaly"]
        actual_fraud    = bool(label_map.get(tid, 0))

        if predicted_fraud and actual_fraud:
            TP += 1
        elif predicted_fraud and not actual_fraud:
            FP += 1
        elif not predicted_fraud and actual_fraud:
            FN += 1
        else:
            TN += 1

    # Calculate Precision, Recall, and F1 from the confusion matrix tallies
    precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
    recall    = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    metrics = {
        "total":     len(results),
        "TP":        TP,
        "FP":        FP,
        "FN":        FN,
        "TN":        TN,
        "precision": round(precision, 4),
        "recall":    round(recall, 4),
        "f1":        round(f1, 4),
    }

    # Print results alongside Phase 5 baseline so we can see the improvement
    print("\n" + "=" * 50)
    print("  Z-SCORE MODEL — EVALUATION RESULTS")
    print("=" * 50)
    print(f"  Total Scored   : {metrics['total']}")
    print(f"  True Positives : {TP}")
    print(f"  False Positives: {FP}")
    print(f"  False Negatives: {FN}")
    print(f"  True Negatives : {TN}")
    print(f"  Precision      : {metrics['precision']}")
    print(f"  Recall         : {metrics['recall']}")
    print(f"  F1 Score       : {metrics['f1']}")
    print("=" * 50)
    print("\n  Phase 5 Baseline for comparison:")
    print("  Precision: 0.908 | Recall: 0.690 | F1: 0.784")
    print("=" * 50 + "\n")

    return metrics


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT — run evaluation directly from terminal
# ══════════════════════════════════════════════════════════════════════════════

# When you run: python -m phase6.zscore_model
# this block executes evaluate_zscore() and prints the full metrics report
if __name__ == "__main__":
    evaluate_zscore()