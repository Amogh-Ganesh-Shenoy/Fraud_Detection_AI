"""
UAE Fraud Detection AI — Phase 6
Random Forest Classifier
Author: Amogh Ganesh Shenoy

How it works:
    Supervised ML model trained on 8 engineered features derived from
    transactions, sessions, behavior_profiles, and fraud_labels tables.
    predict_single() is called at runtime by ensemble.py.
    All other functions are offline training/evaluation tools.
"""

import os
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
import psycopg
from psycopg.rows import dict_row

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

from dotenv import load_dotenv

load_dotenv()

# DATABASE_URL points to Render's managed PostgreSQL in production
# Loaded from .env locally, injected as environment variable on Render
DATABASE_URL = os.getenv("DATABASE_URL")

# Path where the trained model is saved as a .pkl file
# Loaded by predict_single() at runtime — no retraining needed
MODEL_PATH = "phase6/random_forest.pkl"

# Fraud probability threshold — predictions above 0.5 are classified as fraud
FRAUD_THRESHOLD = 0.5


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_db():
    # Connects to PostgreSQL using DATABASE_URL from environment
    # RealDictCursor returns rows as dicts — row["amount"] not row[0]
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE ENGINEERING — offline training only
# ══════════════════════════════════════════════════════════════════════════════

def build_feature_matrix() -> pd.DataFrame:
    """
    Pulls raw data from 5 tables and engineers 8 features for training.
    Offline only — not called at runtime.

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

    # Pull all transactions with account and user context
    # Source: transactions + accounts tables
    cur.execute("""
        SELECT
            t.transaction_id, t.account_id, t.session_id,
            t.amount, t.location AS txn_location, t.timestamp, a.user_id
        FROM transactions t
        JOIN accounts a ON t.account_id = a.account_id
    """)
    transactions = cur.fetchall()

    # Pull all sessions indexed by session_id
    # Source: sessions table
    cur.execute("""
        SELECT session_id, vpn_detected, device_type,
               location AS login_location, login_time
        FROM sessions
    """)
    sessions    = cur.fetchall()
    session_map = {s["session_id"]: s for s in sessions}

    # Pull all behavior profiles indexed by user_id
    # Source: behavior_profiles table
    cur.execute("""
        SELECT user_id, avg_transaction_amount, usual_location,
               typical_device, typical_login_hour
        FROM behavior_profiles
    """)
    profiles    = cur.fetchall()
    profile_map = {p["user_id"]: p for p in profiles}

    # Pull ground truth fraud labels indexed by transaction_id
    # Source: fraud_labels table, populated by Phase 1
    cur.execute("SELECT transaction_id, is_fraud FROM fraud_labels")
    labels    = cur.fetchall()
    label_map = {r["transaction_id"]: r["is_fraud"] for r in labels}

    # Pull all velocity counts in one bulk query — replaces per-transaction DB calls
    # Self-join counts how many transactions from the same account fall within
    # ±10 minutes of each transaction — keyed by transaction_id for fast lookup
    cur.execute("""
        SELECT t1.transaction_id, COUNT(t2.transaction_id) AS cnt
        FROM transactions t1
        JOIN transactions t2 ON t1.account_id = t2.account_id
            AND t2.timestamp::timestamp >= t1.timestamp::timestamp - interval '10 minutes'
            AND t2.timestamp::timestamp <= t1.timestamp::timestamp + interval '10 minutes'
        GROUP BY t1.transaction_id
    """)
    velocity_rows  = cur.fetchall()
    velocity_map   = {r["transaction_id"]: r["cnt"] for r in velocity_rows}

    conn.close()

    rows = []
    for txn in transactions:
        tid        = txn["transaction_id"]
        user_id    = txn["user_id"]
        account_id = txn["account_id"]
        session    = session_map.get(txn["session_id"])
        profile    = profile_map.get(user_id)

        if not session or not profile:
            continue
        if tid not in label_map:
            continue

        # Engineer all 8 features — same logic as predict_single()
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

        # Look up precomputed velocity count — no DB call needed
        velocity_count = velocity_map.get(tid, 1)

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

    df = pd.DataFrame(rows)
    print(f"[RF] Feature matrix built: {len(df)} rows, {len(df.columns)} columns.")
    print(f"[RF] Fraud transactions: {df['is_fraud'].sum()} / {len(df)}")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# TRAINING — offline only
# ══════════════════════════════════════════════════════════════════════════════

def train_random_forest() -> tuple[RandomForestClassifier, pd.DataFrame]:
    """
    Builds the feature matrix, trains the Random Forest, saves the model.
    Offline only — not called at runtime. Run once locally to generate pkl.
    """
    df = build_feature_matrix()

    feature_cols = [
        "amount_ratio", "vpn_flag", "new_device_flag",
        "unusual_login_location", "unusual_txn_location",
        "login_txn_mismatch", "hour_deviation", "velocity_count",
    ]

    X = df[feature_cols]
    y = df["is_fraud"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(X_train, y_train)
    print(f"[RF] Model trained on {len(X_train)} transactions.")

    os.makedirs("phase6", exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"[RF] Model saved to {MODEL_PATH}")

    test_df = df.loc[X_test.index].copy()
    test_df["fraud_probability"] = model.predict_proba(X_test)[:, 1]
    test_df["predicted_fraud"]   = (test_df["fraud_probability"] >= FRAUD_THRESHOLD).astype(int)

    return model, test_df


# ══════════════════════════════════════════════════════════════════════════════
# EVALUATION — offline only
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_random_forest(model: RandomForestClassifier, test_df: pd.DataFrame) -> dict:
    """
    Evaluates the trained model on the held-out test set.
    Offline only — not called at runtime.
    """
    y_true = test_df["is_fraud"]
    y_pred = test_df["predicted_fraud"]
    y_prob = test_df["fraud_probability"]

    cm = confusion_matrix(y_true, y_pred)
    TN, FP, FN, TP = cm.ravel()

    precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
    recall    = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)
    auc       = roc_auc_score(y_true, y_prob)

    feature_cols = [
        "amount_ratio", "vpn_flag", "new_device_flag",
        "unusual_login_location", "unusual_txn_location",
        "login_txn_mismatch", "hour_deviation", "velocity_count",
    ]
    importances        = dict(zip(feature_cols, model.feature_importances_))
    sorted_importances = sorted(importances.items(), key=lambda x: x[1], reverse=True)

    print("\n" + "=" * 55)
    print("  RANDOM FOREST — EVALUATION RESULTS (Test Set 20%)")
    print("=" * 55)
    print(f"  Precision: {round(precision, 4)} | Recall: {round(recall, 4)} | F1: {round(f1, 4)} | AUC: {round(auc, 4)}")
    print("\n  Feature Importances:")
    for feat, imp in sorted_importances:
       print(f"    {feat}: {round(imp, 4)}")
    print("=" * 55 + "\n")

    return {
        "test_size":   len(test_df),
        "TP": int(TP), "FP": int(FP), "FN": int(FN), "TN": int(TN),
        "precision":   round(precision, 4),
        "recall":      round(recall, 4),
        "f1":          round(f1, 4),
        "auc":         round(auc, 4),
        "importances": importances,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE TRANSACTION PREDICTION — called at runtime by ensemble.py
# ══════════════════════════════════════════════════════════════════════════════

def predict_single(transaction_id: str, user_id: str) -> dict | None:
    """
    Loads the saved model and predicts fraud probability for a single transaction.
    Called by phase6/ensemble.py → ensemble_score() at runtime.

    Data sources:
        transactions + accounts — amount, location, timestamp, account_id
        sessions                — vpn_detected, device_type, login city, login_time
        behavior_profiles       — avg_transaction_amount, usual_location,
                                  typical_device, typical_login_hour
    """
    # Load the saved model from disk — trained locally and pushed to GitHub
    # No retraining needed at runtime — pkl file is loaded once per request
    if not os.path.exists(MODEL_PATH):
        print(f"[RF] Model not found at {MODEL_PATH}. Run train_random_forest() first.")
        return None

    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    conn = get_db()

    try:
        cur = conn.cursor()

        # Pull transaction, session, and profile for feature engineering
        # Same joins and logic as build_feature_matrix() for consistency
        cur.execute("""
            SELECT t.amount, t.location AS txn_location, t.timestamp,
                   t.session_id, t.account_id, a.user_id
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE t.transaction_id = %s
        """, (transaction_id,))
        txn = cur.fetchone()

        if not txn:
            return None

        cur.execute("""
            SELECT vpn_detected, device_type,
                   location AS login_location, login_time
            FROM sessions WHERE session_id = %s
        """, (txn["session_id"],))
        session = cur.fetchone()

        cur.execute("""
            SELECT avg_transaction_amount, usual_location,
                   typical_device, typical_login_hour
            FROM behavior_profiles WHERE user_id = %s
        """, (user_id,))
        profile = cur.fetchone()

        if not session or not profile:
            return None

        # Engineer the same 8 features as training — order and logic must match exactly
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
            login_hour     = datetime.fromisoformat(str(session["login_time"])).hour
            hour_diff      = abs(login_hour - profile["typical_login_hour"])
            hour_deviation = min(hour_diff, 24 - hour_diff)
        except (ValueError, TypeError):
            hour_deviation = 0

        # Velocity count — transactions from same account within ±10 minutes
        # interval syntax replaces SQLite's datetime() function for PostgreSQL
        cur.execute("""
            SELECT COUNT(*) as cnt FROM transactions
            WHERE account_id = %s
              AND timestamp::timestamp >= %s::timestamp - interval '10 minutes'
              AND timestamp::timestamp <= %s::timestamp + interval '10 minutes'
        """, (txn["account_id"], txn["timestamp"], txn["timestamp"]))
        velocity_count = cur.fetchone()["cnt"]

        # Build named DataFrame — matches training column order exactly
        # Prevents sklearn feature name warnings on prediction
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
        # index 1 = probability of fraud
        fraud_probability = model.predict_proba(features)[0][1]
        is_fraud          = fraud_probability >= FRAUD_THRESHOLD

        return {
            "transaction_id":    transaction_id,
            "user_id":           user_id,
            "fraud_probability": round(fraud_probability, 4),
            "is_fraud":          is_fraud,
            "threshold":         FRAUD_THRESHOLD,
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


if __name__ == "__main__":
    model, test_df = train_random_forest()
    evaluate_random_forest(model, test_df)