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
  7. STRUCTURING_DETECTED   +25  ← NEW: repeated identical amounts at regular intervals
"""

import sqlite3
import uuid
import statistics
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/fraud.db")


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# DECISION THRESHOLDS
# ══════════════════════════════════════════════════════════════════════════════

def get_decision(score: int) -> str:
    """
    Converts risk score to decision string.
      0  - 30  → APPROVE
      31 - 70  → CHALLENGE
      71 - 100 → BLOCK
    """
    if score <= 30:
        return "APPROVE"
    elif score <= 70:
        return "CHALLENGE"
    else:
        return "BLOCK"


# ══════════════════════════════════════════════════════════════════════════════
# RULE 7 — STRUCTURING DETECTION (NEW)
# ══════════════════════════════════════════════════════════════════════════════

def check_structuring(account_id: str, amount: float, conn: sqlite3.Connection) -> bool:
    """
    Detects structuring (smurfing) — a pattern where an attacker submits
    repeated near-identical transaction amounts from the same account
    at suspiciously regular time intervals within a 20-minute window.

    This is a deliberate, sophisticated fraud technique used to:
    - Stay below detection thresholds
    - Slowly poison the user's behavioral baseline
    - Automate fraud using bots (regular intervals are a bot fingerprint)

    Detection logic:
    1. Query transactions: same account, amount within ±5%, last 20 minutes
    2. Require at least 3 matching transactions (2 could be coincidence)
    3. Calculate time gaps between consecutive transactions
    4. Flag if standard deviation of gaps < 20% of average gap
       → Low std dev = metronomic regularity = likely automated

    Returns:
        True  → structuring pattern detected, add +25 to risk score
        False → no pattern detected
    """
    rows = conn.execute("""
        SELECT amount, timestamp
        FROM transactions
        WHERE account_id = ?
          AND amount BETWEEN ? * 0.95 AND ? * 1.05
          AND timestamp >= datetime('now', '-20 minutes')
        ORDER BY timestamp ASC
    """, (account_id, amount, amount)).fetchall()

    # Need at least 3 to form a pattern — 2 could be coincidence
    if len(rows) < 3:
        return False

    # Parse timestamps and calculate consecutive gaps in seconds
    try:
        timestamps = [datetime.fromisoformat(r["timestamp"]) for r in rows]
    except (ValueError, TypeError):
        return False

    gaps = [
        (timestamps[i + 1] - timestamps[i]).total_seconds()
        for i in range(len(timestamps) - 1)
    ]

    if not gaps:
        return False

    avg_gap = sum(gaps) / len(gaps)

    # Avoid division by zero — if avg_gap is 0 something is wrong
    if avg_gap <= 0:
        return False

    std_dev = statistics.stdev(gaps) if len(gaps) > 1 else 0

    # Flag if intervals are suspiciously regular
    # std_dev < 20% of avg_gap = metronomic = likely bot-driven
    return std_dev < (avg_gap * 0.20)


# ══════════════════════════════════════════════════════════════════════════════
# CORE RISK ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def score_transaction(transaction_id: str, session_id: str) -> dict | None:
    """
    Core scoring engine. Fetches all related data, applies 7 risk rules,
    calculates a score 0-100, determines decision, writes alert to DB,
    and returns a result dictionary.

    Risk Rules:
        VPN_DETECTED        +20  — VPN active during session
        HIGH_AMOUNT         +25  — Amount > 3x user's average
        UNUSUAL_LOCATION    +15  — Location differs from user's usual
        NEW_DEVICE          +15  — Device differs from user's typical
        UNUSUAL_LOGIN_HOUR  +10  — Login hour > 3h from typical
        HIGH_VELOCITY       +15  — >3 transactions from account in 10 mins
        STRUCTURING         +25  — Repeated identical amounts at regular intervals

    Returns:
        dict with alert_id, transaction_id, user_id, amount, merchant,
        location, device, vpn, risk_score, decision, reason_codes, timestamp
        or None on error.
    """
    conn = get_db()
    score = 0
    reason_codes = []

    try:
        # ── Fetch transaction ─────────────────────────────────────────────────
        txn = conn.execute("""
            SELECT t.*, a.user_id, a.account_id
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE t.transaction_id = ?
        """, (transaction_id,)).fetchone()

        if not txn:
            return None

        # ── Fetch session ─────────────────────────────────────────────────────
        session = conn.execute("""
            SELECT * FROM sessions WHERE session_id = ?
        """, (session_id,)).fetchone()

        if not session:
            return None

        # ── Fetch behavior profile ────────────────────────────────────────────
        profile = conn.execute("""
            SELECT * FROM behavior_profiles WHERE user_id = ?
        """, (txn["user_id"],)).fetchone()

        # ── RULE 1: VPN_DETECTED ─────────────────────────────────────────────
        if session["vpn_detected"]:
            score += 20
            reason_codes.append("VPN_DETECTED")

        # ── RULE 2: HIGH_AMOUNT ───────────────────────────────────────────────
        if profile and profile["avg_transaction_amount"]:
            if txn["amount"] > (profile["avg_transaction_amount"] * 3):
                score += 25
                reason_codes.append("HIGH_AMOUNT")

        # ── RULE 3: UNUSUAL_LOCATION ──────────────────────────────────────────
        if profile and profile["usual_location"]:
            if txn["location"].lower() != profile["usual_location"].lower():
                score += 15
                reason_codes.append("UNUSUAL_LOCATION")

        # ── RULE 4: NEW_DEVICE ────────────────────────────────────────────────
        if profile and profile["typical_device"]:
            if session["device_type"].lower() != profile["typical_device"].lower():
                score += 15
                reason_codes.append("NEW_DEVICE")

        # ── RULE 5: UNUSUAL_LOGIN_HOUR ────────────────────────────────────────
        if profile and profile["typical_login_hour"] is not None:
            try:
                login_hour = datetime.fromisoformat(session["login_time"]).hour
                hour_diff = abs(login_hour - profile["typical_login_hour"])
                # Wrap around midnight
                hour_diff = min(hour_diff, 24 - hour_diff)
                if hour_diff > 3:
                    score += 10
                    reason_codes.append("UNUSUAL_LOGIN_HOUR")
            except (ValueError, TypeError):
                pass

        # ── RULE 6: HIGH_VELOCITY ─────────────────────────────────────────────
        recent_count = conn.execute("""
            SELECT COUNT(*) as cnt
            FROM transactions
            WHERE account_id = ?
              AND timestamp >= datetime('now', '-10 minutes')
        """, (txn["account_id"],)).fetchone()["cnt"]

        if recent_count > 3:
            score += 15
            reason_codes.append("HIGH_VELOCITY")

        # ── RULE 7: STRUCTURING_DETECTED ─────────────────────────────────────
        if check_structuring(txn["account_id"], txn["amount"], conn):
            score += 25
            reason_codes.append("STRUCTURING_DETECTED")

        # ── Cap score at 100 ──────────────────────────────────────────────────
        score = min(score, 100)

        # ── Determine decision ────────────────────────────────────────────────
        decision = get_decision(score)

        # ── Write alert to DB ─────────────────────────────────────────────────
        alert_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        conn.execute("""
            INSERT INTO alerts
            (alert_id, transaction_id, risk_score, decision, reason_codes, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
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
            "alert_id":     alert_id,
            "transaction_id": transaction_id,
            "user_id":      txn["user_id"],
            "amount":       txn["amount"],
            "merchant":     txn["merchant"],
            "location":     txn["location"],
            "device":       session["device_type"],
            "vpn":          bool(session["vpn_detected"]),
            "risk_score":   score,
            "decision":     decision,
            "reason_codes": reason_codes,
            "timestamp":    timestamp,
        }

    except Exception as e:
        print(f"[risk_engine] Error scoring transaction: {e}")
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