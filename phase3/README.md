# Phase 3 — Rule-Based Risk Engine

## Overview

Phase 3 is the core decision engine of the fraud detection system. It evaluates
every transaction against 9 risk rules, calculates a cumulative risk score,
and returns a decision of APPROVE, CHALLENGE, or BLOCK. Results are written
to the `alerts` table for audit and dashboard display.

Phase 5 evaluates this engine in batch against all 1,100 transactions.
Phase 6 builds ML models on top of it. Phase 7 exposes it through the
`POST /score` FastAPI endpoint via `phase6/ensemble.py`.

---

## Files

| File | Purpose |
|------|---------|
| `phase3/location_risk.py` | Scores 3 location-based sub-features — pure Python, no DB queries |
| `phase3/risk_engine.py` | Core scoring engine — applies all 9 rules and writes alerts |

---

## How to Run

The risk engine is not run standalone — it is called at runtime by
`POST /score` in `api/main.py` via `phase6/ensemble.py`.

For terminal testing:
```python
from phase3.risk_engine import score_transaction, print_result
result = score_transaction(transaction_id, session_id)
print_result(result)
```

---

## Decision Thresholds

| Score Range | Decision |
|-------------|---------|
| 0 – 30 | APPROVE |
| 31 – 70 | CHALLENGE |
| 71+ | BLOCK |

Scores are uncapped — multiple rules firing simultaneously can push scores
well above 100. This is intentional and ensures high-severity rule
combinations always result in a BLOCK regardless of score ceiling.

---

## Risk Rules — 9 Rules

| Rule | Points | Trigger |
|------|--------|---------|
| `VPN_DETECTED` | +20 | VPN active during session |
| `HIGH_AMOUNT` | +25 to +75 | Transaction amount exceeds user average — tiered (see below) |
| `UNUSUAL_LOGIN_LOCATION` | +5 | Login city ≠ user's usual location |
| `UNUSUAL_TRANSACTION_LOCATION` | +5 | Transaction city ≠ user's usual location |
| `LOGIN_TRANSACTION_MISMATCH` | +5 | Login city ≠ transaction city |
| `NEW_DEVICE` | +15 | Device differs from user's typical device |
| `UNUSUAL_LOGIN_HOUR` | +10 | Login hour > 3h from typical login hour |
| `HIGH_VELOCITY` | +75 | > 3 transactions from same account within ±10 minutes |
| `STRUCTURING_DETECTED` | +25 | Repeated near-identical amounts at metronomic intervals |

### Score Design Rationale

- `HIGH_VELOCITY` is scored at +75 to guarantee an auto-BLOCK on its own —
  more than 3 transactions in 10 minutes has no legitimate explanation
- `STRUCTURING_DETECTED` is scored at +25 — it stacks with other rules
  rather than blocking alone, since isolated structuring without other signals
  may warrant review rather than an immediate block
- `HIGH_AMOUNT` uses tiered scoring so extreme deviations carry proportionally
  higher risk than borderline cases
- Location and device rules are low-point signals designed to stack with
  other rules rather than trigger decisions independently

---

## HIGH_AMOUNT — Tiered Scoring

Replaced the original single threshold (> 1.5x = +25) with 5 tiers in Phase 5
to better reflect the risk gradient of large transactions.

| Multiplier vs User Average | Points |
|---------------------------|--------|
| 1.5x – 2.2x | +25 |
| 2.2x – 2.9x | +35 |
| 2.9x – 3.6x | +50 |
| 3.6x – 4.3x | +65 |
| 4.3x+ | +75 |

**Source:** `transactions.amount` vs `behavior_profiles.avg_transaction_amount`

---

## location_risk.py

Handles all 3 location sub-features as a separate module. Called from
`score_transaction()` and returns a `(score, reason_codes)` tuple.

```python
score_location_risk(login_city, txn_city, usual_city) → (int, list[str])
```

| Parameter | Source |
|-----------|--------|
| `login_city` | `sessions.location` |
| `txn_city` | `transactions.location` |
| `usual_city` | `behavior_profiles.usual_location` |

All city comparisons are case-insensitive and whitespace-stripped.
Maximum combined location score: +15.

Separated into its own module specifically to support reuse in the
Phase 6 ML feature engineering pipeline — imported directly from `phase3/`.

---

## Structuring Detection

Detects smurfing — an automated fraud technique where repeated near-identical
amounts are submitted at suspiciously regular intervals to avoid HIGH_AMOUNT.

Detection logic:
1. Query transactions from same account, amount within ±5%, within ±20 minute window
2. Require at least 3 matching transactions
3. Calculate time gaps between consecutive transactions
4. Flag if standard deviation of gaps < 20% of average gap

```
std_dev < avg_gap × 0.20  →  metronomic regularity  →  STRUCTURING_DETECTED
```

Irregular timing (human behaviour) will not trigger this rule even if amounts match.

---

## score_transaction() — Data Flow

```
score_transaction(transaction_id, session_id)
        │
        ├── Fetch transaction + account   (transactions JOIN accounts)
        ├── Fetch session                 (sessions)
        ├── Fetch behavior profile        (behavior_profiles)
        │
        ├── Apply 9 rules → accumulate score + reason_codes
        │
        ├── get_decision(score) → APPROVE / CHALLENGE / BLOCK
        │
        ├── INSERT into alerts table
        │
        └── Return result dict
```

### Result Dictionary

```python
{
    "alert_id":       str,   # UUID — internal, not shown in UI
    "transaction_id": str,   # UUID — internal
    "user_id":        str,   # UUID — internal
    "amount":         float, # AED
    "merchant":       str,
    "location":       str,   # Transaction city
    "device":         str,   # Session device type
    "vpn":            bool,
    "risk_score":     int,   # Uncapped — can exceed 100
    "decision":       str,   # APPROVE / CHALLENGE / BLOCK
    "reason_codes":   list,  # All triggered rule names
    "timestamp":      str    # ISO format
}
```

Every call writes a row to the `alerts` table before returning.

---

## Phase 5 Evaluation Results

After running batch simulation across all 1,100 transactions:

| Metric | Value |
|--------|-------|
| Total Transactions | 1,100 |
| Actual Fraud | 100 |
| Predicted Blocks | 76 |
| Precision | 0.908 |
| Recall | 0.690 |
| F1 Score | 0.784 |
| AUC | 0.8916 |

Recall of 0.690 reflects the 4 intentional Scenario D slip-throughs and
transactions that score in CHALLENGE rather than BLOCK. The Phase 6 ML
layer is designed to close this gap.

---

## Data Sources

| Rule | Tables Read |
|------|------------|
| VPN_DETECTED | `sessions` |
| HIGH_AMOUNT | `transactions`, `behavior_profiles` |
| Location rules | `sessions`, `transactions`, `behavior_profiles` |
| NEW_DEVICE | `sessions`, `behavior_profiles` |
| UNUSUAL_LOGIN_HOUR | `sessions`, `behavior_profiles` |
| HIGH_VELOCITY | `transactions` |
| STRUCTURING_DETECTED | `transactions` |

**Writes to:** `alerts` table on every call to `score_transaction()`

---

## Dependencies

```
psycopg>=3.0
python-dotenv
```

---

## Notes

- `HIGH_VELOCITY` and `STRUCTURING_DETECTED` both use the transaction's own
  timestamp as the reference point — not `NOW()`. This is critical for
  synthetic data where transactions are backdated 90 days — using `NOW()`
  would mean these rules never fire against historical data.
- `NEW_DEVICE` comparison is case-insensitive — device type values in
  `behavior_profiles.typical_device` must match the exact strings used in
  `frontend/components/ScoreForm.tsx` dropdown, otherwise `NEW_DEVICE`
  fires on every transaction regardless of user selection.
- `print_result()` at the bottom of `risk_engine.py` is a terminal testing
  helper only — it is not called at runtime by the API.