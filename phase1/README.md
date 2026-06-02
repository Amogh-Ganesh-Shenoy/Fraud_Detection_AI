# Phase 1 — Database Schema & Synthetic UAE Data Generation

## Overview
Phase 1 establishes the SQLite database schema and generates a realistic
synthetic UAE financial dataset used as the foundation for all subsequent
fraud detection phases.

---

## Files
| File | Purpose |
|------|---------|
| `phase1/schema.py` | Creates all 7 database tables |
| `phase1/generate_data.py` | Generates all synthetic data and fraud labels |

---

## How to Run

```bash
# Step 1 — Create the database and tables
python phase1/schema.py

# Step 2 — Generate all data
python phase1/generate_data.py
```

---

## Database Schema — 7 Tables

| Table | Key Columns |
|-------|-------------|
| `users` | user_id (PK), emirates_id (UNIQUE), full_name, city, phone, nationality |
| `accounts` | account_id (PK), user_id (FK), balance (AED), account_type |
| `sessions` | session_id (PK), user_id (FK), device_type, location, vpn_detected, login_time |
| `transactions` | transaction_id (PK), account_id (FK), session_id (FK), amount, merchant, location, timestamp |
| `behavior_profiles` | user_id (UNIQUE FK), avg_transaction_amount, usual_location, typical_device, typical_login_hour |
| `alerts` | alert_id (PK), transaction_id (FK), risk_score, decision, reason_codes, timestamp |
| `fraud_labels` | transaction_id (UNIQUE FK), is_fraud, fraud_type |

> **Critical:** The `alerts` table column is named `timestamp` — renamed from
> `created_at` via ALTER TABLE. All code must use `timestamp`.

---

## UAE-Specific Configuration

| Setting | Value |
|---------|-------|
| Cities | All 7 emirates |
| Nationalities | Emirati, Indian, Pakistani, British, Filipino, Egyptian, American |
| Device Types | iPhone, Android, Windows PC, MacBook, iPad |
| Transaction Range | AED 10 – AED 15,000 |
| Merchants | 14 UAE merchants including Carrefour, Noon.com, Talabat, DEWA |

---

## Generated Dataset

### Legitimate Data
| Entity | Count |
|--------|-------|
| Users | 100 |
| Accounts | 100 (1 per user) |
| Sessions | 500 (5 per user) |
| Transactions | 1,000 (10 per account) |
| Behavior Profiles | 100 (1 per user) |

### Fraud Data — 100 Transactions across 4 Scenarios

| Scenario | Rules Triggered | Transactions | Design |
|----------|----------------|--------------|--------|
| A — Burst Spending | HIGH_VELOCITY | 35 | 7 accounts × 5 transactions at 1.5 min intervals |
| B — Split Payments | STRUCTURING_DETECTED | 25 | 5 accounts × 5 transactions, near-identical amounts at 4 min intervals |
| C — Account Takeover | VPN + NEW_DEVICE + UNUSUAL_LOGIN + HIGH_AMOUNT | 30 | 15 accounts × 2 transactions, fraud-specific sessions created |
| D — Travel Mismatch | LOCATION_RULES + UNUSUAL_LOGIN_HOUR | 10 | 6 detectable mismatches + 4 undetected slip-throughs |

---

## Fraud Label Design

All transactions are labelled in the `fraud_labels` table:
- Fraud transactions → `is_fraud = 1`, `fraud_type = "rule_based"`
- Legitimate transactions → `is_fraud = 0`, `fraud_type = "none"`

This gives the Phase 5 evaluation engine and Phase 6 Random Forest
classifier complete ground truth coverage across all 1,100 transactions.

---

## Expected Output

🗑️ Clearing existing data...
✅ Tables cleared.
🚀 Starting data generation...
✅ 100 users created.
✅ 100 accounts created.
✅ 500 sessions created.
✅ 1000 transactions created.
✅ 100 behavior profiles created.
✅ 100 fraud labels created.
✅ 1000 legitimate labels created.
✅ All data generated and saved to data/fraud.db


## Dependencies 

faker
python-dotenv

## Notes

- Run `generate_data.py` performs a full database wipe before regenerating —
  safe to run multiple times without accumulating duplicate data.
- Behavior profiles are built from legitimate transaction averages —
  average transaction amount is approximately AED 7,600.
- Scenario C creates new fraud-specific sessions directly in the `sessions`
  table to guarantee VPN and device flags fire correctly in the risk engine.
