# Phase 1 — Data Layer

## What this phase does
Builds the SQLite database and populates it with UAE-flavoured synthetic data using Faker.
This is the foundation for all subsequent phases.

## Files
- `schema.py` — Creates the SQLite database and all 7 tables
- `generate_data.py` — Populates the database with synthetic data

## Database Tables
| Table | Description |
|---|---|
| users | 100 synthetic UAE users with Emirates IDs, phone numbers, cities |
| accounts | One account per user, balance in AED |
| sessions | Login events with device, IP, location, VPN detection |
| transactions | 1000 transactions linked to accounts and sessions |
| behavior_profiles | Baseline behaviour per user (avg amount, usual location, device) |
| alerts | Risk engine decisions written here |
| fraud_labels | Ground truth — 10% of transactions flagged as fraud |

## Data Statistics
- 100 users
- 100 accounts
- 500 sessions
- 1000 transactions
- ~100 fraudulent transactions (10% fraud rate)

## How to run
```bash
python phase1/schema.py
python phase1/generate_data.py
```

## Dependencies
- faker
- python-dotenv

## Links to other phases
Phase 2 reads from all tables to ingest events and update behavior profiles.
Phase 3 reads transactions, sessions and behavior profiles to score risk.