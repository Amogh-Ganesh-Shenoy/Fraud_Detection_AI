# Phase 1 — Database Schema & Synthetic Data Generation

## Overview
Establishes the SQLite database foundation for the UAE Fraud Detection AI.
Defines 7 tables representing a realistic UAE banking data model and populates
them with synthetic data using the Faker library.

## Database
- **Engine:** SQLite
- **Path:** `data/fraud.db` (configured via `.env`)

## Tables

| Table | Description |
|-------|-------------|
| `users` | 100 synthetic UAE residents with Emirates ID, phone, email, city, nationality |
| `accounts` | Bank accounts linked to users — savings, current, or business — with AED balances |
| `sessions` | Login sessions with device type, location, IP address, VPN detection flag |
| `transactions` | 1,000 transactions with merchant, amount, type, location, timestamp |
| `behavior_profiles` | Per-user behavioral baseline — avg amount, usual location, typical device and login hour |
| `alerts` | Risk engine output — score, decision, reason codes, timestamp |
| `fraud_labels` | Ground truth fraud labels — is_fraud flag and fraud type |

## Synthetic Data Breakdown

| Entity | Count | Notes |
|--------|-------|-------|
| Users | 100 | UAE cities, Emirates IDs, 7 nationalities |
| Accounts | 100 | One per user, balance AED 500–150,000 |
| Sessions | 500 | 5 per user, 10% VPN rate |
| Transactions | 1,000 | 10 per account, AED 10–25,000 |
| Fraud labels | ~100 | 10% fraud rate |

## UAE Reference Data
- **Cities:** Dubai, Abu Dhabi, Sharjah, Ajman, Ras Al Khaimah
- **Devices:** iPhone, Android, Windows PC, MacBook, iPad
- **Merchants:** Carrefour, Noon.com, Emirates NBD ATM, Amazon.ae, Talabat and more
- **Fraud types:** card_not_present, account_takeover, identity_theft, unusual_location, high_velocity

## Key Notes
- `alerts.timestamp` — renamed from `created_at` via `ALTER TABLE`
- `behavior_profiles.historical_baseline_amount` — added in Phase 2 for data poisoning defence
- All primary keys are UUIDs
- Database is gitignored — run `schema.py` then `generate_data.py` to recreate locally

## Files
- `schema.py` — creates all 7 tables
- `generate_data.py` — populates tables with synthetic UAE data
- `data/fraud.db` — SQLite database (gitignored)

## Run
```powershell
python phase1/schema.py
python phase1/generate_data.py
```