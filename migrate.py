# migrate.py
# One-time migration script — creates all 7 tables in PostgreSQL
# and imports all data from the local SQLite database.
# Run once locally: python migrate.py
# After running, the PostgreSQL database on Render will have all your data.

import sqlite3
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# Source: local SQLite database built across Phases 1-6
SQLITE_PATH  = os.getenv("DB_PATH", "data/fraud.db")

# Destination: Render's managed PostgreSQL — uses External Database URL
# Must use EXTERNAL URL here since we're running this locally
DATABASE_URL = os.getenv("DATABASE_URL")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — CREATE ALL TABLES IN POSTGRESQL
# ══════════════════════════════════════════════════════════════════════════════

def create_tables(pg_conn):
    """
    Creates all 7 tables in PostgreSQL matching the Phase 1 SQLite schema.
    Uses TEXT instead of SQLite's TEXT, REAL → NUMERIC, INTEGER → INTEGER.
    IF NOT EXISTS means this is safe to re-run without dropping data.
    """
    cur = pg_conn.cursor()

    # users table — core user identity data
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     TEXT PRIMARY KEY,
            full_name   TEXT,
            emirates_id TEXT UNIQUE,
            phone       TEXT,
            email       TEXT,
            city        TEXT,
            nationality TEXT,
            created_at  TEXT
        )
    """)

    # accounts table — bank accounts linked to users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id     TEXT PRIMARY KEY,
            user_id        TEXT,
            account_number TEXT UNIQUE,
            account_type   TEXT,
            balance        NUMERIC,
            currency       TEXT DEFAULT 'AED',
            created_at     TEXT
        )
    """)

    # sessions table — login events
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id   TEXT PRIMARY KEY,
            user_id      TEXT,
            ip_address   TEXT,
            device_type  TEXT,
            location     TEXT,
            vpn_detected INTEGER DEFAULT 0,
            login_time   TEXT
        )
    """)

    # transactions table — financial transactions
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id   TEXT PRIMARY KEY,
            account_id       TEXT,
            session_id       TEXT,
            amount           NUMERIC,
            currency         TEXT DEFAULT 'AED',
            merchant         TEXT,
            transaction_type TEXT,
            location         TEXT,
            timestamp        TEXT
        )
    """)

    # behavior_profiles table — user behavioral baselines
    cur.execute("""
        CREATE TABLE IF NOT EXISTS behavior_profiles (
            profile_id                  TEXT PRIMARY KEY,
            user_id                     TEXT UNIQUE,
            avg_transaction_amount      NUMERIC,
            usual_location              TEXT,
            typical_device              TEXT,
            typical_login_hour          INTEGER,
            historical_baseline_amount  NUMERIC,
            updated_at                  TEXT
        )
    """)

    # alerts table — fraud decisions written by rule engine
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id       TEXT PRIMARY KEY,
            transaction_id TEXT,
            risk_score     INTEGER,
            decision       TEXT,
            reason_codes   TEXT,
            timestamp      TEXT
        )
    """)

    # fraud_labels table — ground truth labels from Phase 1
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fraud_labels (
            label_id       TEXT PRIMARY KEY,
            transaction_id TEXT UNIQUE,
            is_fraud       INTEGER DEFAULT 0,
            fraud_type     TEXT,
            labeled_at     TEXT
        )
    """)

    pg_conn.commit()
    print("✅ All 7 tables created in PostgreSQL.")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — COPY DATA FROM SQLITE TO POSTGRESQL
# ══════════════════════════════════════════════════════════════════════════════

def migrate_table(sqlite_conn, pg_conn, table_name):
    """
    Copies all rows from a SQLite table into the matching PostgreSQL table.
    Uses ON CONFLICT DO NOTHING so re-running is safe — no duplicate errors.
    Source: local SQLite fraud.db
    Destination: Render PostgreSQL
    """
    sqlite_cur = sqlite_conn.cursor()
    pg_cur     = pg_conn.cursor()

    # Fetch all rows from SQLite
    sqlite_cur.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cur.fetchall()

    if not rows:
        print(f"⚠️  {table_name}: no rows found in SQLite — skipping.")
        return

    # Get column names from SQLite cursor description
    columns     = [desc[0] for desc in sqlite_cur.description]
    col_str     = ", ".join(columns)
    placeholder = ", ".join(["%s"] * len(columns))

    # Insert each row into PostgreSQL
    # ON CONFLICT DO NOTHING prevents errors if migration is re-run
    inserted = 0
    for row in rows:
        try:
            pg_cur.execute(f"""
                INSERT INTO {table_name} ({col_str})
                VALUES ({placeholder})
                ON CONFLICT DO NOTHING
            """, list(row))
            inserted += 1
        except Exception as e:
            print(f"  ⚠️  Row skipped in {table_name}: {e}")

    pg_conn.commit()
    print(f"✅ {table_name}: {inserted}/{len(rows)} rows migrated.")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — run migration
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n🚀 Starting SQLite → PostgreSQL migration...\n")

    # Connect to SQLite source
    sqlite_conn = sqlite3.connect(SQLITE_PATH)

    # Connect to PostgreSQL destination
    pg_conn = psycopg2.connect(DATABASE_URL)

    # Step 1 — create tables
    create_tables(pg_conn)

    # Step 2 — migrate all 7 tables in dependency order
    # Users and accounts must come before sessions and transactions
    # due to foreign key relationships
    tables = [
        "users",
        "accounts",
        "sessions",
        "transactions",
        "behavior_profiles",
        "alerts",
        "fraud_labels",
    ]

    for table in tables:
        migrate_table(sqlite_conn, pg_conn, table)

    sqlite_conn.close()
    pg_conn.close()

    print("\n✅ Migration complete. PostgreSQL is ready.\n")