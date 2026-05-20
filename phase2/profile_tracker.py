import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/fraud.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def recalculate_profile(user_id):
    """Recalculate and update behavior profile for a given user."""
    conn = get_connection()
    cursor = conn.cursor()

    # Get all transactions for this user via their account
    cursor.execute("""
        SELECT t.amount, t.location, t.timestamp
        FROM transactions t
        JOIN accounts a ON t.account_id = a.account_id
        WHERE a.user_id = ?
    """, (user_id,))
    transactions = cursor.fetchall()

    if not transactions:
        print(f"⚠️ No transactions found for user {user_id}")
        conn.close()
        return

    # Calculate average transaction amount
    amounts = [t[0] for t in transactions]
    avg_amount = round(sum(amounts) / len(amounts), 2)

    # Find most common location
    locations = [t[1] for t in transactions]
    usual_location = max(set(locations), key=locations.count)

    # Find most common login hour from sessions
    cursor.execute("""
        SELECT login_time FROM sessions WHERE user_id = ?
    """, (user_id,))
    session_rows = cursor.fetchall()
    if session_rows:
        hours = [int(row[0].split(" ")[1].split(":")[0]) for row in session_rows]
        typical_login_hour = max(set(hours), key=hours.count)
    else:
        typical_login_hour = 12

    # Find most common device
    cursor.execute("""
        SELECT device_type FROM sessions WHERE user_id = ?
    """, (user_id,))
    device_rows = cursor.fetchall()
    devices = [row[0] for row in device_rows]
    typical_device = max(set(devices), key=devices.count) if devices else "Unknown"

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update the behavior profile
    cursor.execute("""
        UPDATE behavior_profiles
        SET avg_transaction_amount = ?,
            usual_location = ?,
            typical_device = ?,
            typical_login_hour = ?,
            updated_at = ?
        WHERE user_id = ?
    """, (avg_amount, usual_location, typical_device, typical_login_hour, updated_at, user_id))

    conn.commit()
    conn.close()

    print(f"✅ Profile updated for user {user_id}")
    print(f"   Avg amount   : {avg_amount} AED")
    print(f"   Usual location: {usual_location}")
    print(f"   Typical device: {typical_device}")
    print(f"   Typical login hour: {typical_login_hour}:00")

def recalculate_all_profiles():
    """Recalculate behavior profiles for all users."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    user_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    print(f"🔄 Recalculating profiles for {len(user_ids)} users...\n")
    for user_id in user_ids:
        recalculate_profile(user_id)

    print(f"\n✅ All profiles recalculated.")

def get_profile(user_id):
    """Fetch the current behavior profile for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM behavior_profiles WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

if __name__ == "__main__":
    # Test — recalculate profile for first user
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users LIMIT 1")
    user_id = cursor.fetchone()[0]
    conn.close()

    print(f"Testing profile recalculation for user: {user_id}\n")
    recalculate_profile(user_id)