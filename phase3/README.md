# Phase 3 — Rule-Based Risk Engine

## Overview
Phase 3 is the core decision engine of the fraud detection system. It evaluates
every transaction against 9 risk rules, calculates a cumulative risk score,
and returns a decision of APPROVE, CHALLENGE, or BLOCK. Results are written
to the `alerts` table for audit and dashboard display.

---

## Files
| File | Purpose |
|------|---------|
| `phase3/location_risk.py` | Scores 3 location-based sub-features |
| `phase3/risk_engine.py` | Core scoring engine — applies all 9 rules and writes alerts |

---

## How to Run

```bash
# The risk engine is called programmatically — not run standalone.
# It is invoked from Phase 4 (app.py) and Phase 5 (batch_sim.py).

# For terminal testing, call score_transaction() directly:
from phase3.risk_engine import score_transaction, print_result
result = score_transaction(transaction_id, session_id)
print_result(result)
```

---

## Decision Thresholds

| Score Range | Decision |
|-------------|----------|
| 0 – 30 | APPROVE |
| 31 – 70 | CHALLENGE |
| 71+ | BLOCK |

> The score is **uncapped** — multiple rules firing simultaneously can
> push scores well above 100. This is intentional and ensures high-severity
> rule combinations always result in a BLOCK regardless of score ceiling.

---

## Risk Rules — 9 Rules

| Rule | Points | Trigger |
|------|--------|---------|
| `VPN_DETECTED` | +20 | VPN active during session |
| `HIGH_AMOUNT` | +25 | Transaction amount > 1.5x user's average |
| `UNUSUAL_LOGIN_LOCATION` | +5 | Login city ≠ user's usual location |
| `UNUSUAL_TRANSACTION_LOCATION` | +5 | Transaction city ≠ user's usual location |
| `LOGIN_TRANSACTION_MISMATCH` | +5 | Login city ≠ transaction city |
| `NEW_DEVICE` | +15 | Device differs from user's typical device |
| `UNUSUAL_LOGIN_HOUR` | +10 | Login hour > 3h from typical login hour |
| `HIGH_VELOCITY` | +75 | > 3 transactions from same account within 10 minutes |
| `STRUCTURING_DETECTED` | +75 | Repeated near-identical amounts at metronomic intervals |

### Score Design Rationale
- `HIGH_VELOCITY` and `STRUCTURING_DETECTED` are scored at +75 to guarantee
  an auto-BLOCK on their own — these patterns have no legitimate explanation
- `HIGH_AMOUNT` is kept at +25 since a single large transaction (e.g. rent,
  insurance) can occur legitimately — it contributes to a combined score
  rather than blocking alone
- Location and device rules are low-point signals designed to stack with
  other rules rather than trigger decisions independently

---

## location_risk.py

Handles all 3 location sub-features as a separate module. Called from
`score_transaction()` and returns a `(score, reason_codes)` tuple.

```python
score_location_risk(login_city, txn_city, usual_city)
→ (int, list[str])
```

Separated into its own module specifically to support reuse in the
Phase 6 ML feature engineering pipeline.

---

## Structuring Detection — check_structuring()

Detects smurfing — an automated fraud technique where repeated
near-identical amounts are submitted at suspiciously regular intervals.

Detection logic:
1. Query transactions from same account, amount within ±5%, within ±20 minute window
2. Require at least 3 matching transactions
3. Calculate time gaps between consecutive transactions
4. Flag if standard deviation of gaps < 20% of average gap

std_dev < avg_gap × 0.20  →  metronomic regularity  →  STRUCTURING_DETECTED

> Both HIGH_VELOCITY and STRUCTURING use the **transaction's own timestamp**
> as the reference point — not `datetime('now')`. This is critical for
> synthetic data where transactions are backdated 90 days.

---

## score_transaction() Output

```python
{
    "alert_id":       str,
    "transaction_id": str,
    "user_id":        str,
    "amount":         float,
    "merchant":       str,
    "location":       str,
    "device":         str,
    "vpn":            bool,
    "risk_score":     int,
    "decision":       str,   # APPROVE / CHALLENGE / BLOCK
    "reason_codes":   list,
    "timestamp":      str
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

---

## Dependencies

python-dotenv
