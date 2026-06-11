# Phase 6 — ML Models: Z-Score Anomaly Detection, Random Forest Classifier & Ensemble

## Overview

Phase 6 introduces two machine learning models — a Z-Score anomaly detector and a
Random Forest classifier — and combines them with the Phase 3 rule engine into a
weighted ensemble that produces a single final fraud decision per transaction.

The ensemble is the primary decision-maker in production. It is called at runtime
by `POST /score` in `api/main.py` via `phase6/ensemble.py`. All three evaluation
functions (`evaluate_zscore`, `evaluate_random_forest`, `evaluate_ensemble`) are
offline tools only — they are not called by any API endpoint.

---

## Files

| File | Purpose |
|------|---------|
| `phase6/zscore_model.py` | Z-Score anomaly detection — flags statistically unusual transaction amounts |
| `phase6/random_forest_model.py` | Supervised Random Forest classifier — trained on 8 engineered features |
| `phase6/ensemble.py` | Weighted ensemble — combines all 3 models into one final decision |
| `phase6/random_forest.pkl` | Serialised trained model — 320KB, committed to GitHub, loaded at runtime |

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

> `random_forest.pkl` must exist before running the ensemble.
> Always run `random_forest_model.py` first on a fresh setup.
> After running, update the static metric values in `api/main.py`
> `GET /metrics` with the new output before redeploying to Render.

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
| Std dev fallback | `avg_amount` — used when < 3 historical transactions exist |
| Zero std dev fallback | `avg_amount` — used when all historical amounts are identical |

**Data sources:**

| Table | Columns Used |
|-------|-------------|
| `transactions` | amount, account_id, transaction_id |
| `accounts` | account_id → user_id |
| `behavior_profiles` | avg_transaction_amount |

**Runtime function:** `score_zscore(transaction_id, user_id)`
Called by `ensemble.py → ensemble_score()` at runtime.

**Offline function:** `evaluate_zscore()`
Pre-fetches all data in bulk — no per-transaction DB calls. Not called at runtime.

---

## Model 2 — Random Forest Classifier

Supervised ML model trained on 8 engineered features. Learns which combinations
of session, transaction, and behavioral signals indicate fraud.

**Training configuration:**

| Parameter | Value |
|-----------|-------|
| Estimators | 100 decision trees |
| Class weight | balanced — compensates for 100 fraud vs 1,000 legitimate |
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
| `hour_deviation` | sessions, behavior_profiles | abs(login_hour - typical_login_hour), wrapped at midnight |
| `velocity_count` | transactions | Transactions from same account within ±10 min window |

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

**Runtime function:** `predict_single(transaction_id, user_id)`
Loads `random_forest.pkl`, engineers 8 features, returns `fraud_probability`.
Called by `ensemble.py → ensemble_score()` at runtime.

**Offline functions:** `build_feature_matrix()`, `train_random_forest()`, `evaluate_random_forest()`
Not called at runtime. Run locally to retrain and update the `.pkl` file.

---

## Model 3 — Weighted Ensemble

Combines all 3 model outputs by normalising each to a 0.0–1.0 scale and
applying a weighted average to produce a single ensemble score.

**Weights:**

| Model | Weight | Reason |
|-------|--------|--------|
| Rule Engine (Phase 3) | 0.50 | Strong precision, domain-encoded knowledge |
| Random Forest | 0.35 | Best recall, learned fraud patterns from data |
| Z-Score | 0.15 | Weakest on this dataset — single feature signal |

**Normalisation:**

| Model Output | Method |
|-------------|--------|
| `fraud_probability` | Already 0.0–1.0 — no change |
| `risk_score` | Divide by 150, clamp to 1.0 |
| `anomaly_score` | Divide by 5.0, clamp to 1.0. Negative scores floored at 0.0 |

**Decision thresholds:**

| Range | Decision |
|-------|---------|
| 0.00 – 0.30 | APPROVE |
| 0.30 – 0.35 | CHALLENGE |
| 0.35+ | BLOCK |

**Runtime function:** `ensemble_score(transaction_id, session_id, user_id)`
Orchestrates all 3 models, returns full result dict to `api/main.py POST /score`.

**Offline function:** `evaluate_ensemble()`
Pre-fetches all data in bulk, runs batch RF prediction in one call,
computes all metrics in memory. Not called at runtime.

---

## Ensemble Score Flow

```
POST /score (api/main.py)
        │
        └── ensemble_score(transaction_id, session_id, user_id)
                │
                ├── score_transaction()     → risk_score, reason_codes
                │   phase3/risk_engine.py   → writes to alerts table
                │
                ├── score_zscore()          → anomaly_score, is_anomaly
                │   phase6/zscore_model.py
                │
                ├── predict_single()        → fraud_probability
                │   phase6/random_forest_model.py
                │   loads phase6/random_forest.pkl
                │
                ├── Normalise all 3 scores → 0.0–1.0
                ├── Weighted average       → ensemble_score
                └── Threshold mapping      → APPROVE / CHALLENGE / BLOCK
```

---

## Evaluation Results

### Individual Model Comparison

| Model | Precision | Recall | F1 | AUC |
|-------|-----------|--------|----|-----|
| Phase 5 Rule Engine (baseline) | 0.908 | 0.690 | 0.784 | 0.8916 |
| Z-Score | 0.571 | 0.040 | 0.075 | — |
| Random Forest (test set 20%) | 0.950 | 0.950 | 0.950 | 0.9992 |
| Ensemble (full DB) | 1.000 | 0.790 | 0.883 | — |

The ensemble achieves perfect precision (0 false positives) at the cost of
some recall — a deliberate trade-off. The CHALLENGE threshold was set low
(0.35) to push borderline cases to BLOCK rather than APPROVE, prioritising
recall over precision.

> Perfect Random Forest metrics (0.95/0.95) reflect synthetic data with clean,
> distinct fraud patterns. Real-world performance would produce ~0.90–0.95.
> This is an acknowledged limitation of synthetic training data.

---

## Key Changes Made During Phase 6

### ensemble.py — Weights Revised
Original weights from the Phase 6 design doc had Random Forest at 0.50
and Rule Engine at 0.35. Final code reverses this — Rule Engine carries
0.50 and Random Forest carries 0.35. Rule engine precision on synthetic
data is more reliable as a primary signal; RF supports it.

### ensemble.py — CHALLENGE Threshold Lowered
CHALLENGE upper bound lowered from 0.45 → 0.35. This pushes more
borderline cases to BLOCK rather than CHALLENGE, improving Recall.
False negatives (missed fraud) are more costly than false positives
in fraud detection.

### ensemble.py — Bulk Query Optimisation
`evaluate_ensemble()` originally made per-transaction DB calls — 7,000+
network round trips against Render PostgreSQL in Oregon. Rewritten to
pre-fetch all data in 5 bulk queries, build features in memory, and run
a single batch `predict_proba()` call for all 1,100 transactions.

### random_forest_model.py — Named DataFrame for predict_proba()
`predict_single()` was updated to pass a named pandas DataFrame instead
of a raw numpy array to `model.predict_proba()`. This eliminates the
sklearn `UserWarning` about feature names that fired on every prediction
call in FastAPI logs.

### random_forest_model.py — Fraud Amount Range Fixed
Original fraud generation used `random.uniform(1.6, 2.5)` as a multiplier.
The model learned fraud only existed up to 2.5× average, returning near-zero
probability on larger amounts. Updated to
`random.uniform(3.0, random.uniform(5.0, 15.0))` to cover high-amount fraud.

### zscore_model.py — Zero Std Dev Edge Case
Added explicit handling for the case where all historical transaction amounts
are identical (std dev = 0). Falls back to `avg_amount` to prevent
division by zero rather than raising an exception.

### All Phase 6 Files — PostgreSQL Migration
All three files were fully rewritten from SQLite to PostgreSQL:
- `sqlite3.connect(DB_PATH)` → `psycopg.connect(DATABASE_URL, row_factory=dict_row)`
- `?` binding → `%s` binding
- `datetime('now', '-10 minutes')` → `%s::timestamp - interval '10 minutes'`
- `sqlite3.Row` → `psycopg dict_row`

---

## Dependencies

```
scikit-learn
pandas
numpy
psycopg>=3.0
python-dotenv
```

---

## Notes

- `random_forest.pkl` is committed to GitHub (320KB) and deploys with the
  codebase to Render. No retraining occurs at runtime — the model is loaded
  from disk on every `predict_single()` call.
- Z-Score performs poorly standalone (Recall 0.04) because legitimate and
  fraud transaction amounts overlap significantly in the synthetic data
  (AED 10–15,000 legitimate vs fraud at 3–15× average). Z-Score contributes
  15% weight in the ensemble and is most useful in live interactive mode
  where users can enter extreme amounts manually.
- `evaluate_ensemble()`, `evaluate_zscore()`, and `evaluate_random_forest()`
  are all offline tools. None write to the `alerts` table — evaluation
  replicates scoring logic in memory to avoid polluting production data.
- The `velocity_count` bulk query in `build_feature_matrix()` and
  `evaluate_ensemble()` uses a self-join on `transactions` — this is the
  same logic as `HIGH_VELOCITY` in the rule engine, ensuring consistency
  between the rule engine and Random Forest feature definitions.