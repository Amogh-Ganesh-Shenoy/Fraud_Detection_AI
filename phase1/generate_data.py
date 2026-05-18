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
UAE_CITIES = ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah"]
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
                "amount": round(random.uniform(10, 25000), 2),
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

    for user in users:
        account_id = account_map.get(user["user_id"])
        amounts = tx_map.get(account_id, [random.uniform(100, 5000)])
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

def generate_fraud_labels(cursor, transactions, fraud_rate=0.10):
    fraud_types = ["card_not_present", "account_takeover", "identity_theft", "unusual_location", "high_velocity"]
    count = 0
    for t in transactions:
        is_fraud = random.choices([0, 1], weights=[1 - fraud_rate, fraud_rate])[0]
        cursor.execute("""
            INSERT INTO fraud_labels VALUES (?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            t["transaction_id"],
            is_fraud,
            random.choice(fraud_types) if is_fraud else None,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        if is_fraud:
            count += 1
    print(f"✅ Fraud labels created. {count} fraudulent transactions flagged.")

def generate_all():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🚀 Starting data generation...\n")
    users = generate_users(cursor)
    accounts = generate_accounts(cursor, users)
    sessions = generate_sessions(cursor, users)
    transactions = generate_transactions(cursor, accounts, sessions)
    generate_behavior_profiles(cursor, users, transactions, accounts)
    generate_fraud_labels(cursor, transactions)

    conn.commit()
    conn.close()
    print("\n✅ All data generated and saved to", DB_PATH)

if __name__ == "__main__":
    generate_all()