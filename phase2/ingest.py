# phase2/ingest.py
# Ingestion functions for sessions and transactions.
# Called by api/main.py endpoints — never called directly by React.
# Writes to PostgreSQL using DATABASE_URL from environment variables.

import uuid
import os
from datetime import datetime
from dotenv import load_dotenv

import psycopg
from psycopg.rows import dict_row

load_dotenv()

# DATABASE_URL points to Render's managed PostgreSQL in production
# Loaded from .env locally, injected as environment variable on Render
DATABASE_URL = os.getenv("DATABASE_URL")


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_connection():
    # Connects to PostgreSQL using the full connection URL
    # RealDictCursor returns rows as dicts — consistent with api/dependencies.py
    conn=psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# INGEST SESSION
# ══════════════════════════════════════════════════════════════════════════════

def ingest_session(user_id, ip_address, device_type, location, vpn_detected=0):
    """
    Records a new login session to the sessions table.
    Called by POST /session and POST /score in api/main.py.
    Returns the generated session_id for use in ingest_transaction().
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Generate a unique session_id and record the login timestamp
    # %s replaces ? for PostgreSQL parameter binding — functionally identical
    session_id = str(uuid.uuid4())
    login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO sessions (
            session_id, user_id, ip_address, device_type,
            location, vpn_detected, login_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (session_id, user_id, ip_address, device_type, location, vpn_detected, login_time))

    conn.commit()
    conn.close()

    print(f"✅ Session ingested — user: {user_id}, device: {device_type}, VPN: {bool(vpn_detected)}")
    return session_id


# ══════════════════════════════════════════════════════════════════════════════
# INGEST TRANSACTION
# ══════════════════════════════════════════════════════════════════════════════

def ingest_transaction(account_id, session_id, amount, merchant, transaction_type, location):
    """
    Records a new transaction to the transactions table.
    Called by POST /score in api/main.py after ingest_session().
    Returns the generated transaction_id for use in ensemble_score().
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Generate a unique transaction_id and record the timestamp
    # Source: account_id from accounts table, session_id from ingest_session()
    transaction_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO transactions (
            transaction_id, account_id, session_id, amount,
            currency, merchant, transaction_type, location, timestamp
        ) VALUES (%s, %s, %s, %s, 'AED', %s, %s, %s, %s)
    """, (transaction_id, account_id, session_id, amount, merchant, transaction_type, location, timestamp))

    conn.commit()
    conn.close()

    print(f"✅ Transaction ingested — amount: {amount} AED, merchant: {merchant}, type: {transaction_type}")
    return transaction_id


# ══════════════════════════════════════════════════════════════════════════════
# LOOKUP HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_user_by_id(user_id):
    """
    Fetches a user record by user_id from the users table.
    Source: users table, populated by Phase 1 generate_users().
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_account_by_user(user_id):
    """
    Fetches the account linked to a user from the accounts table.
    Source: accounts table, populated by Phase 1 generate_accounts().
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row