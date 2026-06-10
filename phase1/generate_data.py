# phase1/generate_data.py
# Generates all synthetic UAE fraud detection data directly into PostgreSQL.
# Replaces the SQLite version — same logic, PostgreSQL connection and syntax.
# Run once: python -m phase1.generate_data
# Clears all existing data first, then regenerates everything fresh.

import os
import random
import uuid
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
from faker import Faker
from dotenv import load_dotenv

load_dotenv()

fake = Faker()

# DATABASE_URL points to Render's managed PostgreSQL
# Uses External URL when run locally, Internal URL on Render
DATABASE_URL = os.getenv("DATABASE_URL")

# ── UAE specific data ─────────────────────────────────────────────────────────
UAE_CITIES       = ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Umm Al Quwain", "Fujairah"]
UAE_NATIONALITIES = ["Emirati", "Indian", "Pakistani", "British", "Filipino", "Egyptian", "American"]
DEVICE_TYPES     = ["iPhone", "Android", "Windows PC", "MacBook", "iPad"]
MERCHANTS        = [
    "Carrefour Dubai", "Noon.com", "Emirates NBD ATM", "ADCB ATM",
    "Spinneys", "LuLu Hypermarket", "Amazon.ae", "Talabat",
    "DEWA Bill Payment", "Etisalat Bill", "Dubai Mall Shop",
    "Emaar Properties", "Uber UAE", "Careem"
]
TRANSACTION_TYPES = ["purchase", "transfer", "withdrawal", "bill_payment", "online_payment"]


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_db():
    # Connects to PostgreSQL using DATABASE_URL from .env
    # RealDictCursor returns rows as dicts — consistent with all other phase files
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def random_emirates_id():
    return f"784-{random.randint(1960,2000)}-{random.randint(1000000,9999999)}-{random.randint(1,9)}"

def random_uae_phone():
    return f"+9715{random.randint(10000000,99999999)}"

def random_timestamp(days_back=90):
    start          = datetime.now() - timedelta(days=days_back)
    random_seconds = random.randint(0, days_back * 86400)
    return (start + timedelta(seconds=random_seconds)).strftime("%Y-%m-%d %H:%M:%S")


# ══════════════════════════════════════════════════════════════════════════════
# DATA GENERATORS
# ══════════════════════════════════════════════════════════════════════════════

def generate_users(cur, n=100):
    """
    Generates 100 synthetic UAE users and inserts into users table.
    Returns list of user dicts for use by downstream generators.
    """
    users = []
    for _ in range(n):
        user = {
            "user_id":     str(uuid.uuid4()),
            "full_name":   fake.name(),
            "emirates_id": random_emirates_id(),
            "phone":       random_uae_phone(),
            "email":       fake.email(),
            "city":        random.choice(UAE_CITIES),
            "nationality": random.choice(UAE_NATIONALITIES),
            "created_at":  random_timestamp(days_back=365),
        }
        users.append(user)
        # %s replaces SQLite's :named_param syntax for PostgreSQL
        cur.execute("""
            INSERT INTO users (user_id, full_name, emirates_id, phone,
                               email, city, nationality, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user["user_id"], user["full_name"], user["emirates_id"],
              user["phone"], user["email"], user["city"],
              user["nationality"], user["created_at"]))
    print(f"✅ {n} users created.")
    return users


def generate_accounts(cur, users):
    """
    Generates one bank account per user and inserts into accounts table.
    Returns list of account dicts for use by downstream generators.
    Source: users list from generate_users()
    """
    accounts = []
    for user in users:
        account = {
            "account_id":     str(uuid.uuid4()),
            "user_id":        user["user_id"],
            "account_number": f"AE{random.randint(10,99)}-{random.randint(1000,9999)}-{random.randint(10000000,99999999)}",
            "account_type":   random.choice(["savings", "current", "business"]),
            "balance":        round(random.uniform(500, 150000), 2),
            "currency":       "AED",
            "created_at":     user["created_at"],
        }
        accounts.append(account)
        cur.execute("""
            INSERT INTO accounts (account_id, user_id, account_number, account_type,
                                  balance, currency, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (account["account_id"], account["user_id"], account["account_number"],
              account["account_type"], account["balance"],
              account["currency"], account["created_at"]))
    print(f"✅ {len(accounts)} accounts created.")
    return accounts


def generate_sessions(cur, users, sessions_per_user=5):
    """
    Generates 5 sessions per user and inserts into sessions table.
    Returns list of session dicts for use by downstream generators.
    Source: users list from generate_users()
    """
    sessions = []
    for user in users:
        for _ in range(sessions_per_user):
            session = {
                "session_id":   str(uuid.uuid4()),
                "user_id":      user["user_id"],
                "ip_address":   fake.ipv4(),
                "device_type":  random.choice(DEVICE_TYPES),
                "location":     user["city"],
                "vpn_detected": random.choices([0, 1], weights=[90, 10])[0],
                "login_time":   random_timestamp(),
            }
            sessions.append(session)
            cur.execute("""
                INSERT INTO sessions (session_id, user_id, ip_address, device_type,
                                      location, vpn_detected, login_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (session["session_id"], session["user_id"], session["ip_address"],
                  session["device_type"], session["location"],
                  session["vpn_detected"], session["login_time"]))
    print(f"✅ {len(sessions)} sessions created.")
    return sessions


def generate_transactions(cur, accounts, sessions, transactions_per_account=10):
    """
    Generates 10 transactions per account and inserts into transactions table.
    Returns list of transaction dicts for use by downstream generators.
    Source: accounts from generate_accounts(), sessions from generate_sessions()
    """
    transactions = []
    session_map  = {s["user_id"]: [] for s in sessions}
    for s in sessions:
        session_map[s["user_id"]].append(s["session_id"])

    for account in accounts:
        user_sessions = session_map.get(account["user_id"], [])
        if not user_sessions:
            continue
        for _ in range(transactions_per_account):
            txn = {
                "transaction_id":   str(uuid.uuid4()),
                "account_id":       account["account_id"],
                "session_id":       random.choice(user_sessions),
                "amount":           round(random.uniform(10, 15000), 2),
                "currency":         "AED",
                "merchant":         random.choice(MERCHANTS),
                "transaction_type": random.choice(TRANSACTION_TYPES),
                "location":         random.choice(UAE_CITIES),
                "timestamp":        random_timestamp(),
            }
            transactions.append(txn)
            cur.execute("""
                INSERT INTO transactions (transaction_id, account_id, session_id,
                                          amount, currency, merchant,
                                          transaction_type, location, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (txn["transaction_id"], txn["account_id"], txn["session_id"],
                  txn["amount"], txn["currency"], txn["merchant"],
                  txn["transaction_type"], txn["location"], txn["timestamp"]))
    print(f"✅ {len(transactions)} transactions created.")
    return transactions


def generate_behavior_profiles(cur, users, transactions, accounts):
    """
    Generates one behavior profile per user and inserts into behavior_profiles table.
    Calculates avg_transaction_amount from actual transaction history.
    Source: users, transactions, accounts from previous generators.
    """
    account_map = {a["user_id"]: a["account_id"] for a in accounts}
    tx_map      = {a["account_id"]: [] for a in accounts}
    for t in transactions:
        tx_map[t["account_id"]].append(t["amount"])

    profiles = []
    for user in users:
        account_id = account_map.get(user["user_id"])
        amounts    = tx_map.get(account_id, [random.uniform(100, 5000)])
        profile    = {
            "user_id":            user["user_id"],
            "avg_amount":         round(sum(amounts) / len(amounts), 2),
            "usual_location":     user["city"],
            "typical_device":     random.choice(DEVICE_TYPES),
            "typical_login_hour": random.randint(8, 22),
        }
        profiles.append(profile)
        cur.execute("""
            INSERT INTO behavior_profiles (profile_id, user_id, avg_transaction_amount,
                                           usual_location, typical_device,
                                           typical_login_hour, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (str(uuid.uuid4()), user["user_id"], profile["avg_amount"],
              profile["usual_location"], profile["typical_device"],
              profile["typical_login_hour"],
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print(f"✅ {len(users)} behavior profiles created.")
    return profiles


def generate_fraud_transactions(cur, accounts, sessions, profiles):
    """
    Generates 4 fraud scenarios and inserts into transactions and sessions tables.
    Scenario A: HIGH_VELOCITY — 7 accounts × 5 rapid transactions
    Scenario B: STRUCTURING — 5 accounts × 5 near-identical amounts
    Scenario C: ACCOUNT_TAKEOVER — 15 accounts × 2 high-amount transactions
    Scenario D: LOCATION_MISMATCH — 10 accounts × 1 transaction
    Source: accounts, sessions, profiles from previous generators.
    """
    fraud_transactions = []
    profile_map        = {p["user_id"]: p for p in profiles}

    # ── SCENARIO A: HIGH_VELOCITY ─────────────────────────────────────────────
    velocity_accounts = random.sample(accounts, 7)
    for account in velocity_accounts:
        base_time     = datetime.strptime(random_timestamp(days_back=90), "%Y-%m-%d %H:%M:%S")
        user_sessions = [s for s in sessions if s["user_id"] == account["user_id"]]
        for i in range(5):
            timestamp = base_time + timedelta(minutes=1.5 * i)
            txn = {
                "transaction_id":   str(uuid.uuid4()),
                "account_id":       account["account_id"],
                "session_id":       random.choice(user_sessions)["session_id"],
                "amount":           round(random.uniform(500, 3000), 2),
                "currency":         "AED",
                "merchant":         random.choice(MERCHANTS),
                "transaction_type": "purchase",
                "location":         random.choice(UAE_CITIES),
                "timestamp":        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            }
            fraud_transactions.append(txn)
            cur.execute("""
                INSERT INTO transactions (transaction_id, account_id, session_id,
                                          amount, currency, merchant,
                                          transaction_type, location, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (txn["transaction_id"], txn["account_id"], txn["session_id"],
                  txn["amount"], txn["currency"], txn["merchant"],
                  txn["transaction_type"], txn["location"], txn["timestamp"]))

    # ── SCENARIO B: STRUCTURING ───────────────────────────────────────────────
    structuring_accounts = random.sample(
        [a for a in accounts if a not in velocity_accounts], 5
    )
    for account in structuring_accounts:
        base_time     = datetime.strptime(random_timestamp(days_back=90), "%Y-%m-%d %H:%M:%S")
        user_sessions = [s for s in sessions if s["user_id"] == account["user_id"]]
        base_amount   = round(random.uniform(500, 2000), 2)
        for i in range(5):
            timestamp = base_time + timedelta(minutes=4 * i)
            txn = {
                "transaction_id":   str(uuid.uuid4()),
                "account_id":       account["account_id"],
                "session_id":       random.choice(user_sessions)["session_id"],
                "amount":           round(base_amount * random.uniform(0.97, 1.03), 2),
                "currency":         "AED",
                "merchant":         random.choice(MERCHANTS),
                "transaction_type": "transfer",
                "location":         random.choice(UAE_CITIES),
                "timestamp":        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            }
            fraud_transactions.append(txn)
            cur.execute("""
                INSERT INTO transactions (transaction_id, account_id, session_id,
                                          amount, currency, merchant,
                                          transaction_type, location, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (txn["transaction_id"], txn["account_id"], txn["session_id"],
                  txn["amount"], txn["currency"], txn["merchant"],
                  txn["transaction_type"], txn["location"], txn["timestamp"]))

    # ── SCENARIO C: ACCOUNT TAKEOVER ─────────────────────────────────────────
    takeover_accounts = random.sample(
        [a for a in accounts if a not in velocity_accounts
         and a not in structuring_accounts], 15
    )
    for account in takeover_accounts:
        profile = profile_map.get(account["user_id"])
        if not profile:
            continue

        fraud_city    = random.choice([c for c in UAE_CITIES if c != profile["usual_location"]])
        fraud_device  = random.choice([d for d in DEVICE_TYPES if d != profile["typical_device"]])
        fraud_hour    = (profile["typical_login_hour"] + 6) % 24
        fraud_login_time = datetime.strptime(
            random_timestamp(days_back=90), "%Y-%m-%d %H:%M:%S"
        ).replace(hour=fraud_hour)

        fraud_session_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO sessions (session_id, user_id, ip_address, device_type,
                                  location, vpn_detected, login_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (fraud_session_id, account["user_id"], fake.ipv4(),
              fraud_device, fraud_city, 1,
              fraud_login_time.strftime("%Y-%m-%d %H:%M:%S")))

        for i in range(2):
            timestamp = fraud_login_time + timedelta(minutes=5 * i)
            txn = {
                "transaction_id":   str(uuid.uuid4()),
                "account_id":       account["account_id"],
                "session_id":       fraud_session_id,
                "amount":           round(profile["avg_amount"] * random.uniform(1.6, 2.5), 2),
                "currency":         "AED",
                "merchant":         random.choice(MERCHANTS),
                "transaction_type": "purchase",
                "location":         random.choice([c for c in UAE_CITIES if c != profile["usual_location"]]),
                "timestamp":        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            }
            fraud_transactions.append(txn)
            cur.execute("""
                INSERT INTO transactions (transaction_id, account_id, session_id,
                                          amount, currency, merchant,
                                          transaction_type, location, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (txn["transaction_id"], txn["account_id"], txn["session_id"],
                  txn["amount"], txn["currency"], txn["merchant"],
                  txn["transaction_type"], txn["location"], txn["timestamp"]))

    # ── SCENARIO D: LOCATION MISMATCH ────────────────────────────────────────
    mismatch_accounts = random.sample(
        [a for a in accounts if a not in velocity_accounts
         and a not in structuring_accounts
         and a not in takeover_accounts], 10
    )
    for i, account in enumerate(mismatch_accounts):
        profile = profile_map.get(account["user_id"])
        if not profile:
            continue

        if i < 6:
            login_city = random.choice([c for c in UAE_CITIES if c != profile["usual_location"]])
            txn_city   = random.choice([c for c in UAE_CITIES if c != login_city])
            login_hour = (profile["typical_login_hour"] + 5) % 24
        else:
            login_city = profile["usual_location"]
            txn_city   = profile["usual_location"]
            login_hour = profile["typical_login_hour"]

        fraud_login_time = datetime.strptime(
            random_timestamp(days_back=90), "%Y-%m-%d %H:%M:%S"
        ).replace(hour=login_hour)

        fraud_session_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO sessions (session_id, user_id, ip_address, device_type,
                                  location, vpn_detected, login_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (fraud_session_id, account["user_id"], fake.ipv4(),
              random.choice(DEVICE_TYPES), login_city, 0,
              fraud_login_time.strftime("%Y-%m-%d %H:%M:%S")))

        txn = {
            "transaction_id":   str(uuid.uuid4()),
            "account_id":       account["account_id"],
            "session_id":       fraud_session_id,
            "amount":           round(random.uniform(200, 800), 2),
            "currency":         "AED",
            "merchant":         random.choice(MERCHANTS),
            "transaction_type": "purchase",
            "location":         txn_city,
            "timestamp":        fraud_login_time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        fraud_transactions.append(txn)
        cur.execute("""
            INSERT INTO transactions (transaction_id, account_id, session_id,
                                      amount, currency, merchant,
                                      transaction_type, location, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (txn["transaction_id"], txn["account_id"], txn["session_id"],
              txn["amount"], txn["currency"], txn["merchant"],
              txn["transaction_type"], txn["location"], txn["timestamp"]))

    return fraud_transactions


def generate_fraud_labels(cur, fraud_transactions):
    """
    Inserts is_fraud=1 labels for all fraud transactions into fraud_labels table.
    Source: fraud_transactions list from generate_fraud_transactions()
    """
    for txn in fraud_transactions:
        cur.execute("""
            INSERT INTO fraud_labels (label_id, transaction_id, is_fraud, fraud_type, labeled_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (str(uuid.uuid4()), txn["transaction_id"], 1, "rule_based",
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print(f"✅ {len(fraud_transactions)} fraud labels created.")


def generate_legitimate_labels(cur, transactions, fraud_transactions):
    """
    Inserts is_fraud=0 labels for all legitimate transactions into fraud_labels table.
    Source: transactions from generate_transactions(), fraud_transactions for exclusion
    """
    fraud_ids  = {t["transaction_id"] for t in fraud_transactions}
    legitimate = [t for t in transactions if t["transaction_id"] not in fraud_ids]
    for txn in legitimate:
        cur.execute("""
            INSERT INTO fraud_labels (label_id, transaction_id, is_fraud, fraud_type, labeled_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (str(uuid.uuid4()), txn["transaction_id"], 0, "none",
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print(f"✅ {len(legitimate)} legitimate labels created.")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — clear all tables and regenerate everything fresh
# ══════════════════════════════════════════════════════════════════════════════

def generate_all():
    conn = get_db()
    cur  = conn.cursor()

    # Clear all tables in reverse dependency order to avoid foreign key errors
    # Source: all 7 tables in PostgreSQL on Render
    print("🗑️  Clearing existing data...")
    for table in ["fraud_labels", "alerts", "behavior_profiles",
                  "transactions", "sessions", "accounts", "users"]:
        cur.execute(f"DELETE FROM {table}")
    conn.commit()
    print("✅ Tables cleared.\n")

    print("🚀 Starting data generation...\n")
    users             = generate_users(cur)
    conn.commit()
    accounts          = generate_accounts(cur, users)
    conn.commit()
    sessions          = generate_sessions(cur, users)
    conn.commit()
    transactions      = generate_transactions(cur, accounts, sessions)
    conn.commit()
    profiles          = generate_behavior_profiles(cur, users, transactions, accounts)
    conn.commit()
    fraud_transactions = generate_fraud_transactions(cur, accounts, sessions, profiles)
    conn.commit()
    generate_fraud_labels(cur, fraud_transactions)
    conn.commit()
    generate_legitimate_labels(cur, transactions, fraud_transactions)
    conn.commit()

    conn.close()
    print("\n✅ All data generated and saved to PostgreSQL.")


if __name__ == "__main__":
    generate_all()