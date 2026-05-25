# Phase 2 — Event Ingestion & Behavior Profile Tracker

## Overview
Handles real-time event ingestion and maintains per-user behavioral baselines.
Includes two security layers to protect profiles against data poisoning attacks.

## Files
- `ingest.py` — records new sessions and transactions into the database
- `profile_tracker.py` — recalculates and protects behavioral baselines

---

## ingest.py

Provides four functions for writing and reading live event data:

| Function | Description |
|----------|-------------|
| `ingest_session()` | Records a new login session — device, location, VPN flag |
| `ingest_transaction()` | Records a new transaction — amount, merchant, type, location |
| `get_user_by_id()` | Fetches a user record by UUID |
| `get_account_by_user()` | Fetches the account linked to a user |

---

## profile_tracker.py

Recalculates per-user behavioral baselines from transaction history.
Two protection layers defend against data poisoning attacks.

### Baseline Values Tracked

| Field | Method |
|-------|--------|
| `avg_transaction_amount` | Mean of all historical transaction amounts |
| `usual_location` | Most frequent transaction location |
| `typical_device` | Most frequent session device type |
| `typical_login_hour` | Average login hour across all sessions |
| `historical_baseline_amount` | Set on first profile write, never changed |

### Baseline Protection Layers

| Layer | Function | Description |
|-------|----------|-------------|
| Layer 1 | `apply_avg_cap()` | Caps how much a single update can shift the average — max 15% movement per update. Prevents rapid baseline manipulation. |
| Layer 2 | `check_baseline_drift()` | Compares current average against the stored historical baseline. Blocks update if drift exceeds 40%. Catches slow, patient poisoning attacks. |

### Protection Flow

New transaction arrives
↓
Compute raw new average from all transactions
↓
Layer 1 — Apply 15% movement cap
↓
Layer 2 — Check drift against historical baseline (40% threshold)
↓
Pass → Write updated profile to DB
Fail → Freeze update, profile unchanged

### Key Functions

| Function | Description |
|----------|-------------|
| `recalculate_profile()` | Recalculates one user's profile with both protection layers applied |
| `recalculate_all_profiles()` | Loops all users — used by Phase 5 batch simulation |
| `get_profile()` | Fetches current profile row — used by Phase 3 risk engine |

## Security Note
`recalculate_profile()` is called from Phase 4 `run_risk_engine()` **only when
the decision is not BLOCK**. Blocked transactions never update the baseline —
this is the first line of data poisoning defence.