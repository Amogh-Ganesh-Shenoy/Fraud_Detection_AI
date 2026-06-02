# Phase 5 — Model Evaluation

## Overview
Phase 5 evaluates the Phase 3 rule-based risk engine against ground-truth
fraud labels. It runs a batch simulation across all 1,100 transactions,
computes a full suite of classification metrics, and renders the results
as an interactive Streamlit tab inside the Phase 4 dashboard.

---

## Files
| File | Purpose |
|------|---------|
| `phase5/batch_sim.py` | Loops all transactions through the risk engine, returns merged DataFrame |
| `phase5/metrics.py` | Computes confusion matrix, Precision, Recall, F1, ROC, AUC |
| `phase5/dashboard_tab.py` | Streamlit tab rendering all metrics and charts |

---

## How to Run

Phase 5 is accessed via the Phase 4 dashboard:

```bash
streamlit run app.py
```

Navigate to the **Phase 5 — Model Evaluation** tab and click
**▶ Run Batch Simulation**.

Results are cached in `st.session_state` — the simulation does not
re-run on every Streamlit interaction.

---

## Binary Classification Mapping

| Engine Decision | Predicted Label |
|----------------|----------------|
| BLOCK | 1 (Fraud) |
| CHALLENGE | 0 (Not Fraud) |
| APPROVE | 0 (Not Fraud) |

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

**Scores are uncapped** — the risk engine removes the `min(score, 100)`
ceiling so that multiple rules firing simultaneously push scores well
above 100. This preserves a meaningful gradient for the ROC curve
while ensuring severe rule combinations always result in BLOCK.

**Legitimate transactions are labelled** — all 1,000 legitimate
transactions have `is_fraud = 0` in `fraud_labels`. Without this,
the left merge in `batch_sim.py` would drop them as NaN and evaluation
would only cover the 100 fraud transactions.

**Undetected fraud is intentional** — 4 Scenario D transactions are
designed to look completely normal and slip through the rule engine.
This produces a realistic Recall below 1.0 and avoids overfitting.

---

## Dependencies
```
pandas
scikit-learn
plotly
streamlit
```