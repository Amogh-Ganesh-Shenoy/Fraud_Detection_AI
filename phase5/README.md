# Phase 5 — Model Evaluation

## Overview

Phase 5 evaluates the Phase 3 rule-based risk engine against ground-truth
fraud labels. It runs a batch simulation across all 1,100 transactions,
computes a full suite of classification metrics, and renders the results
as an interactive Streamlit tab inside the Phase 4 dashboard.

> **Note:** Phase 5 is an offline evaluation tool. It is not called at
> runtime by the Phase 7 FastAPI backend or the React frontend. The
> metrics it produces are hardcoded as static values in `api/main.py`'s
> `GET /metrics` endpoint and displayed in the React dashboard's
> MetricsPanel component. `batch_sim.py` should be re-run locally
> whenever the rule engine or data changes, and the output values
> updated manually in `api/main.py`.

---

## Files

| File | Purpose |
|------|---------|
| `phase5/batch_sim.py` | Loops all transactions through the risk engine in memory — no DB calls per transaction, no alerts written |
| `phase5/metrics.py` | Computes confusion matrix, Precision, Recall, F1, ROC, AUC from batch sim DataFrame |
| `phase5/dashboard_tab.py` | Streamlit tab rendering all metrics and charts — embedded in Phase 4 dashboard |

---

## How to Run

Phase 5 is run offline from the terminal:

```bash
python -m phase5.batch_sim
```

Or accessed via the Phase 4 Streamlit dashboard:

```bash
streamlit run phase4/app.py
```

Navigate to the **Phase 5 — Model Evaluation** tab and click
**▶ Run Batch Simulation**.

Results are cached in `st.session_state` — the simulation does not
re-run on every Streamlit interaction.

> After running, update the static metric values in `api/main.py`
> `GET /metrics` with the new output before redeploying to Render.

---

## Binary Classification Mapping

| Engine Decision | Predicted Label |
|----------------|----------------|
| BLOCK | 1 (Fraud) |
| CHALLENGE | 0 (Not Fraud) |
| APPROVE | 0 (Not Fraud) |

CHALLENGE is treated as not-fraud for binary classification. This is a
deliberate decision — CHALLENGE represents elevated risk requiring human
review, not a confirmed fraud prediction.

---

## Metrics Computed

### Confusion Matrix

| | Predicted Fraud | Predicted Not Fraud |
|---|---|---|
| **Actual Fraud** | TP | FN |
| **Actual Not Fraud** | FP | TN |

### Classification Metrics

| Metric | Formula | Meaning |
|--------|---------|---------|
| Precision | TP / (TP + FP) | Of all BLOCKed transactions, how many were real fraud |
| Recall | TP / (TP + FN) | Of all actual fraud cases, how many were caught |
| F1 Score | 2 × (P × R) / (P + R) | Harmonic mean — punishes imbalance between Precision and Recall |
| AUC | Area under ROC curve | Overall separation ability — 0.5 = random, 1.0 = perfect |

### ROC Curve
Plots True Positive Rate vs False Positive Rate across every possible
risk score threshold. Uses the continuous `risk_score` (normalised 0–1),
not the binary BLOCK/APPROVE split — this gives a meaningful curve
rather than a single point.

---

## Phase 5 Results — Rule Engine Baseline

| Metric | Value |
|--------|-------|
| Total Transactions | 1,100 |
| Actual Fraud | 100 |
| Predicted Blocks | 76 |
| TP | 69 |
| FP | 7 |
| FN | 31 |
| TN | 993 |
| Precision | 0.908 |
| Recall | 0.690 |
| F1 Score | 0.784 |
| AUC | 0.8916 |

---

## Key Changes Made During Phase 5

### batch_sim.py — Bulk Query Optimisation
The original implementation made a separate set of database queries per
transaction — 7,000+ network round trips against Render's PostgreSQL in
Oregon. Rewritten to pre-fetch all data in 5 bulk queries, process
entirely in memory, and make zero DB calls inside the scoring loop.

| Original | Rewritten |
|----------|-----------|
| 1 query per transaction | 5 bulk queries total |
| 7,000+ network round trips | 0 DB calls inside scoring loop |
| Alerts written per transaction | No alerts written — evaluation only |

### batch_sim.py — No Alerts Written
Calling `score_transaction()` per transaction during evaluation would
insert 1,100 rows into the live `alerts` table, polluting production
data. `batch_sim.py` replicates scoring logic entirely in memory and
never calls `score_transaction()`.

### risk_engine.py — Score Cap Removed
`min(score, 100)` was removed. Scores are now uncapped — multiple rules
firing simultaneously can push scores above 100. This preserves a
meaningful gradient for the ROC curve while ensuring severe rule
combinations always BLOCK.

### risk_engine.py — HIGH_AMOUNT Tiered Scoring
The original single threshold (`> 1.5x = +25`) was replaced with 5 tiers
to better reflect the risk gradient of extreme transaction amounts.

| Multiplier vs User Average | Old Points | New Points |
|---------------------------|-----------|-----------|
| 1.5x – 2.2x | +25 | +25 |
| 2.2x – 2.9x | +25 | +35 |
| 2.9x – 3.6x | +25 | +50 |
| 3.6x – 4.3x | +25 | +65 |
| 4.3x+ | +25 | +75 |

### risk_engine.py — HIGH_VELOCITY Score Increased
Raised from +15 to +75. More than 3 transactions from the same account
within 10 minutes has no legitimate explanation — auto-BLOCK justified.

### generate_data.py — Legitimate Labels Added
All 1,000 legitimate transactions now receive `is_fraud = 0` labels in
`fraud_labels`. Without this, the left merge in `batch_sim.py` dropped
them as NaN and evaluation only covered the 100 fraud transactions.

### generate_data.py — Fraud Amount Range Fixed
Original fraud generation used `random.uniform(1.6, 2.5)` as a multiplier.
The Random Forest learned fraud only existed up to 2.5× average —
returning near-zero probability on larger amounts. Updated to
`random.uniform(3.0, random.uniform(5.0, 15.0))` to cover realistic
high-amount fraud scenarios.

---

## Dashboard Sections

| Section | Description |
|---------|-------------|
| Summary KPIs | Total transactions, actual fraud count, predicted blocks |
| Decision Distribution | Bar chart — APPROVE / CHALLENGE / BLOCK counts |
| Confusion Matrix | Annotated heatmap — TP, FP, TN, FN |
| Classification Metrics | Colour coded cards — green ≥ 0.70, orange ≥ 0.40, red < 0.40 |
| ROC Curve | AUC plotted against random baseline |
| Model Verdict | Plain English interpretation of AUC score |

---

## Model Verdict Thresholds

| AUC Range | Verdict | Meaning |
|-----------|---------|---------|
| ≥ 0.80 | Good | Strong separation — ready for Phase 6 ML layer |
| ≥ 0.65 | Decent | Reasonable — ML layer needed to close the gap |
| < 0.65 | Poor | Rule thresholds need tuning before Phase 6 |

---

## Key Design Decisions

**Recall is the priority metric** — in fraud detection, false negatives
(missed fraud) are more costly than false positives (blocked legitimate
transactions). Recall of 0.690 reflects 4 intentional Scenario D
slip-throughs and transactions that score in CHALLENGE rather than BLOCK.
The Phase 6 ML layer is designed to close this gap.

**Undetected fraud is intentional** — 4 Scenario D transactions are
designed to look completely normal and slip through the rule engine.
This produces a realistic Recall below 1.0 and avoids overfitting the
engine to the synthetic data.

**Velocity counts use transaction timestamp** — both `HIGH_VELOCITY`
and `STRUCTURING_DETECTED` use the transaction's own timestamp as the
reference point, not `NOW()`. This is critical for synthetic data where
transactions are backdated 90 days.

---

## Dependencies

```
pandas
scikit-learn
plotly
streamlit
psycopg>=3.0
python-dotenv
```