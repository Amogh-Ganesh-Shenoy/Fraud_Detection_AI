import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/fraud.db")

def create_database():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            full_name TEXT,
            emirates_id TEXT UNIQUE,
            phone TEXT,
            email TEXT,
            city TEXT,
            nationality TEXT,
            created_at TEXT
        )
    """)

    # Accounts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id TEXT PRIMARY KEY,
            user_id TEXT,
            account_number TEXT UNIQUE,
            account_type TEXT,
            balance REAL,
            currency TEXT DEFAULT 'AED',
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT,
            ip_address TEXT,
            device_type TEXT,
            location TEXT,
            vpn_detected INTEGER DEFAULT 0,
            login_time TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            account_id TEXT,
            session_id TEXT,
            amount REAL,
            currency TEXT DEFAULT 'AED',
            merchant TEXT,
            transaction_type TEXT,
            location TEXT,
            timestamp TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    # Behavior profiles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS behavior_profiles (
            profile_id TEXT PRIMARY KEY,
            user_id TEXT UNIQUE,
            avg_transaction_amount REAL,
            usual_location TEXT,
            typical_device TEXT,
            typical_login_hour INTEGER,
            historical_baseline_amount REAL DEFAULT NULL
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Alerts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id TEXT PRIMARY KEY,
            transaction_id TEXT,
            risk_score INTEGER,
            decision TEXT,
            reason_codes TEXT,
            created_at TEXT,
            FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
        )
    """)

    # Fraud labels table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fraud_labels (
            label_id TEXT PRIMARY KEY,
            transaction_id TEXT UNIQUE,
            is_fraud INTEGER DEFAULT 0,
            fraud_type TEXT,
            labeled_at TEXT,
            FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database and all tables created successfully.")

if __name__ == "__main__":
    create_database()
    