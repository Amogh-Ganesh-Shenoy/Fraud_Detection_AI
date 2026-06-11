# Phase 1 — Database Schema & Synthetic Data Generation

## Overview

Phase 1 establishes the foundation of the UAE Fraud Detection AI. It defines
the relational schema across 7 tables and generates a complete synthetic dataset
of UAE users, accounts, sessions, transactions, behavioral profiles, and fraud
labels targeting realistic UAE banking patterns.

The original schema was written for SQLite. By Phase 7, the database was migrated
to Render's managed PostgreSQL. The schema structure is identical — only the
connection layer and syntax changed.

---

## Files

| File | Purpose |
|------|---------|
| `phase1/schema.py` | Original SQLite schema — defines all 7 tables |
| `phase1/generate_data.py` | Generates all synthetic data — targets PostgreSQL in production |

---

## How to Run

```bash
# Wipes all existing data and regenerates everything fresh
python -m phase1.generate_data
```

> **Prerequisites:** `DATABASE_URL` must be set in `.env` pointing to your PostgreSQL instance.

This will:
1. Clear all 7 tables in reverse dependency order
2. Regenerate users, accounts, sessions, transactions, behavior profiles
3. Inject all 4 fraud scenarios
4. Write fraud and legitimate labels into `fraud_labels`

**Warning:** Running this script wipes and rebuilds the entire database. Do not run against production unless intentional.

---

## Database Schema — 7 Tables

### `users`
Stores 100 synthetic UAE residents.

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | TEXT (PK) | UUID |
| `full_name` | TEXT | Faker-generated |
| `emirates_id` | TEXT UNIQUE | Format: `784-YYYY-XXXXXXX-X` |
| `phone` | TEXT | UAE mobile format `+9715XXXXXXXX` |
| `email` | TEXT | Faker-generated |
| `city` | TEXT | One of 7 UAE emirates |
| `nationality` | TEXT | One of 7 nationalities |
| `created_at` | TEXT | Timestamp string |

### `accounts`
One bank account per user.

| Column | Type | Notes |
|--------|------|-------|
| `account_id` | TEXT (PK) | UUID |
| `user_id` | TEXT (FK → users) | |
| `account_number` | TEXT UNIQUE | Format: `AEXX-XXXX-XXXXXXXX` |
| `account_type` | TEXT | savings / current / business |
| `balance` | REAL | AED 500 – 150,000 |
| `currency` | TEXT | Default: AED |
| `created_at` | TEXT | Matches user creation time |

### `sessions`
Login events — 5 per user for legitimate sessions, plus additional fraud-specific
sessions created for Scenarios C and D.

| Column | Type | Notes |
|--------|------|-------|
| `session_id` | TEXT (PK) | UUID |
| `user_id` | TEXT (FK → users) | |
| `ip_address` | TEXT | Faker IPv4 |
| `device_type` | TEXT | iPhone / Android / Windows PC / MacBook / iPad |
| `location` | TEXT | UAE city |
| `vpn_detected` | INTEGER | 0 or 1 — 10% base rate for legitimate sessions |
| `login_time` | TEXT | Timestamp string |

### `transactions`
10 legitimate transactions per account, plus fraud scenario transactions.

| Column | Type | Notes |
|--------|------|-------|
| `transaction_id` | TEXT (PK) | UUID |
| `account_id` | TEXT (FK → accounts) | |
| `session_id` | TEXT (FK → sessions) | |
| `amount` | REAL | AED 10 – 15,000 (legitimate) |
| `currency` | TEXT | Default: AED |
| `merchant` | TEXT | UAE merchants (Carrefour, Noon, Talabat, etc.) |
| `transaction_type` | TEXT | purchase / transfer / withdrawal / bill_payment / online_payment |
| `location` | TEXT | UAE city |
| `timestamp` | TEXT | **Column is `timestamp` — not `created_at`** |

### `behavior_profiles`
One profile per user, calculated from actual transaction history.
Used by the Phase 3 risk engine and Phase 6 ML models for anomaly detection.

| Column | Type | Notes |
|--------|------|-------|
| `profile_id` | TEXT (PK) | UUID |
| `user_id` | TEXT UNIQUE (FK → users) | |
| `avg_transaction_amount` | REAL | Mean of user's transaction amounts |
| `usual_location` | TEXT | User's home city |
| `typical_device` | TEXT | Randomly assigned at generation |
| `typical_login_hour` | INTEGER | Hour 8–22 |
| `historical_baseline_amount` | REAL | Set on first write, never changed — used for drift detection in Phase 2 |
| `updated_at` | TEXT | Last update timestamp |

### `alerts`
Written at runtime by the Phase 3 risk engine on every scored transaction.
Not populated during data generation.

| Column | Type | Notes |
|--------|------|-------|
| `alert_id` | TEXT (PK) | UUID |
| `transaction_id` | TEXT (FK → transactions) | |
| `risk_score` | INTEGER | 0–100+ (uncapped from Phase 5 onwards) |
| `decision` | TEXT | APPROVE / CHALLENGE / BLOCK |
| `reason_codes` | TEXT | Comma-separated triggered rule names |
| `timestamp` | TEXT | **Named `timestamp` — was `created_at` before Phase 4 rename** |

### `fraud_labels`
Ground truth labels for all 1,100 transactions.
Used by Phase 5 batch evaluation and Phase 6 Random Forest training.

| Column | Type | Notes |
|--------|------|-------|
| `label_id` | TEXT (PK) | UUID |
| `transaction_id` | TEXT UNIQUE (FK → transactions) | |
| `is_fraud` | INTEGER | 0 = legitimate, 1 = fraud |
| `fraud_type` | TEXT | `rule_based` (fraud) or `none` (legitimate) |
| `labeled_at` | TEXT | Timestamp string |

---

## Synthetic Dataset — Row Counts

| Table | Rows | Notes |
|-------|------|-------|
| users | 100 | |
| accounts | 100 | 1 per user |
| sessions | 525+ | 500 legitimate + fraud-specific sessions for Scenarios C and D |
| transactions | 1,100 | 1,000 legitimate + 100 fraud |
| behavior_profiles | 100 | 1 per user |
| alerts | 0 at generation | Populated at runtime by `POST /score` |
| fraud_labels | 1,100 | 100 fraud + 1,000 legitimate |

---

## Fraud Scenarios — 100 Fraud Transactions

Four fraud scenarios are injected with patterns designed to trigger specific
risk engine rules. Each scenario maps directly to rules in Phase 3.

| Scenario | Rule Targeted | Transactions | Design |
|----------|--------------|--------------|--------|
| A — Burst Spending | HIGH_VELOCITY | 35 (7 accounts × 5) | Transactions 1.5 min apart within same account |
| B — Structuring | STRUCTURING_DETECTED | 25 (5 accounts × 5) | Near-identical amounts at 4 min intervals |
| C — Account Takeover | VPN + NEW_DEVICE + UNUSUAL_LOGIN + HIGH_AMOUNT | 30 (15 accounts × 2) | Fraud-specific sessions: wrong city, wrong device, VPN on, amount 3–15× user average |
| D — Location Mismatch | Location rules + UNUSUAL_LOGIN_HOUR | 10 (1 per account) | 6 detectable + 4 intentional slip-throughs |

Scenario D intentionally includes 4 undetectable transactions (normal city, normal
hour, low amount) to produce a realistic Recall below 1.0 and avoid overfitting
the rule engine to the synthetic data.

---

## Dependencies

```
psycopg>=3.0
faker
python-dotenv
```

---

## Notes

- `schema.py` targets SQLite and contains a syntax error in `behavior_profiles` —
  missing comma after `historical_baseline_amount REAL DEFAULT NULL`. This file is
  preserved for reference only and is not used at runtime in production.
- The production schema is defined implicitly by the INSERT statements in
  `generate_data.py` targeting PostgreSQL on Render.
- `typical_device` values in `behavior_profiles` must match the dropdown options
  in `frontend/components/ScoreForm.tsx` exactly — any divergence causes
  `NEW_DEVICE` to fire on every transaction regardless of user selection.