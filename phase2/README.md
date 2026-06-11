# Phase 2 — Event Ingestion & Behavior Profile Tracker

## Overview

Phase 2 handles two responsibilities: writing live session and transaction
events to the database at runtime, and maintaining per-user behavioral
baselines that the Phase 3 risk engine uses for anomaly detection.

The profile tracker includes two security layers designed to defend against
data poisoning attacks — scenarios where an attacker submits crafted
transactions to manipulate a user's behavioral baseline and make future
fraudulent transactions appear normal.

---

## Files

| File | Purpose |
|------|---------|
| `phase2/ingest.py` | Writes sessions and transactions to PostgreSQL at runtime |
| `phase2/profile_tracker.py` | Recalculates behavioral baselines with two protection layers |

---

## How It Works

### Ingestion Flow

```
POST /score (api/main.py)
        │
        ├── ingest_session()       → writes to sessions table, returns session_id
        ├── ingest_transaction()   → writes to transactions table, returns transaction_id
        └── (after scoring)
            └── recalculate_profile()  → updates behavior_profiles if decision != BLOCK
```

`ingest.py` is called at runtime by `api/main.py`. It is never called directly
by the React frontend — all data flows through FastAPI endpoints.

---

## ingest.py — Functions

### `ingest_session()`

| | |
|---|---|
| **Purpose** | Records a new login event to the `sessions` table |
| **Called by** | `POST /session` and `POST /score` in `api/main.py` |
| **Returns** | `session_id` (UUID) — passed to `ingest_transaction()` |
| **Writes to** | `sessions` table |

### `ingest_transaction()`

| | |
|---|---|
| **Purpose** | Records a new transaction to the `transactions` table |
| **Called by** | `POST /score` in `api/main.py` after `ingest_session()` |
| **Returns** | `transaction_id` (UUID) — passed to `score_transaction()` in Phase 3 |
| **Writes to** | `transactions` table |

### `get_user_by_id()`

| | |
|---|---|
| **Purpose** | Fetches a user record by `user_id` |
| **Source** | `users` table — populated by Phase 1 |
| **Called by** | `api/main.py` for user resolution |

### `get_account_by_user()`

| | |
|---|---|
| **Purpose** | Fetches the account linked to a user |
| **Source** | `accounts` table — populated by Phase 1 |
| **Called by** | `api/main.py` to resolve `account_id` before scoring |

---

## profile_tracker.py — Baseline Protection

The profile tracker maintains `behavior_profiles` — the per-user averages
the risk engine compares against at scoring time. Two security layers protect
these baselines from being manipulated.

### Why This Matters

Without protection, an attacker could submit hundreds of small transactions
to drag `avg_transaction_amount` down — making future large fraudulent
transactions appear statistically normal to the risk engine.

### Protection Architecture

```
recalculate_profile(user_id)
        │
        ├── Compute raw new average from transaction history
        │
        ├── LAYER 1 — apply_avg_cap()
        │       Limits movement to ±15% per update
        │       Prevents rapid baseline manipulation
        │
        ├── LAYER 2 — check_baseline_drift()
        │       Compares capped average to historical_baseline_amount
        │       Blocks update if drift exceeds 40%
        │       Catches slow, patient poisoning over days or weeks
        │
        └── Write to behavior_profiles only if both layers pass
```

**Critical:** `recalculate_profile()` is only called when the transaction
decision is not `BLOCK`. Blocked transactions never influence the baseline —
this is the first line of data poisoning defence.

---

## Baseline Protection — Layer 1

### `apply_avg_cap(current_avg, new_avg, max_shift_pct=0.15)`

Limits how much the average can shift in a single profile update.

**Example:**
```
current_avg = AED 2,000
new_avg     = AED 800    ← attacker submitted many small transactions
max_shift   = 15%        → AED 300 maximum movement allowed
capped_avg  = AED 1,700  ← not AED 800
```

| Parameter | Value | Notes |
|-----------|-------|-------|
| `max_shift_pct` | 0.15 | 15% maximum movement per update |
| Returns | Capped float | Constrained to ±15% of current average |

---

## Baseline Protection — Layer 2

### `check_baseline_drift(user_id, new_avg, conn, drift_threshold=0.40)`

Compares the proposed new average against the permanently stored
`historical_baseline_amount`. If drift exceeds 40%, the update is blocked.

| Parameter | Value | Notes |
|-----------|-------|-------|
| `drift_threshold` | 0.40 | 40% maximum drift from historical baseline |
| Returns | `True` | Drift detected — update blocked |
| Returns | `False` | Drift acceptable — update proceeds |

The 40% threshold is deliberately chosen:
- Conservative enough to catch meaningful manipulation
- Permissive enough not to flag legitimate spending changes over time

---

## Other Functions

### `recalculate_profile(user_id)`
Recalculates one user's full profile from transaction history. Applies both
protection layers before writing. Called after every non-BLOCK decision.

### `recalculate_all_profiles()`
Loops all users and recalculates every profile. Used by Phase 5 batch
simulation after bulk data inserts. Both protection layers still apply.

### `get_profile(user_id)`
Fetches the current profile row for a user. Used by the Phase 3 risk engine
to retrieve baseline values for scoring.

---

## Data Sources

| Function | Tables Read | Tables Written |
|----------|------------|----------------|
| `ingest_session()` | — | `sessions` |
| `ingest_transaction()` | — | `transactions` |
| `get_account_by_user()` | `accounts` | — |
| `recalculate_profile()` | `transactions`, `sessions`, `accounts`, `behavior_profiles` | `behavior_profiles` |

---

## Dependencies

```
psycopg>=3.0
python-dotenv
```

---

## Notes

- `profile_tracker.py` still targets SQLite (`sqlite3.connect(DB_PATH)`) and
  has not been migrated to PostgreSQL. At runtime in production, `recalculate_profile()`
  is not functional against the Render PostgreSQL database. Migration to `psycopg`
  with `DATABASE_URL` is required for this to work in production.
- `ingest.py` is fully migrated to PostgreSQL using `psycopg` with `%s` binding
  and `dict_row` — consistent with all other Phase 7 runtime files.
- The `historical_baseline_amount` column is set on the first profile write and
  never changed after that — it is the permanent anchor for Layer 2 drift detection.