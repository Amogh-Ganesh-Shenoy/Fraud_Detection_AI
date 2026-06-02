import sqlite3
import os
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker
from dotenv import load_dotenv

load_dotenv()

fake = Faker()
DB_PATH = os.getenv("DB_PATH", "data/fraud.db")

# UAE specific data
UAE_CITIES = ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Umm Al Quwain", "Fujairah"]
UAE_NATIONALITIES = ["Emirati", "Indian", "Pakistani", "British", "Filipino", "Egyptian", "American"]
DEVICE_TYPES = ["iPhone", "Android", "Windows PC", "MacBook", "iPad"]
MERCHANTS = [
    "Carrefour Dubai", "Noon.com", "Emirates NBD ATM", "ADCB ATM",
    "Spinneys", "LuLu Hypermarket", "Amazon.ae", "Talabat",
    "DEWA Bill Payment", "Etisalat Bill", "Dubai Mall Shop",
    "Emaar Properties", "Uber UAE", "Careem"
]
TRANSACTION_TYPES = ["purchase", "transfer", "withdrawal", "bill_payment", "online_payment"]

def random_emirates_id():
    return f"784-{random.randint(1960,2000)}-{random.randint(1000000,9999999)}-{random.randint(1,9)}"

def random_uae_phone():
    return f"+9715{random.randint(10000000,99999999)}"

def random_timestamp(days_back=90):
    start = datetime.now() - timedelta(days=days_back)
    random_seconds = random.randint(0, days_back * 86400)
    return (start + timedelta(seconds=random_seconds)).strftime("%Y-%m-%d %H:%M:%S")

def generate_users(cursor, n=100):
    users = []
    for _ in range(n):
        user_id = str(uuid.uuid4())
        users.append({
            "user_id": user_id,
            "full_name": fake.name(),
            "emirates_id": random_emirates_id(),
            "phone": random_uae_phone(),
            "email": fake.email(),
            "city": random.choice(UAE_CITIES),
            "nationality": random.choice(UAE_NATIONALITIES),
            "created_at": random_timestamp(days_back=365)
        })
        cursor.execute("""
            INSERT INTO users VALUES (
                :user_id, :full_name, :emirates_id, :phone,
                :email, :city, :nationality, :created_at
            )
        """, users[-1])
    print(f"✅ {n} users created.")
    return users

def generate_accounts(cursor, users):
    accounts = []
    for user in users:
        account_id = str(uuid.uuid4())
        account = {
            "account_id": account_id,
            "user_id": user["user_id"],
            "account_number": f"AE{random.randint(10,99)}-{random.randint(1000,9999)}-{random.randint(10000000,99999999)}",
            "account_type": random.choice(["savings", "current", "business"]),
            "balance": round(random.uniform(500, 150000), 2),
            "currency": "AED",
            "created_at": user["created_at"]
        }
        accounts.append(account)
        cursor.execute("""
            INSERT INTO accounts VALUES (
                :account_id, :user_id, :account_number, :account_type,
                :balance, :currency, :created_at
            )
        """, account)
    print(f"✅ {len(accounts)} accounts created.")
    return accounts

def generate_sessions(cursor, users, sessions_per_user=5):
    sessions = []
    for user in users:
        for _ in range(sessions_per_user):
            session_id = str(uuid.uuid4())
            session = {
                "session_id": session_id,
                "user_id": user["user_id"],
                "ip_address": fake.ipv4(),
                "device_type": random.choice(DEVICE_TYPES),
                "location": user["city"],
                "vpn_detected": random.choices([0, 1], weights=[90, 10])[0],
                "login_time": random_timestamp()
            }
            sessions.append(session)
            cursor.execute("""
                INSERT INTO sessions VALUES (
                    :session_id, :user_id, :ip_address, :device_type,
                    :location, :vpn_detected, :login_time
                )
            """, session)
    print(f"✅ {len(sessions)} sessions created.")
    return sessions

def generate_transactions(cursor, accounts, sessions, transactions_per_account=10):
    transactions = []
    session_map = {s["user_id"]: [] for s in sessions}
    for s in sessions:
        session_map[s["user_id"]].append(s["session_id"])

    for account in accounts:
        user_sessions = session_map.get(account["user_id"], [])
        if not user_sessions:
            continue
        for _ in range(transactions_per_account):
            transaction_id = str(uuid.uuid4())
            transaction = {
                "transaction_id": transaction_id,
                "account_id": account["account_id"],
                "session_id": random.choice(user_sessions),
                "amount": round(random.uniform(10, 15000), 2),
                "currency": "AED",
                "merchant": random.choice(MERCHANTS),
                "transaction_type": random.choice(TRANSACTION_TYPES),
                "location": random.choice(UAE_CITIES),
                "timestamp": random_timestamp()
            }
            transactions.append(transaction)
            cursor.execute("""
                INSERT INTO transactions VALUES (
                    :transaction_id, :account_id, :session_id, :amount,
                    :currency, :merchant, :transaction_type, :location, :timestamp
                )
            """, transaction)
    print(f"✅ {len(transactions)} transactions created.")
    return transactions

def generate_behavior_profiles(cursor, users, transactions, accounts):
    account_map = {a["user_id"]: a["account_id"] for a in accounts}
    tx_map = {a["account_id"]: [] for a in accounts}
    for t in transactions:
        tx_map[t["account_id"]].append(t["amount"])

    profiles = []
    for user in users:
        account_id = account_map.get(user["user_id"])
        amounts = tx_map.get(account_id, [random.uniform(100, 5000)])
        # Build profile dict so it can be returned and used by generate_fraud_transactions
        profile = {
            "user_id":            user["user_id"],
            "avg_amount":         round(sum(amounts) / len(amounts), 2),
            "usual_location":     user["city"],
            "typical_device":     random.choice(DEVICE_TYPES),
            "typical_login_hour": random.randint(8, 22),
        }
        profiles.append(profile)
        cursor.execute("""
            INSERT INTO behavior_profiles VALUES (
                ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            str(uuid.uuid4()),
            user["user_id"],
            round(sum(amounts) / len(amounts), 2),
            user["city"],
            random.choice(DEVICE_TYPES),
            random.randint(8, 22),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
    print(f"✅ {len(users)} behavior profiles created.")
    return profiles

def generate_fraud_transactions(cursor, accounts, sessions, profiles):
    fraud_transactions = []
    profile_map = {p["user_id"]: p for p in profiles}

    # ── SCENARIO A: 7 accounts × 5 transactions at 1.5 min intervals → HIGH_VELOCITY ──
    velocity_accounts = random.sample(accounts, 7)
    for account in velocity_accounts:
        base_time = datetime.strptime(random_timestamp(days_back=90), "%Y-%m-%d %H:%M:%S")
        user_sessions = [s for s in sessions if s["user_id"] == account["user_id"]]
        for i in range(5):
            timestamp = base_time + timedelta(minutes=1.5 * i)
            transaction_id = str(uuid.uuid4())
            transaction = {
                "transaction_id":   transaction_id,
                "account_id":       account["account_id"],
                "session_id":       random.choice(user_sessions)["session_id"],
                "amount":           round(random.uniform(500, 3000), 2),
                "currency":         "AED",
                "merchant":         random.choice(MERCHANTS),
                "transaction_type": "purchase",
                "location":         random.choice(UAE_CITIES),
                "timestamp":        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            }
            fraud_transactions.append(transaction)
            cursor.execute("""
                INSERT INTO transactions VALUES (
                    :transaction_id, :account_id, :session_id, :amount,
                    :currency, :merchant, :transaction_type, :location, :timestamp
                )
            """, transaction)

    # ── SCENARIO B: 5 accounts × 5 transactions at 4 min intervals with near-identical amounts → STRUCTURING_DETECTED ──
    structuring_accounts = random.sample(
        [a for a in accounts if a not in velocity_accounts], 5
    )
    for account in structuring_accounts:
        base_time = datetime.strptime(random_timestamp(days_back=90), "%Y-%m-%d %H:%M:%S")
        user_sessions = [s for s in sessions if s["user_id"] == account["user_id"]]
        base_amount = round(random.uniform(500, 2000), 2)
        for i in range(5):
            # Keep amount within ±3% to stay inside structuring detection window
            timestamp = base_time + timedelta(minutes=4 * i)
            transaction_id = str(uuid.uuid4())
            amount = round(base_amount * random.uniform(0.97, 1.03), 2)
            transaction = {
                "transaction_id":   transaction_id,
                "account_id":       account["account_id"],
                "session_id":       random.choice(user_sessions)["session_id"],
                "amount":           amount,
                "currency":         "AED",
                "merchant":         random.choice(MERCHANTS),
                "transaction_type": "transfer",
                "location":         random.choice(UAE_CITIES),
                "timestamp":        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            }
            fraud_transactions.append(transaction)
            cursor.execute("""
                INSERT INTO transactions VALUES (
                    :transaction_id, :account_id, :session_id, :amount,
                    :currency, :merchant, :transaction_type, :location, :timestamp
                )
            """, transaction)

    # ── SCENARIO C: 15 accounts × 2 transactions with fraud sessions → VPN + NEW_DEVICE + UNUSUAL_LOGIN + HIGH_AMOUNT ──
    takeover_accounts = random.sample(
        [a for a in accounts if a not in velocity_accounts and a not in structuring_accounts], 15
    )
    for account in takeover_accounts:
        profile = profile_map.get(account["user_id"])
        if not profile:
            continue

        # Build a fraud session with VPN, foreign device, different city, odd login hour
        fraud_city = random.choice([c for c in UAE_CITIES if c != profile["usual_location"]])
        fraud_device = random.choice([d for d in DEVICE_TYPES if d != profile["typical_device"]])
        fraud_hour = (profile["typical_login_hour"] + 6) % 24
        fraud_login_time = datetime.strptime(
            random_timestamp(days_back=90), "%Y-%m-%d %H:%M:%S"
        ).replace(hour=fraud_hour)

        fraud_session_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            fraud_session_id,
            account["user_id"],
            fake.ipv4(),
            fraud_device,
            fraud_city,
            1,
            fraud_login_time.strftime("%Y-%m-%d %H:%M:%S")
        ))

        for i in range(2):
            # Amount set to 1.6x–2.5x user average to guarantee HIGH_AMOUNT fires
            timestamp = fraud_login_time + timedelta(minutes=5 * i)
            transaction_id = str(uuid.uuid4())
            amount = round(profile["avg_amount"] * random.uniform(1.6, 2.5), 2)
            transaction = {
                "transaction_id":   transaction_id,
                "account_id":       account["account_id"],
                "session_id":       fraud_session_id,
                "amount":           amount,
                "currency":         "AED",
                "merchant":         random.choice(MERCHANTS),
                "transaction_type": "purchase",
                "location":         random.choice([c for c in UAE_CITIES if c != profile["usual_location"]]),
                "timestamp":        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            }
            fraud_transactions.append(transaction)
            cursor.execute("""
                INSERT INTO transactions VALUES (
                    :transaction_id, :account_id, :session_id, :amount,
                    :currency, :merchant, :transaction_type, :location, :timestamp
                )
            """, transaction)

    # ── SCENARIO D: 10 accounts × 1 transaction — 6 detectable mismatches, 4 undetected slip-throughs ──
    mismatch_accounts = random.sample(
        [a for a in accounts if a not in velocity_accounts
         and a not in structuring_accounts
         and a not in takeover_accounts], 10
    )
    for i, account in enumerate(mismatch_accounts):
        profile = profile_map.get(account["user_id"])
        if not profile:
            continue

        # First 6 trigger location + hour rules, last 4 look completely normal
        if i < 6:
            login_city = random.choice([c for c in UAE_CITIES if c != profile["usual_location"]])
            txn_city = random.choice([c for c in UAE_CITIES if c != login_city])
            login_hour = (profile["typical_login_hour"] + 5) % 24
        else:
            login_city = profile["usual_location"]
            txn_city = profile["usual_location"]
            login_hour = profile["typical_login_hour"]

        fraud_login_time = datetime.strptime(
            random_timestamp(days_back=90), "%Y-%m-%d %H:%M:%S"
        ).replace(hour=login_hour)

        fraud_session_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            fraud_session_id,
            account["user_id"],
            fake.ipv4(),
            random.choice(DEVICE_TYPES),
            login_city,
            0,
            fraud_login_time.strftime("%Y-%m-%d %H:%M:%S")
        ))

        # Low amount to avoid HIGH_AMOUNT — these should slip through or only CHALLENGE
        transaction_id = str(uuid.uuid4())
        transaction = {
            "transaction_id":   transaction_id,
            "account_id":       account["account_id"],
            "session_id":       fraud_session_id,
            "amount":           round(random.uniform(200, 800), 2),
            "currency":         "AED",
            "merchant":         random.choice(MERCHANTS),
            "transaction_type": "purchase",
            "location":         txn_city,
            "timestamp":        fraud_login_time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        fraud_transactions.append(transaction)
        cursor.execute("""
            INSERT INTO transactions VALUES (
                :transaction_id, :account_id, :session_id, :amount,
                :currency, :merchant, :transaction_type, :location, :timestamp
            )
        """, transaction)

    return fraud_transactions

def generate_fraud_labels(cursor, fraud_transactions):
    for transaction in fraud_transactions:
        cursor.execute("""
            INSERT INTO fraud_labels (transaction_id, is_fraud, fraud_type)
            VALUES (?, ?, ?)
        """, (transaction["transaction_id"], 1, "rule_based"))
    print(f"✅ {len(fraud_transactions)} fraud labels created.")
    
def generate_legitimate_labels(cursor, transactions, fraud_transactions):
    fraud_ids = {t["transaction_id"] for t in fraud_transactions}
    legitimate = [t for t in transactions if t["transaction_id"] not in fraud_ids]
    
    for transaction in legitimate:
        cursor.execute("""
            INSERT INTO fraud_labels (transaction_id, is_fraud, fraud_type)
            VALUES (?, ?, ?)
        """, (transaction["transaction_id"], 0, "none"))
    print(f"✅ {len(legitimate)} legitimate labels created.")

# ── Clear existing data before regenerating ──────────────────
def generate_all():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🗑️ Clearing existing data...")
    cursor.execute("DELETE FROM fraud_labels")
    cursor.execute("DELETE FROM behavior_profiles")
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM sessions")
    cursor.execute("DELETE FROM accounts")
    cursor.execute("DELETE FROM users")
    print("✅ Tables cleared.\n")

    print("🚀 Starting data generation...\n")
    users = generate_users(cursor)
    accounts = generate_accounts(cursor, users)
    sessions = generate_sessions(cursor, users)
    transactions = generate_transactions(cursor, accounts, sessions)
    profiles = generate_behavior_profiles(cursor, users, transactions, accounts)
    fraud_transactions = generate_fraud_transactions(cursor, accounts, sessions, profiles)
    generate_fraud_labels(cursor, fraud_transactions)
    generate_legitimate_labels(cursor, transactions, fraud_transactions)

    conn.commit()
    conn.close()
    print("\n✅ All data generated and saved to", DB_PATH)

if __name__ == "__main__":
    generate_all()