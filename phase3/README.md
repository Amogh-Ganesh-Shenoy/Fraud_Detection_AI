# Phase 3 — Rule-Based Risk Engine

## Overview
Scores every transaction against 9 risk rules and returns an APPROVE,
CHALLENGE, or BLOCK decision. Location risk is handled as a separate
module following the separation of concerns principle.

## Files
- `risk_engine.py` — core scoring engine, 9 rules, alert writer
- `location_risk.py` — location risk scorer, 3 sub-features, max +15

---

## Decision Thresholds

| Score | Decision |
|-------|----------|
| 0 – 30 | APPROVE |
| 31 – 70 | CHALLENGE |
| 71 – 100 | BLOCK |

---

## Risk Rules

| Rule | Points | Trigger |
|------|--------|---------|
| `VPN_DETECTED` | +20 | VPN active during session |
| `HIGH_AMOUNT` | +25 | Transaction amount > 3x user's average |
| `UNUSUAL_LOGIN_LOCATION` | +5 | Login city ≠ user's usual location |
| `UNUSUAL_TRANSACTION_LOCATION` | +5 | Transaction city ≠ user's usual location |
| `LOGIN_TRANSACTION_MISMATCH` | +5 | Login city ≠ transaction city |
| `NEW_DEVICE` | +15 | Device differs from user's typical device |
| `UNUSUAL_LOGIN_HOUR` | +10 | Login hour > 3h from typical login hour |
| `HIGH_VELOCITY` | +15 | > 3 transactions from same account in 10 mins |
| `STRUCTURING_DETECTED` | +25 | Repeated near-identical amounts at regular intervals |

**Maximum possible score: 125 — capped at 100**

---

## location_risk.py

Separates location scoring logic from the core engine for reusability
and clean architecture. Called by `risk_engine.py` during Rule 3 scoring.

### Sub-features

| Sub-feature | Points | Trigger |
|-------------|--------|---------|
| `UNUSUAL_LOGIN_LOCATION` | +5 | Login city ≠ profile usual location |
| `UNUSUAL_TRANSACTION_LOCATION` | +5 | Transaction city ≠ profile usual location |
| `LOGIN_TRANSACTION_MISMATCH` | +5 | Login city ≠ transaction city |

**Maximum combined location score: +15**

### Future Enhancement
`IMPOSSIBLE_TRAVEL` — flagged for Phase 6 implementation when the data
model distinguishes physical vs online transactions.

---

## Structuring Detection

Detects bot-driven fraud patterns where an attacker submits repeated
near-identical amounts at metronomic intervals to avoid velocity rules.

Detection logic:
1. Query transactions from same account, amount within ±5%, last 20 minutes
2. Require at least 3 matching transactions
3. Calculate time gaps between consecutive transactions
4. Flag if standard deviation of gaps < 20% of average gap

---

## Key Functions

| Function | Description |
|----------|-------------|
| `score_transaction()` | Core engine — fetches data, applies all rules, writes alert to DB |
| `get_decision()` | Converts numeric score to APPROVE / CHALLENGE / BLOCK |
| `check_structuring()` | Detects metronomic bot transaction patterns |
| `score_location_risk()` | Scores 3 location sub-features, returns score + reason codes |
| `print_result()` | Pretty prints result dict for terminal testing |

## Run
```powershell
# From project root
python -c "from phase3.risk_engine import score_transaction, print_result; ..."
```