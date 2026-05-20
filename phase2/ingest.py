import sqlite3
import uuid
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/fraud.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def ingest_session(user_id, ip_address, device_type, location, vpn_detected=0):
    """Record a new login session event."""
    conn = get_connection()
    cursor = conn.cursor()

    session_id = str(uuid.uuid4())
    login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO sessions (
            session_id, user_id, ip_address, device_type,
            location, vpn_detected, login_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session_id, user_id, ip_address, device_type, location, vpn_detected, login_time))

    conn.commit()
    conn.close()

    print(f"✅ Session ingested — user: {user_id}, device: {device_type}, VPN: {bool(vpn_detected)}")
    return session_id

def ingest_transaction(account_id, session_id, amount, merchant, transaction_type, location):
    """Record a new transaction event."""
    conn = get_connection()
    cursor = conn.cursor()

    transaction_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO transactions (
            transaction_id, account_id, session_id, amount,
            currency, merchant, transaction_type, location, timestamp
        ) VALUES (?, ?, ?, ?, 'AED', ?, ?, ?, ?)
    """, (transaction_id, account_id, session_id, amount, merchant, transaction_type, location, timestamp))

    conn.commit()
    conn.close()

    print(f"✅ Transaction ingested — amount: {amount} AED, merchant: {merchant}, type: {transaction_type}")
    return transaction_id

def get_user_by_id(user_id):
    """Fetch a user record by user_id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_account_by_user(user_id):
    """Fetch account linked to a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

if __name__ == "__main__":
    # Quick test — fetch first user and simulate an event
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users LIMIT 1")
    user_id = cursor.fetchone()[0]
    cursor.execute("SELECT account_id FROM accounts WHERE user_id = ?", (user_id,))
    account_id = cursor.fetchone()[0]
    conn.close()

    # Simulate a login
    session_id = ingest_session(
        user_id=user_id,
        ip_address="185.220.101.45",
        device_type="iPhone",
        location="Dubai",
        vpn_detected=0
    )

    # Simulate a transaction
    ingest_transaction(
        account_id=account_id,
        session_id=session_id,
        amount=4500.00,
        merchant="Noon.com",
        transaction_type="online_payment",
        location="Dubai"
    )