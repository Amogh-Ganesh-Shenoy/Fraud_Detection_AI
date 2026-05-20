# Phase 2 — Event Ingestion and Behavior Profile Tracking

## What this phase does
Handles real-time event ingestion and keeps user behavior profiles up to date.
When a new login or transaction occurs, this phase records it and recalculates
what normal looks like for that user.

## Files
- `ingest.py` — Writes new session and transaction events to the database
- `profile_tracker.py` — Recalculates behavior profiles after new events

## Key Functions

### ingest.py
| Function | Description |
|---|---|
| ingest_session() | Records a new login event, returns session_id |
| ingest_transaction() | Records a new transaction event, returns transaction_id |
| get_user_by_id() | Fetches a user record by user_id |
| get_account_by_user() | Fetches an account linked to a user |

### profile_tracker.py
| Function | Description |
|---|---|
| recalculate_profile() | Recalculates one user's behavior profile |
| recalculate_all_profiles() | Recalculates all users' profiles |
| get_profile() | Fetches the current profile for a user |

## Behavior Profile Fields
| Field | How it is calculated |
|---|---|
| avg_transaction_amount | Average of all transaction amounts for this user |
| usual_location | Most frequent transaction location |
| typical_device | Most frequently used device across sessions |
| typical_login_hour | Most frequent login hour across sessions |

## How to run
```bash
python phase2/ingest.py
python phase2/profile_tracker.py
```

## Links to other phases
Phase 1 creates the initial data this phase reads from.
Phase 3 reads the behavior profiles this phase maintains.