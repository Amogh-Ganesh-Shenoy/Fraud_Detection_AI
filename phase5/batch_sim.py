"""
phase5/batch_sim.py
-------------------
Batch simulation for Phase 5 — Model Evaluation.

Loops through all 1,000 transactions in the database, runs each through
the Phase 3 risk engine, and returns a single merged DataFrame containing:
    - Engine outputs  : risk_score, decision, reason_codes, predicted_fraud
    - Ground truth    : is_fraud (from fraud_labels table)

Binary mapping:
    BLOCK              → predicted_fraud = 1
    APPROVE / CHALLENGE → predicted_fraud = 0
"""

import pandas as pd
from phase3.risk_engine import score_transaction, get_db


def run_batch_simulation() -> pd.DataFrame:
     import traceback
     traceback.print_stack()  # shows who called this function

    # ── SECTION: Fetch Transaction Data ─────────────────────────────
    # Pull all transaction_id + session_id pairs from the transactions table.
    # Both are needed to call score_transaction().
    # session_id lives on the transactions table as a foreign key.
     conn = get_db()
     rows = conn.execute(
        "SELECT transaction_id, session_id FROM transactions"
    ).fetchall()

    # ── SECTION: Fetch Fraud Labels ──────────────────────────────────
    # Pull all ground truth labels in ONE query — not inside the loop.
    # Fetching inside the loop would hit the database 1,000 times.
    # We merge these into the DataFrame at the end instead.
     
     fraud_labels = pd.read_sql(
        "SELECT transaction_id, is_fraud FROM fraud_labels", conn
    )
     conn.close()

    # ── SECTION: Run Batch Simulation ────────────────────────────────
    # Loop through every transaction and run it through the Phase 3 risk engine.
    # score_transaction() returns a dict with risk_score, decision, reason_codes etc.
    # If it returns None (error), log a warning and skip — do not crash the batch.
     results = []
     for row in rows:
        result = score_transaction(row["transaction_id"], row["session_id"])
        if result:
            results.append(result)
        else:
            print(f"[WARN] score_transaction returned None for {row['transaction_id']}")

    # ── SECTION: Build DataFrame ─────────────────────────────────────
    # Convert the list of result dicts into a pandas DataFrame.
    # Each dict key becomes a column — risk_score, decision, reason_codes etc.
     df = pd.DataFrame(results)
     print("Total results collected:", len(df))
     print("Decision value counts:")
     print(df["decision"].value_counts())
     print("Sample risk scores:", df["risk_score"].head(10).tolist())
    # ── SECTION: Add Predicted Fraud Binary Column ───────────────────
    # Map engine decisions to binary predictions for the confusion matrix.
    # BLOCK = 1 (fraud predicted) | APPROVE / CHALLENGE = 0 (not fraud predicted)
    # Uses a lambda — a one line function applied to every value in the decision column.
     df["predicted_fraud"] = df["decision"].apply(lambda x: 1 if x == "BLOCK" else 0)

    # ── SECTION: Merge Ground Truth Labels ───────────────────────────
    # Join the fraud_labels DataFrame into our results on transaction_id.
    # how="left" keeps all engine results even if a label is missing.
    # This gives us predicted_fraud vs is_fraud side by side — ready for metrics.
    # Some transactions may not have a corresponding row in fraud_labels.
    # These produce NaN in is_fraud after the left merge.
    # We drop them — they cannot be used for evaluation without a ground truth label.
     df = df.merge(fraud_labels, on="transaction_id", how="left")
     df = df.dropna(subset=["is_fraud"])
     
    # Cast is_fraud to integer — dropna leaves it as float
     df["is_fraud"] = df["is_fraud"].astype(int)

     print("Before return - decisions:", df["decision"].value_counts().to_dict())
     print("Before return - predicted_fraud sum:", df["predicted_fraud"].sum())
     return df