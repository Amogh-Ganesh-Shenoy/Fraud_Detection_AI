"""
phase5/batch_sim.py
-------------------
Batch simulation for Phase 5 — Model Evaluation.

Loops through all transactions in the database, computes rule engine
scores in memory (no DB calls per transaction, no alerts written),
and returns a merged DataFrame containing:
    - Engine outputs  : risk_score, decision, reason_codes, predicted_fraud
    - Ground truth    : is_fraud (from fraud_labels table)

Binary mapping:
    BLOCK              → predicted_fraud = 1
    APPROVE / CHALLENGE → predicted_fraud = 0
"""

import statistics
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

from phase3.location_risk import score_location_risk

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn


def get_decision(score: int) -> str:
    if score <= 30:
        return "APPROVE"
    elif score <= 70:
        return "CHALLENGE"
    else:
        return "BLOCK"


def run_batch_simulation() -> pd.DataFrame:

    conn = get_db()
    cur  = conn.cursor()

    # ── SECTION: Fetch all data in bulk ──────────────────────────────
    # Pull all transactions with account and user context
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
               location, login_time
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

    # Pull velocity counts in one bulk query
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

    conn.close()

    # ── SECTION: Compute rule engine scores in memory ─────────────────
    # No DB calls per transaction — no alerts written
    results = []
    for txn in transactions:
        tid        = txn["transaction_id"]
        user_id    = txn["user_id"]
        session    = session_map.get(txn["session_id"])
        profile    = profile_map.get(user_id)

        if not session or not profile:
            continue

        score        = 0
        reason_codes = []

        # RULE 1: VPN_DETECTED
        if session["vpn_detected"]:
            score += 20
            reason_codes.append("VPN_DETECTED")

        # RULE 2: HIGH_AMOUNT — tiered
        avg   = float(profile["avg_transaction_amount"]) or 1.0
        ratio = float(txn["amount"]) / avg
        if ratio >= 4.3:
            score += 75
            reason_codes.append("HIGH_AMOUNT")
        elif ratio >= 3.6:
            score += 65
            reason_codes.append("HIGH_AMOUNT")
        elif ratio >= 2.9:
            score += 50
            reason_codes.append("HIGH_AMOUNT")
        elif ratio >= 2.2:
            score += 35
            reason_codes.append("HIGH_AMOUNT")
        elif ratio >= 1.5:
            score += 25
            reason_codes.append("HIGH_AMOUNT")

        # RULE 3: LOCATION RISK
        if profile["usual_location"]:
            location_score, location_reasons = score_location_risk(
                login_city=session["location"],
                txn_city=txn["txn_location"],
                usual_city=profile["usual_location"],
            )
            score += location_score
            reason_codes.extend(location_reasons)

        # RULE 4: NEW_DEVICE
        if profile["typical_device"]:
            if session["device_type"].lower() != profile["typical_device"].lower():
                score += 15
                reason_codes.append("NEW_DEVICE")

        # RULE 5: UNUSUAL_LOGIN_HOUR
        if profile["typical_login_hour"] is not None:
            try:
                login_hour = datetime.fromisoformat(str(session["login_time"])).hour
                hour_diff  = abs(login_hour - profile["typical_login_hour"])
                hour_diff  = min(hour_diff, 24 - hour_diff)
                if hour_diff > 3:
                    score += 10
                    reason_codes.append("UNUSUAL_LOGIN_HOUR")
            except (ValueError, TypeError):
                pass

        # RULE 6: HIGH_VELOCITY
        velocity_count = velocity_map.get(tid, 1)
        if velocity_count > 3:
            score += 75
            reason_codes.append("HIGH_VELOCITY")

        decision = get_decision(score)

        results.append({
            "transaction_id": tid,
            "risk_score":     score,
            "decision":       decision,
            "reason_codes":   ", ".join(reason_codes),
        })

    # ── SECTION: Build DataFrame ──────────────────────────────────────
    df = pd.DataFrame(results)
    print(f"Total results collected: {len(df)}")
    print("Decision value counts:")
    print(df["decision"].value_counts())

    # ── SECTION: Add Predicted Fraud Binary Column ────────────────────
    df["predicted_fraud"] = df["decision"].apply(lambda x: 1 if x == "BLOCK" else 0)

    # ── SECTION: Merge Ground Truth Labels ────────────────────────────
    fraud_labels_df = pd.DataFrame([
        {"transaction_id": k, "is_fraud": v} for k, v in label_map.items()
    ])
    df = df.merge(fraud_labels_df, on="transaction_id", how="left")
    df = df.dropna(subset=["is_fraud"])
    df["is_fraud"] = df["is_fraud"].astype(int)

    print(f"Predicted fraud count: {df['predicted_fraud'].sum()}")
    return df


if __name__ == "__main__":
    df = run_batch_simulation()

    TP = len(df[(df["predicted_fraud"] == 1) & (df["is_fraud"] == 1)])
    FP = len(df[(df["predicted_fraud"] == 1) & (df["is_fraud"] == 0)])
    FN = len(df[(df["predicted_fraud"] == 0) & (df["is_fraud"] == 1)])
    TN = len(df[(df["predicted_fraud"] == 0) & (df["is_fraud"] == 0)])

    precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
    recall    = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    print("\n" + "=" * 55)
    print("  PHASE 5 — RULE ENGINE EVALUATION RESULTS")
    print("=" * 55)
    print(f"  TP: {TP} | FP: {FP} | FN: {FN} | TN: {TN}")
    print(f"  Precision: {round(precision, 4)}")
    print(f"  Recall:    {round(recall, 4)}")
    print(f"  F1:        {round(f1, 4)}")
    print("=" * 55 + "\n")