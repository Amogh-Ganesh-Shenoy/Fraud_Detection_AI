import sqlite3
import os
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/fraud.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def get_decision(score):
    """Convert risk score to a decision."""
    if score <= 30:
        return "APPROVE"
    elif score <= 70:
        return "CHALLENGE"
    else:
        return "BLOCK"

def score_transaction(transaction_id, session_id):
    """
    Core risk engine — scores a transaction and writes result to alerts table.
    Returns a dict with score, decision and reason codes.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Fetch transaction
    cursor.execute("SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,))
    transaction = cursor.fetchone()
    if not transaction:
        conn.close()
        return {"error": "Transaction not found"}

    # Map transaction columns
    tx = {
        "transaction_id": transaction[0],
        "account_id":     transaction[1],
        "session_id":     transaction[2],
        "amount":         transaction[3],
        "currency":       transaction[4],
        "merchant":       transaction[5],
        "type":           transaction[6],
        "location":       transaction[7],
        "timestamp":      transaction[8]
    }

    # Fetch session
    cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        return {"error": "Session not found"}

    # Map session columns
    sx = {
        "session_id":   session[0],
        "user_id":      session[1],
        "ip_address":   session[2],
        "device_type":  session[3],
        "location":     session[4],
        "vpn_detected": session[5],
        "login_time":   session[6]
    }

    # Fetch behavior profile
    cursor.execute("SELECT * FROM behavior_profiles WHERE user_id = ?", (sx["user_id"],))
    profile = cursor.fetchone()
    if not profile:
        conn.close()
        return {"error": "Behavior profile not found"}

    # Map profile columns
    px = {
        "profile_id":              profile[0],
        "user_id":                 profile[1],
        "avg_transaction_amount":  profile[2],
        "usual_location":          profile[3],
        "typical_device":          profile[4],
        "typical_login_hour":      profile[5],
        "updated_at":              profile[6]
    }

    # --- RISK RULES ---
    risk_score = 0
    reason_codes = []

    # Rule 1 — VPN detected
    if sx["vpn_detected"] == 1:
        risk_score += 20
        reason_codes.append("VPN_DETECTED")

    # Rule 2 — Transaction amount 3x above user average
    if px["avg_transaction_amount"] and tx["amount"] > px["avg_transaction_amount"] * 3:
        risk_score += 25
        reason_codes.append("HIGH_AMOUNT")

    # Rule 3 — Transaction location differs from usual location
    if tx["location"] != px["usual_location"]:
        risk_score += 15
        reason_codes.append("UNUSUAL_LOCATION")

    # Rule 4 — Device differs from typical device
    if sx["device_type"] != px["typical_device"]:
        risk_score += 15
        reason_codes.append("NEW_DEVICE")

    # Rule 5 — Login at unusual hour (outside typical hour +/- 3 hours)
    login_hour = int(sx["login_time"].split(" ")[1].split(":")[0])
    hour_diff = abs(login_hour - px["typical_login_hour"])
    if hour_diff > 3:
        risk_score += 10
        reason_codes.append("UNUSUAL_LOGIN_HOUR")

    # Rule 6 — High velocity (more than 3 transactions in last 10 minutes)
    ten_mins_ago = (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE account_id = ? AND timestamp >= ?
    """, (tx["account_id"], ten_mins_ago))
    recent_count = cursor.fetchone()[0]
    if recent_count > 3:
        risk_score += 15
        reason_codes.append("HIGH_VELOCITY")

    # Cap score at 100
    risk_score = min(risk_score, 100)

    # Get decision
    decision = get_decision(risk_score)
    reason_string = ", ".join(reason_codes) if reason_codes else "NONE"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Write to alerts table
    alert_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO alerts (alert_id, transaction_id, risk_score, decision, reason_codes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (alert_id, transaction_id, risk_score, decision, reason_string, created_at))

    conn.commit()
    conn.close()

    result = {
        "alert_id":     alert_id,
        "transaction_id": transaction_id,
        "user_id":      sx["user_id"],
        "amount":       tx["amount"],
        "merchant":     tx["merchant"],
        "location":     tx["location"],
        "device":       sx["device_type"],
        "vpn":          bool(sx["vpn_detected"]),
        "risk_score":   risk_score,
        "decision":     decision,
        "reason_codes": reason_codes,
        "timestamp":    created_at
    }

    return result

def print_result(result):
    """Pretty print the scoring result."""
    print("\n" + "="*50)
    print(f"  FRAUD DETECTION RESULT")
    print("="*50)
    print(f"  User ID      : {result['user_id']}")
    print(f"  Amount       : {result['amount']} AED")
    print(f"  Merchant     : {result['merchant']}")
    print(f"  Location     : {result['location']}")
    print(f"  Device       : {result['device']}")
    print(f"  VPN          : {result['vpn']}")
    print(f"  Risk Score   : {result['risk_score']} / 100")
    print(f"  Decision     : {result['decision']}")
    print(f"  Reason Codes : {', '.join(result['reason_codes']) if result['reason_codes'] else 'NONE'}")
    print("="*50 + "\n")

if __name__ == "__main__":
    # Fetch a real transaction and session from the database to test
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT transaction_id, session_id FROM transactions LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    transaction_id = row[0]
    session_id = row[1]

    print(f"Testing risk engine on transaction: {transaction_id}")
    result = score_transaction(transaction_id, session_id)
    print_result(result)