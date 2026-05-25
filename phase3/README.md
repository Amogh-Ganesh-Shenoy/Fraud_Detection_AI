# Phase 3 — Rule-Based Risk Engine

## What this phase does
The core fraud detection engine. Takes a transaction and session, compares them
against the user's behavior profile, applies 6 risk rules, produces a risk score
from 0-100 and returns a decision.

## Files
- `risk_engine.py` — Full rule-based scoring engine

## Risk Score Thresholds
| Score | Decision |
|---|---|
| 0 - 30 | APPROVE |
| 31 - 70 | CHALLENGE |
| 71 - 100 | BLOCK |

## Risk Rules
| Rule | Points | Trigger Condition |
|---|---|---|
| VPN_DETECTED | +20 | VPN detected during session |
| HIGH_AMOUNT | +25 | Transaction amount exceeds 3x user average |
| UNUSUAL_LOCATION | +15 | Transaction location differs from usual location |
| NEW_DEVICE | +15 | Device differs from typical device |
| UNUSUAL_LOGIN_HOUR | +10 | Login hour more than 3 hours from typical hour |
| HIGH_VELOCITY | +15 | More than 3 transactions in last 10 minutes |

## Key Functions
| Function | Description |
|---|---|
| score_transaction() | Core engine — scores a transaction, writes to alerts table |
| get_decision() | Converts risk score to APPROVE/CHALLENGE/BLOCK |
| print_result() | Pretty prints scoring result for testing |

## Output
Every scored transaction produces an alert record containing:
- Risk score
- Decision
- Reason codes
- Timestamp

## How to run
```bash
python phase3/risk_engine.py
```

## Security
- All database queries use parameterised statements
- No raw user input touches the database directly
- Score is capped at 100 regardless of rules triggered

## Links to other phases
Phase 2 maintains the behavior profiles this engine reads.
Phase 4 Streamlit UI calls this engine and displays results.
Phase 5 runs this engine in bulk across all transactions.
Phase 6 adds ML scoring on top of this rule layer.