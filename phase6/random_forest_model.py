"""
UAE Fraud Detection AI — Phase 6
Random Forest Classifier
Author: Amogh Ganesh Shenoy

How it works:
    Supervised ML model trained on 8 engineered features derived from
    transactions, sessions, behavior_profiles, and fraud_labels tables.
    The model learns which combinations of features indicate fraud,
    then predicts a fraud_probability (0.0-1.0) for each transaction.

    Unlike the rule engine which uses hardcoded thresholds, the Random
    Forest learns where the thresholds should be from the data itself.

Features:
    amount_ratio            - transaction amount / user average
    vpn_flag                - VPN active during session (0/1)
    new_device_flag         - device differs from typical (0/1)
    unusual_login_location  - login city differs from usual (0/1)
    unusual_txn_location    - txn city differs from usual (0/1)
    login_txn_mismatch      - login city differs from txn city (0/1)
    hour_deviation          - abs(login_hour - typical_login_hour)
    velocity_count          - transactions in ±10 min window

Output:
    fraud_probability (0.0-1.0) per transaction
    is_fraud prediction (True/False) at threshold 0.5
"""

# Standard library and third-party imports
import sqlite3
import os
import pickle
from datetime import datetime

# numpy for array operations, pandas for tabular data handling
import numpy as np
import pandas as pd

# scikit-learn: the ML library powering the Random Forest
# RandomForestClassifier  - the model itself
# train_test_split        - splits data into training and evaluation sets
# classification_report   - prints precision/recall/F1 per class
# confusion_matrix        - builds the TP/FP/FN/TN table
# roc_auc_score           - computes AUC for comparison with Phase 5
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

from dotenv import load_dotenv

# Load DB_PATH from .env file — same pattern used across all phases
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/fraud.db")

# Path where the trained model will be saved as a .pkl file
# ensemble.py will load this file to make predictions without retraining
MODEL_PATH = "phase6/random_forest.pkl"

# Fraud probability threshold — predictions above 0.5 are classified as fraud
# This can be tuned later: lower = more sensitive, higher = more conservative
FRAUD_THRESHOLD = 0.5


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

# Opens a connection to the SQLite database.
# row_factory = sqlite3.Row lets us access columns by name (row["amount"])
# instead of by position (row[0])
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE ENGINEERING — build the training dataset from raw DB tables
# ══════════════════════════════════════════════════════════════════════════════

def build_feature_matrix() -> pd.DataFrame:
    """
    Pulls raw data from 4 tables and engineers the 8 features the
    Random Forest will train on. Each row in the output DataFrame
    represents one transaction with its feature values and ground truth label.

    Data sources:
        transactions      - amount, location, timestamp, session_id, account_id
        sessions          - vpn_detected, device_type, location, login_time
        behavior_profiles - avg_transaction_amount, usual_location,
                            typical_device, typical_login_hour
        accounts          - links transactions to users
        fraud_labels      - ground truth is_fraud label (0 or 1)

    Returns:
        pandas DataFrame with one row per transaction,
        columns = 8 features + transaction_id + is_fraud label
    """
    conn = get_db()

    # ── Pull all transactions with their account and user context ─────────────
    # We JOIN accounts to get user_id, which we need to look up
    # behavior_profiles and fraud_labels for each transaction
    transactions = conn.execute("""
        SELECT
            t.transaction_id,
            t.account_id,
            t.session_id,
            t.amount,
            t.location      AS txn_location,
            t.timestamp,
            a.user_id
        FROM transactions t
        JOIN accounts a ON t.account_id = a.account_id
    """).fetchall()

    # ── Pull all sessions indexed by session_id ───────────────────────────────
    # Sessions hold VPN status, device type, login city, and login time —
    # all needed for vpn_flag, new_device_flag, location, and hour features
    sessions = conn.execute("""
        SELECT session_id, vpn_detected, device_type, location AS login_location, login_time
        FROM sessions
    """).fetchall()

    # Build a lookup dict: session_id → session row
    # This avoids running a separate DB query for every transaction
    session_map = {s["session_id"]: s for s in sessions}

    # ── Pull all behavior profiles indexed by user_id ─────────────────────────
    # Profiles hold the user's historical average amount, usual location,
    # typical device, and typical login hour — all baseline comparison values
    profiles = conn.execute("""
        SELECT user_id, avg_transaction_amount, usual_location,
               typical_device, typical_login_hour
        FROM behavior_profiles
    """).fetchall()

    # Build a lookup dict: user_id → profile row
    profile_map = {p["user_id"]: p for p in profiles}

    # ── Pull ground truth fraud labels indexed by transaction_id ──────────────
    # fraud_labels was populated by generate_fraud_labels() and
    # generate_legitimate_labels() in Phase 1 — is_fraud = 1 or 0
    labels = conn.execute("""
        SELECT transaction_id, is_fraud FROM fraud_labels
    """).fetchall()

    # Build a lookup dict: transaction_id → is_fraud (0 or 1)
    label_map = {r["transaction_id"]: r["is_fraud"] for r in labels}

    conn.close()

    # ── Engineer features for each transaction ────────────────────────────────
    # Loop through every transaction and compute all 8 features by
    # combining data from the session, profile, and transaction itself
    rows = []
    for txn in transactions:
        tid        = txn["transaction_id"]
        user_id    = txn["user_id"]
        account_id = txn["account_id"]
        session    = session_map.get(txn["session_id"])
        profile    = profile_map.get(user_id)

        # Skip transactions where session or profile data is missing —
        # we cannot engineer meaningful features without both
        if not session or not profile:
            continue

        # Skip transactions that have no fraud label —
        # supervised learning requires a ground truth label for every row
        if tid not in label_map:
            continue

        # ── Feature 1: amount_ratio ───────────────────────────────────────────
        # How large is this transaction relative to the user's normal spending?
        # ratio > 1.0 means above average, ratio > 1.5 means HIGH_AMOUNT territory
        # Source: transactions.amount / behavior_profiles.avg_transaction_amount
        avg = profile["avg_transaction_amount"] or 1.0
        amount_ratio = txn["amount"] / avg

        # ── Feature 2: vpn_flag ───────────────────────────────────────────────
        # Was a VPN active during this session? 1 = yes, 0 = no
        # Source: sessions.vpn_detected
        vpn_flag = int(session["vpn_detected"])

        # ── Feature 3: new_device_flag ────────────────────────────────────────
        # Is the device used in this session different from the user's typical device?
        # 1 = new/unknown device, 0 = known device
        # Source: sessions.device_type vs behavior_profiles.typical_device
        new_device_flag = int(
            session["device_type"].lower() != profile["typical_device"].lower()
        )

        # ── Feature 4: unusual_login_location ─────────────────────────────────
        # Did the user log in from a city different from their usual location?
        # 1 = unusual login city, 0 = normal login city
        # Source: sessions.location vs behavior_profiles.usual_location
        unusual_login_location = int(
            session["login_location"].strip().lower() !=
            profile["usual_location"].strip().lower()
        )

        # ── Feature 5: unusual_txn_location ──────────────────────────────────
        # Did the transaction occur in a city different from the user's usual location?
        # 1 = unusual transaction city, 0 = normal transaction city
        # Source: transactions.location vs behavior_profiles.usual_location
        unusual_txn_location = int(
            txn["txn_location"].strip().lower() !=
            profile["usual_location"].strip().lower()
        )

        # ── Feature 6: login_txn_mismatch ────────────────────────────────────
        # Is the login city different from the transaction city?
        # Catches account takeover where attacker logs in remotely
        # but transaction city is elsewhere
        # Source: sessions.location vs transactions.location
        login_txn_mismatch = int(
            session["login_location"].strip().lower() !=
            txn["txn_location"].strip().lower()
        )

        # ── Feature 7: hour_deviation ─────────────────────────────────────────
        # How many hours away from the user's typical login hour is this session?
        # Wraps around midnight so e.g. 23:00 vs 01:00 = 2 hours not 22
        # Source: sessions.login_time vs behavior_profiles.typical_login_hour
        try:
            login_hour = datetime.fromisoformat(session["login_time"]).hour
            hour_diff  = abs(login_hour - profile["typical_login_hour"])
            hour_deviation = min(hour_diff, 24 - hour_diff)
        except (ValueError, TypeError):
            # If login_time is malformed, default to 0 deviation
            hour_deviation = 0

        # ── Feature 8: velocity_count ─────────────────────────────────────────
        # How many transactions occurred from this account within ±10 minutes
        # of this transaction's timestamp? High count = burst spending = Scenario A
        # Source: transactions table, filtered by account_id and timestamp window
        conn2 = get_db()
        velocity_count = conn2.execute("""
            SELECT COUNT(*) as cnt
            FROM transactions
            WHERE account_id = ?
              AND timestamp >= datetime(?, '-10 minutes')
              AND timestamp <= datetime(?, '+10 minutes')
        """, (account_id, txn["timestamp"], txn["timestamp"])).fetchone()["cnt"]
        conn2.close()

        # ── Assemble the feature row ──────────────────────────────────────────
        # Combine all 8 features with the transaction ID and ground truth label
        # into a single dict that becomes one row in the training DataFrame
        rows.append({
            "transaction_id":         tid,
            "amount_ratio":           round(amount_ratio, 4),
            "vpn_flag":               vpn_flag,
            "new_device_flag":        new_device_flag,
            "unusual_login_location": unusual_login_location,
            "unusual_txn_location":   unusual_txn_location,
            "login_txn_mismatch":     login_txn_mismatch,
            "hour_deviation":         hour_deviation,
            "velocity_count":         velocity_count,
            "is_fraud":               label_map[tid],
        })

    # Convert the list of dicts into a pandas DataFrame
    # Each row = one transaction, each column = one feature or label
    df = pd.DataFrame(rows)
    print(f"[RF] Feature matrix built: {len(df)} rows, {len(df.columns)} columns.")
    print(f"[RF] Fraud transactions: {df['is_fraud'].sum()} / {len(df)}")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# TRAINING — train the Random Forest on the feature matrix
# ══════════════════════════════════════════════════════════════════════════════

def train_random_forest() -> tuple[RandomForestClassifier, pd.DataFrame]:
    """
    Builds the feature matrix, splits into train/test sets,
    trains the Random Forest classifier, saves the model to disk,
    and returns the trained model and test set for evaluation.

    Train/test split: 80% training, 20% evaluation
    Random state fixed at 42 for reproducibility across runs

    Returns:
        (trained model, test DataFrame with predictions attached)
    """

    # ── Step 1: Build the full feature matrix from the DB ─────────────────────
    df = build_feature_matrix()

    # These are the exact 8 column names the model trains on —
    # order matters here and must stay consistent between training and prediction
    feature_cols = [
        "amount_ratio",
        "vpn_flag",
        "new_device_flag",
        "unusual_login_location",
        "unusual_txn_location",
        "login_txn_mismatch",
        "hour_deviation",
        "velocity_count",
    ]

    # ── Step 2: Separate features (X) from labels (y) ─────────────────────────
    # X = the 8 input features the model learns from
    # y = the ground truth is_fraud labels (0 or 1) the model tries to predict
    X = df[feature_cols]
    y = df["is_fraud"]

    # ── Step 3: Split into training and test sets ──────────────────────────────
    # 80% of data trains the model, 20% is held back for honest evaluation
    # stratify=y ensures both sets have the same fraud/legitimate ratio
    # random_state=42 makes the split reproducible across runs
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"[RF] Training set: {len(X_train)} rows | Test set: {len(X_test)} rows")

    # ── Step 4: Train the Random Forest classifier ────────────────────────────
    # n_estimators=100 means 100 decision trees — each trained on a random
    # subset of the data and features. Final prediction is majority vote.
    # class_weight="balanced" compensates for imbalanced data (100 fraud
    # vs 1000 legitimate) by giving fraud cases more weight during training
    # random_state=42 ensures tree construction is reproducible
    model = RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(X_train, y_train)
    print(f"[RF] Model trained on {len(X_train)} transactions.")

    # ── Step 5: Save the trained model to disk as a .pkl file ─────────────────
    # pickle serialises the trained model so ensemble.py can load it
    # later without retraining — this is standard ML deployment practice
    os.makedirs("phase6", exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"[RF] Model saved to {MODEL_PATH}")

    # ── Step 6: Attach predictions to the test set for evaluation ────────────
    # predict_proba returns [prob_legitimate, prob_fraud] for each transaction
    # we take column index 1 (prob_fraud) as our fraud_probability score
    test_df = df.loc[X_test.index].copy()
    test_df["fraud_probability"] = model.predict_proba(X_test)[:, 1]
    test_df["predicted_fraud"]   = (test_df["fraud_probability"] >= FRAUD_THRESHOLD).astype(int)

    return model, test_df


# ══════════════════════════════════════════════════════════════════════════════
# EVALUATION — measure model performance against Phase 5 baseline
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_random_forest(model: RandomForestClassifier, test_df: pd.DataFrame) -> dict:
    """
    Evaluates the trained Random Forest on the held-out test set.
    Prints confusion matrix, classification report, AUC, and feature
    importances — then compares against the Phase 5 rule engine baseline.

    Args:
        model:   the trained RandomForestClassifier
        test_df: test set DataFrame with fraud_probability and predicted_fraud columns

    Returns:
        metrics dict with TP, FP, FN, TN, precision, recall, F1, AUC
    """

    # ── Pull actual vs predicted labels from the test DataFrame ───────────────
    y_true = test_df["is_fraud"]
    y_pred = test_df["predicted_fraud"]
    y_prob = test_df["fraud_probability"]

    # ── Compute confusion matrix — TP, FP, FN, TN ────────────────────────────
    # confusion_matrix returns [[TN, FP], [FN, TP]] for binary classification
    cm = confusion_matrix(y_true, y_pred)
    TN, FP, FN, TP = cm.ravel()

    # ── Compute Precision, Recall, F1, and AUC ────────────────────────────────
    # Precision = of everything flagged as fraud, how many were actually fraud
    # Recall    = of all actual fraud, how many did we catch
    # F1        = harmonic mean of precision and recall
    # AUC       = area under ROC curve — measures overall discrimination ability
    precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
    recall    = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)
    auc       = roc_auc_score(y_true, y_prob)

    # ── Feature importances — which features the RF relied on most ────────────
    # Higher importance = that feature contributed more to the trees' decisions
    # This is useful for understanding what the model actually learned
    feature_cols = [
        "amount_ratio", "vpn_flag", "new_device_flag",
        "unusual_login_location", "unusual_txn_location",
        "login_txn_mismatch", "hour_deviation", "velocity_count",
    ]
    importances = dict(zip(feature_cols, model.feature_importances_))
    sorted_importances = sorted(importances.items(), key=lambda x: x[1], reverse=True)

    # ── Print full evaluation report ──────────────────────────────────────────
    print("\n" + "=" * 55)
    print("  RANDOM FOREST — EVALUATION RESULTS (Test Set 20%)")
    print("=" * 55)
    print(f"  Test Set Size  : {len(test_df)}")
    print(f"  True Positives : {TP}")
    print(f"  False Positives: {FP}")
    print(f"  False Negatives: {FN}")
    print(f"  True Negatives : {TN}")
    print(f"  Precision      : {round(precision, 4)}")
    print(f"  Recall         : {round(recall, 4)}")
    print(f"  F1 Score       : {round(f1, 4)}")
    print(f"  AUC            : {round(auc, 4)}")
    print("=" * 55)
    print("\n  Phase 5 Baseline for comparison:")
    print("  Precision: 0.908 | Recall: 0.690 | F1: 0.784 | AUC: 0.8916")
    print("=" * 55)
    print("\n  Feature Importances (highest → lowest):")
    for feat, imp in sorted_importances:
        bar = "█" * int(imp * 50)
        print(f"  {feat:<28} {imp:.4f}  {bar}")
    print("=" * 55 + "\n")

    return {
        "test_size":  len(test_df),
        "TP":         int(TP),
        "FP":         int(FP),
        "FN":         int(FN),
        "TN":         int(TN),
        "precision":  round(precision, 4),
        "recall":     round(recall, 4),
        "f1":         round(f1, 4),
        "auc":        round(auc, 4),
        "importances": importances,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE TRANSACTION PREDICTION — used by ensemble.py at runtime
# ══════════════════════════════════════════════════════════════════════════════

def predict_single(transaction_id: str, user_id: str) -> dict | None:
    """
    Loads the saved model and predicts fraud probability for a single
    transaction. Called by ensemble.py during live scoring.

    Args:
        transaction_id: UUID of the transaction to score
        user_id:        UUID of the account owner

    Returns:
        dict with fraud_probability, is_fraud prediction, and feature values
        or None on error
    """

    # ── Load the saved model from disk ────────────────────────────────────────
    # The model was serialised to random_forest.pkl during training.
    # We load it here so ensemble.py doesn't need to retrain every time.
    if not os.path.exists(MODEL_PATH):
        print(f"[RF] Model not found at {MODEL_PATH}. Run train_random_forest() first.")
        return None

    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    conn = get_db()

    try:
        # ── Pull the transaction, session, and profile for this transaction ────
        # Same joins as build_feature_matrix() but for a single transaction
        txn = conn.execute("""
            SELECT t.amount, t.location AS txn_location, t.timestamp,
                   t.session_id, t.account_id, a.user_id
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE t.transaction_id = ?
        """, (transaction_id,)).fetchone()

        if not txn:
            return None

        # Pull the session for this transaction
        session = conn.execute("""
            SELECT vpn_detected, device_type, location AS login_location, login_time
            FROM sessions WHERE session_id = ?
        """, (txn["session_id"],)).fetchone()

        # Pull the user's behavior profile for baseline comparison values
        profile = conn.execute("""
            SELECT avg_transaction_amount, usual_location,
                   typical_device, typical_login_hour
            FROM behavior_profiles WHERE user_id = ?
        """, (user_id,)).fetchone()

        if not session or not profile:
            return None

        # ── Engineer the same 8 features as build_feature_matrix() ───────────
        # Must be in the exact same order and logic as training —
        # any mismatch would cause incorrect predictions
        avg          = profile["avg_transaction_amount"] or 1.0
        amount_ratio = txn["amount"] / avg
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
            login_hour     = datetime.fromisoformat(session["login_time"]).hour
            hour_diff      = abs(login_hour - profile["typical_login_hour"])
            hour_deviation = min(hour_diff, 24 - hour_diff)
        except (ValueError, TypeError):
            hour_deviation = 0

        velocity_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM transactions
            WHERE account_id = ?
              AND timestamp >= datetime(?, '-10 minutes')
              AND timestamp <= datetime(?, '+10 minutes')
        """, (txn["account_id"], txn["timestamp"], txn["timestamp"])).fetchone()["cnt"]

        # ── Build feature DataFrame and run prediction ────────────────────────
        # IMPORTANT: we wrap the features in a pandas DataFrame with named
        # columns instead of a raw numpy array. The model was trained on a
        # DataFrame with named columns — passing a nameless numpy array causes
        # sklearn to fire a UserWarning on every prediction call. Named columns
        # eliminate the warning and ensure feature order is always correct.
        feature_cols = [
            "amount_ratio", "vpn_flag", "new_device_flag",
            "unusual_login_location", "unusual_txn_location",
            "login_txn_mismatch", "hour_deviation", "velocity_count",
        ]
        features = pd.DataFrame([[
            amount_ratio, vpn_flag, new_device_flag,
            unusual_login_location, unusual_txn_location,
            login_txn_mismatch, hour_deviation, velocity_count
        ]], columns=feature_cols)

        # predict_proba returns [[prob_legit, prob_fraud]]
        # we take index 1 = probability of fraud
        fraud_probability = model.predict_proba(features)[0][1]
        is_fraud          = fraud_probability >= FRAUD_THRESHOLD

        return {
            "transaction_id":         transaction_id,
            "user_id":                user_id,
            "fraud_probability":      round(fraud_probability, 4),
            "is_fraud":               is_fraud,
            "threshold":              FRAUD_THRESHOLD,
            "features": {
                "amount_ratio":           round(amount_ratio, 4),
                "vpn_flag":               vpn_flag,
                "new_device_flag":        new_device_flag,
                "unusual_login_location": unusual_login_location,
                "unusual_txn_location":   unusual_txn_location,
                "login_txn_mismatch":     login_txn_mismatch,
                "hour_deviation":         hour_deviation,
                "velocity_count":         velocity_count,
            }
        }

    except Exception as e:
        print(f"[RF ERROR] predict_single failed for {transaction_id}: {e}")
        return None

    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT — train and evaluate directly from terminal
# ══════════════════════════════════════════════════════════════════════════════

# When you run: python -m phase6.random_forest_model
# this trains the model, evaluates it, and prints the full metrics report
if __name__ == "__main__":
    model, test_df = train_random_forest()
    evaluate_random_forest(model, test_df)