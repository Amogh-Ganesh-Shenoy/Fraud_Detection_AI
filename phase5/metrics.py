"""
phase5/metrics.py
-----------------
Computes all Phase 5 evaluation metrics from the batch simulation DataFrame.

Takes the DataFrame produced by batch_sim.run_batch_simulation() and returns
a single dict containing all metrics needed by the Streamlit dashboard tab.

Metrics produced:
    Confusion Matrix  : TP, FP, TN, FN
    Classification    : Precision, Recall, F1 Score
    ROC / AUC         : False positive rate, True positive rate, AUC score
"""

import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    roc_curve,
    roc_auc_score,
)


def compute_all_metrics(df: pd.DataFrame) -> dict:

    # ── SECTION: Extract Arrays from DataFrame ───────────────────────
    # y_true  — ground truth labels from fraud_labels table (0 = legit, 1 = fraud)
    # y_pred  — binary predictions from the engine (0 = not BLOCK, 1 = BLOCK)
    # y_score — raw risk score normalised to 0–1 range for ROC curve.
    #           ROC needs a continuous score across all thresholds, not just
    #           the binary BLOCK/APPROVE split, so we use risk_score not y_pred.
    y_true  = df["is_fraud"].values
    y_pred  = df["predicted_fraud"].values
    y_score = df["risk_score"].values / 100.0  # normalise 0–100 → 0–1

    # ── SECTION: Confusion Matrix ────────────────────────────────────
    # Compares y_true vs y_pred and produces a 2x2 matrix:
    #   [[TN, FP],
    #    [FN, TP]]
    # ravel() flattens the 2x2 matrix into a single list so we can
    # unpack the four values directly into named variables.
    # Order is always: tn, fp, fn, tp — matches sklearn convention.
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()

    # ── SECTION: Classification Metrics ─────────────────────────────
    # Precision = TP / (TP + FP)
    #   Of all transactions the engine BLOCKed, how many were real fraud.
    #
    # Recall = TP / (TP + FN)
    #   Of all actual fraud cases, how many did the engine catch.
    #
    # F1 = 2 * (Precision * Recall) / (Precision + Recall)
    #   Harmonic mean — punishes heavily if either precision or recall is poor.
    #
    # zero_division=0 — prevents a crash if the engine produces zero BLOCK
    # decisions (e.g. threshold set too high). Returns 0 instead of ZeroDivisionError.
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall    = recall_score(y_true, y_pred, zero_division=0)
    f1        = f1_score(y_true, y_pred, zero_division=0)

    # ── SECTION: ROC Curve and AUC ───────────────────────────────────
    # roc_curve() slides the decision threshold across all risk score values
    # and computes the True Positive Rate (recall) and False Positive Rate
    # at each threshold. This produces the full ROC curve — not just one point.
    #
    # roc_auc_score() computes the area under that curve as a single number:
    #   1.0 = perfect model
    #   0.5 = random guessing
    #   0.65–0.80 = realistic range for a rule-based engine
    fpr, tpr, thresholds = roc_curve(y_true, y_score)
    auc = roc_auc_score(y_true, y_score)

    # ── SECTION: Return Results Dict ─────────────────────────────────
    # All metrics packed into a single dict for the dashboard tab to consume.
    # Lists are converted with .tolist() so they are JSON serialisable
    # and compatible with Plotly chart inputs.
    # Float values rounded to 4 decimal places for clean display.
    return {
        "TP":        int(tp),
        "FP":        int(fp),
        "TN":        int(tn),
        "FN":        int(fn),
        "precision": round(float(precision), 4),
        "recall":    round(float(recall), 4),
        "f1":        round(float(f1), 4),
        "fpr":       fpr.tolist(),
        "tpr":       tpr.tolist(),
        "auc":       round(float(auc), 4),
    }