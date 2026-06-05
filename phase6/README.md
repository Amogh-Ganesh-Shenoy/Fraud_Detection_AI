# Phase 6 — ML Models: Z-Score Anomaly Detection, Random Forest Classifier & Ensemble

## Overview
Phase 6 introduces two machine learning models — a Z-Score anomaly detector and a
Random Forest classifier — and combines them with the Phase 3 rule engine into a
weighted ensemble that produces a single final fraud decision per transaction.
---

## Files

| File | Purpose |
|------|---------|
| `phase6/zscore_model.py` | Z-Score anomaly detection — flags statistically unusual transaction amounts |
| `phase6/random_forest_model.py` | Supervised Random Forest classifier — trained on 8 engineered features |
| `phase6/ensemble.py` | Weighted ensemble — combines all 3 models into one final decision |
| `phase6/random_forest.pkl` | Serialised trained model — loaded by ensemble at runtime |

---

## How to Run

```bash
# Step 1 — Train and evaluate the Random Forest (saves random_forest.pkl)
python -m phase6.random_forest_model

# Step 2 — Evaluate the Z-Score model standalone
python -m phase6.zscore_model

# Step 3 — Run full ensemble evaluation across all 1,100 transactions
python -m phase6.ensemble
```

> **Note:** `random_forest.pkl` must exist before running the ensemble.
> Always run `random_forest_model.py` first on a fresh setup.

---

## Model 1 — Z-Score Anomaly Detection

Detects statistically unusual transaction amounts using per-user standard deviation.

**Formula:**
```
Z = (transaction_amount - avg_amount) / std_deviation
```

| Parameter | Value |
|-----------|-------|
| Anomaly threshold | Z ≥ 2.5 |
| Normalisation ceiling | 5.0 |
| Std dev fallback | `avg_amount` (used when < 3 historical transactions exist) |

**Data sources:**
| Table | Columns Used |
|-------|-------------|
| `transactions` | amount, account_id |
| `accounts` | account_id → user_id |
| `behavior_profiles` | avg_transaction_amount |

---

## Model 2 — Random Forest Classifier

Supervised ML model trained on 8 engineered features. Learns which combinations
of session, transaction, and behavioral signals indicate fraud.

**Training configuration:**

| Parameter | Value |
|-----------|-------|
| Estimators | 100 decision trees |
| Class weight | balanced (compensates for 100 fraud vs 1,000 legitimate) |
| Train / test split | 80% / 20% (stratified, random_state=42) |
| Fraud threshold | 0.5 |
| Model path | `phase6/random_forest.pkl` |

**Features (8 total):**

| Feature | Source Tables | Description |
|---------|--------------|-------------|
| `amount_ratio` | transactions, behavior_profiles | Transaction amount / user average |
| `vpn_flag` | sessions | VPN active during session (0/1) |
| `new_device_flag` | sessions, behavior_profiles | Device differs from typical (0/1) |
| `unusual_login_location` | sessions, behavior_profiles | Login city differs from usual (0/1) |
| `unusual_txn_location` | transactions, behavior_profiles | Txn city differs from usual (0/1) |
| `login_txn_mismatch` | sessions, transactions | Login city differs from txn city (0/1) |
| `hour_deviation` | sessions, behavior_profiles | abs(login_hour - typical_login_hour) |
| `velocity_count` | transactions | Transactions within ±10 min window |

**Feature importances (trained result):**

| Feature | Importance |
|---------|-----------|
| `velocity_count` | 0.5060 |
| `amount_ratio` | 0.2800 |
| `unusual_login_location` | 0.1267 |
| `vpn_flag` | 0.0366 |
| `hour_deviation` | 0.0258 |
| `unusual_txn_location` | 0.0108 |
| `login_txn_mismatch` | 0.0090 |
| `new_device_flag` | 0.0051 |

---

## Model 3 — Weighted Ensemble

Combines all 3 model outputs by normalising each to a 0.0–1.0 scale and
applying a weighted average to produce a single ensemble score.

**Weights:**

| Model | Weight | Reason |
|-------|--------|--------|
| Random Forest | 0.50 | Best recall, learned fraud patterns from data |
| Rule Engine (Phase 3) | 0.35 | Strong precision, domain-encoded knowledge |
| Z-Score | 0.15 | Weakest on this dataset — single feature signal |

**Normalisation:**

| Model Output | Method |
|-------------|--------|
| `fraud_probability` | Already 0.0–1.0 — no change |
| `risk_score` | Divide by 150, clamp to 1.0 |
| `anomaly_score` | Divide by 5.0, clamp to 1.0 |

**Decision thresholds:**

| Range | Decision |
|-------|---------|
| 0.00 – 0.30 | APPROVE |
| 0.30 – 0.45 | CHALLENGE |
| 0.45+ | BLOCK |

---

## Evaluation Results

### Individual Model Comparison

| Model | Precision | Recall | F1 | AUC |
|-------|-----------|--------|----|-----|
| Phase 5 Rule Engine (baseline) | 0.908 | 0.690 | 0.784 | 0.8916 |
| Z-Score | 0.571 | 0.040 | 0.075 | — |
| Random Forest (test set 20%) | 0.950 | 0.950 | 0.950 | 0.9992 |
| Ensemble (full DB) | 1.000 | 0.790 | 0.883 | — |

> The ensemble achieves perfect precision (0 false positives) at the cost of
> some recall — a deliberate trade-off for a production fraud system where
> blocking legitimate transactions carries high operational cost.

---

## Dependencies

```
scikit-learn
pandas
numpy
python-dotenv
```

---

## Notes

- Run `random_forest_model.py` first on any fresh environment to generate `random_forest.pkl`.
  The ensemble will fail silently (defaulting RF score to 0.0) if the `.pkl` file is missing.
- The `check_structuring` function inside `phase3/risk_engine.py → score_transaction()` is
  defined but does not return a value — structuring detection does not currently fire in the
  ensemble pipeline. This is a known issue to be resolved in a future phase.
- Z-Score uses `avg_amount` as a fallback std dev for users with fewer than 3 transactions —
  this path becomes less common as transaction history accumulates.
- The ensemble CHALLENGE threshold was lowered from 0.60 → 0.45 to improve recall
  (false negatives are more costly than false positives in fraud detection).