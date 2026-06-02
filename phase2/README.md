# Phase 2 — Event Ingestion & Behavior Profile Tracker

## Overview
Phase 2 adds two capabilities on top of the Phase 1 schema:
1. **Event ingestion** — records live sessions and transactions into the database
2. **Behavior profile tracker** — recalculates user behavioral baselines with
   two built-in protection layers against data poisoning attacks

---

## Files
| File | Purpose |
|------|---------|
| `phase2/ingest.py` | Ingests session and transaction events into the database |
| `phase2/profile_tracker.py` | Recalculates behavior profiles with baseline protection |

---

## How to Run

```bash
# Ingest a session and transaction manually (for testing)
python phase2/ingest.py
```

> Profile recalculation is triggered automatically from the Phase 4
> risk engine after every non-BLOCK decision. It is not run standalone.

---

## ingest.py

Provides four functions for recording live events:

| Function | Purpose |
|----------|---------|
| `ingest_session()` | Records a new login session |
| `ingest_transaction()` | Records a new transaction |
| `get_user_by_id()` | Fetches a user record by user_id |
| `get_account_by_user()` | Fetches the account linked to a user |

---

## profile_tracker.py

Recalculates a user's behavior profile from their full transaction and
session history. The profile stores:

- `avg_transaction_amount` — rolling average spend
- `usual_location` — most frequent transaction city
- `typical_device` — most frequently used device
- `typical_login_hour` — average login hour
- `historical_baseline_amount` — locked anchor set on first profile write

---

## Baseline Protection — 2 Layers

### Layer 1 — Per-Transaction Cap
Limits how much a single update can shift `avg_transaction_amount`.
Maximum allowed movement per update: **±15% of current average**.

current_avg = AED 2,000
new_avg     = AED 800   ← attacker submitted many small transactions
max_shift   = AED 300   ← 15% of 2,000
capped_avg  = AED 1,700 ← not 800

### Layer 2 — Drift Detector
Compares the proposed new average against the locked
`historical_baseline_amount`. If drift exceeds **40%**, the update
is blocked entirely and a drift alert is printed.

historical_baseline = AED 2,000
proposed new avg    = AED 900
drift               = 55%  → BLOCKED (threshold: 40%)

**Why this matters:** Without these layers, an attacker could
submit hundreds of small transactions over days to drag the
baseline down — making future large fraudulent transactions
look normal to the HIGH_AMOUNT rule.

---

## Protection Flow

New transaction ingested
│
▼
Compute raw new average from all transactions
│
▼
Layer 1 — Apply ±15% cap on movement
│
▼
Layer 2 — Check drift vs historical baseline
│
drift > 40%?
┌────┴────┐
YES       NO
│         │
BLOCK     Write updated profile to DB
update

---

## Key Design Decision

`recalculate_profile()` is called from Phase 4 **only when the
decision is not BLOCK**. This means fraudulent transactions that
get blocked never influence the user's behavioral baseline —
the first and most important line of defence against data poisoning.

---

## Dependencies

python-dotenv