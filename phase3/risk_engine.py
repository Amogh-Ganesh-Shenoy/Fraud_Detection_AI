"""
UAE Fraud Detection AI — Phase 3
Rule-Based Risk Engine
Author: Amogh Ganesh Shenoy

Rules:
  1. VPN_DETECTED          +20
  2. HIGH_AMOUNT            +25
  3. UNUSUAL_LOCATION       +15
  4. NEW_DEVICE             +15
  5. UNUSUAL_LOGIN_HOUR     +10
  6. HIGH_VELOCITY          +15
  7. STRUCTURING_DETECTED   +25
"""

# Standard library imports
import uuid
import statistics
import os
from datetime import datetime, timedelta

import psycopg
from psycopg.rows import dict_row

from phase3.location_risk import score_location_risk
from dotenv import load_dotenv

load_dotenv()

# DATABASE_URL points to Render's managed PostgreSQL in production
# Loaded from .env locally, injected as environment variable on Render
DATABASE_URL = os.getenv("DATABASE_URL")


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_db():
    # Connects to PostgreSQL using DATABASE_URL from environment
    # RealDictCursor returns rows as dicts — row["amount"] not row[0]
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# DECISION THRESHOLDS
# ══════════════════════════════════════════════════════════════════════════════

def get_decision(score: int) -> str:
    """
    Converts risk score to decision string.
      0  - 30  → APPROVE
      31 - 70  → CHALLENGE
      71+      → BLOCK
    """
    if score <= 30:
        return "APPROVE"
    elif score <= 70:
        return "CHALLENGE"
    else:
        return "BLOCK"


# ══════════════════════════════════════════════════════════════════════════════
# CORE RISK ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def score_transaction(transaction_id: str, session_id: str) -> dict | None:
    """
    Core scoring engine. Fetches all related data, applies 7 risk rules,
    calculates a score, determines decision, writes alert to DB,
    and returns a result dictionary.

    Data sources:
        transactions + accounts — transaction amount, location, account_id
        sessions                — VPN status, device type, login city, login time
        behavior_profiles       — user's historical averages and typical behaviour

    Writes to:
        alerts table — alert_id, transaction_id, risk_score, decision,
                       reason_codes, timestamp
    """
    conn = get_db()
    score = 0
    reason_codes = []

    try:
        cur = conn.cursor()

        # ── Fetch transaction ─────────────────────────────────────────────────
        # JOINs accounts to get user_id and account_id alongside transaction data
        # Source: transactions table + accounts table
        cur.execute("""
            SELECT t.*, a.user_id, a.account_id
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE t.transaction_id = %s
        """, (transaction_id,))
        txn = cur.fetchone()

        if not txn:
            return None

        # ── Fetch session ─────────────────────────────────────────────────────
        # Source: sessions table, keyed by session_id
        cur.execute("""
            SELECT * FROM sessions WHERE session_id = %s
        """, (session_id,))
        session = cur.fetchone()

        if not session:
            return None

        # ── Fetch behavior profile ────────────────────────────────────────────
        # Source: behavior_profiles table, keyed by user_id
        # Built by Phase 1 generate_behavior_profiles()
        cur.execute("""
            SELECT * FROM behavior_profiles WHERE user_id = %s
        """, (txn["user_id"],))
        profile = cur.fetchone()

        # ── RULE 1: VPN_DETECTED ─────────────────────────────────────────────
        if session["vpn_detected"]:
            score += 20
            reason_codes.append("VPN_DETECTED")

        # ── RULE 2: HIGH_AMOUNT ───────────────────────────────────────────────
        # Flags if transaction amount exceeds 1.5x the user's average
        if profile and profile["avg_transaction_amount"]:
            if txn["amount"] > (profile["avg_transaction_amount"] * 1.5):
                score += 25
                reason_codes.append("HIGH_AMOUNT")

        # ── RULE 3: LOCATION RISK (3 sub-features) ───────────────────────────
        # Compares login city, transaction city, and usual city
        # Source: phase3/location_risk.py — pure Python, no DB queries
        if profile and profile["usual_location"]:
            location_score, location_reasons = score_location_risk(
                login_city=session["location"],
                txn_city=txn["location"],
                usual_city=profile["usual_location"],
            )
            score += location_score
            reason_codes.extend(location_reasons)

        # ── RULE 4: NEW_DEVICE ────────────────────────────────────────────────
        # Flags if session device differs from user's typical device
        if profile and profile["typical_device"]:
            if session["device_type"].lower() != profile["typical_device"].lower():
                score += 15
                reason_codes.append("NEW_DEVICE")

        # ── RULE 5: UNUSUAL_LOGIN_HOUR ────────────────────────────────────────
        # Flags if login hour deviates more than 3 hours from typical
        if profile and profile["typical_login_hour"] is not None:
            try:
                login_hour = datetime.fromisoformat(str(session["login_time"])).hour
                hour_diff = abs(login_hour - profile["typical_login_hour"])
                hour_diff = min(hour_diff, 24 - hour_diff)
                if hour_diff > 3:
                    score += 10
                    reason_codes.append("UNUSUAL_LOGIN_HOUR")
            except (ValueError, TypeError):
                pass

        # ── RULE 6: HIGH_VELOCITY ─────────────────────────────────────────────
        # Counts transactions from same account within ±10 minutes
        # NOW() replaces SQLite's datetime('now') for PostgreSQL compatibility
        cur.execute("""
            SELECT COUNT(*) as cnt
            FROM transactions
            WHERE account_id = %s
            AND timestamp >= %s::timestamp - interval '10 minutes'
            AND timestamp <= %s::timestamp + interval '10 minutes'
        """, (txn["account_id"], txn["timestamp"], txn["timestamp"]))
        recent_count = cur.fetchone()["cnt"]

        if recent_count > 3:
            score += 75
            reason_codes.append("HIGH_VELOCITY")

        # ── RULE 7: STRUCTURING_DETECTED ─────────────────────────────────────
        # Detects repeated near-identical amounts at regular intervals
        # Source: transactions table filtered by account_id and amount range
        cur.execute("""
            SELECT amount, timestamp
            FROM transactions
            WHERE account_id = %s
              AND amount BETWEEN %s * 0.95 AND %s * 1.05
              AND timestamp >= %s::timestamp - interval '20 minutes'
              AND timestamp <= %s::timestamp + interval '20 minutes'
            ORDER BY timestamp ASC
        """, (txn["account_id"], txn["amount"], txn["amount"], txn["timestamp"], txn["timestamp"]))
        struct_rows = cur.fetchall()

        if len(struct_rows) >= 3:
            try:
                timestamps = [datetime.fromisoformat(str(r["timestamp"])) for r in struct_rows]
                gaps = [
                    (timestamps[i + 1] - timestamps[i]).total_seconds()
                    for i in range(len(timestamps) - 1)
                ]
                if gaps:
                    avg_gap = sum(gaps) / len(gaps)
                    if avg_gap > 0:
                        std_dev = statistics.stdev(gaps) if len(gaps) > 1 else 0
                        if std_dev < (avg_gap * 0.20):
                            score += 25
                            reason_codes.append("STRUCTURING_DETECTED")
            except (ValueError, TypeError):
                pass

        # ── Determine decision ────────────────────────────────────────────────
        decision = get_decision(score)

        # ── Write alert to DB ─────────────────────────────────────────────────
        # Inserts into alerts table — read later by GET /alerts endpoint
        alert_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        cur.execute("""
            INSERT INTO alerts
            (alert_id, transaction_id, risk_score, decision, reason_codes, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            alert_id,
            transaction_id,
            score,
            decision,
            ", ".join(reason_codes),
            timestamp,
        ))
        conn.commit()

        # ── Build and return result dict ──────────────────────────────────────
        return {
            "alert_id":       alert_id,
            "transaction_id": transaction_id,
            "user_id":        txn["user_id"],
            "amount":         txn["amount"],
            "merchant":       txn["merchant"],
            "location":       txn["location"],
            "device":         session["device_type"],
            "vpn":            bool(session["vpn_detected"]),
            "risk_score":     score,
            "decision":       decision,
            "reason_codes":   reason_codes,
            "timestamp":      timestamp,
        }

    except Exception as e:
        print(f"[ERROR] score_transaction failed for {transaction_id}: {e}")
        return None

    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# TERMINAL TESTING HELPER
# ══════════════════════════════════════════════════════════════════════════════

def print_result(result: dict) -> None:
    """Pretty prints result dict for terminal testing."""
    if not result:
        print("No result returned.")
        return

    print("\n" + "=" * 55)
    print(f"  RISK SCORE  : {result['risk_score']} / 100")
    print(f"  DECISION    : {result['decision']}")
    print(f"  AMOUNT      : AED {result['amount']:,.2f}")
    print(f"  MERCHANT    : {result['merchant']}")
    print(f"  LOCATION    : {result['location']}")
    print(f"  DEVICE      : {result['device']}")
    print(f"  VPN         : {result['vpn']}")
    print(f"  REASONS     : {', '.join(result['reason_codes']) or 'None'}")
    print(f"  TIMESTAMP   : {result['timestamp']}")
    print("=" * 55 + "\n")