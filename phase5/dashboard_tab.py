"""
phase5/dashboard_tab.py
-----------------------
Streamlit rendering function for the "Phase 5 — Model Evaluation" tab.

Usage inside phase4/app.py:
    from phase5.dashboard_tab import render_phase5_tab

    tab1, tab2, tab3 = st.tabs(["Play Mode", "Alert Log", "Phase 5 — Model Evaluation"])
    with tab3:
        render_phase5_tab()
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.figure_factory as ff


def render_phase5_tab() -> None:

    # ── SECTION: Tab Header ──────────────────────────────────────────
    # Title and description of what this tab does
    st.header("Phase 5 — Model Evaluation")
    st.markdown(
        "Evaluates the **Phase 3 rule-based risk engine** against "
        "ground-truth fraud labels stored in `fraud_labels`. "
        "Click the button below to run the simulation across all 1,000 transactions."
    )

    # ── SECTION: Run Simulation Button ──────────────────────────────
    # User manually triggers the simulation — prevents it auto-running
    # on every Streamlit rerun (tab switch, button click elsewhere, etc.)
    if st.button("▶ Run Batch Simulation", type="primary"):
        with st.spinner("Running simulation across all transactions …"):
            try:
                # Import here to avoid circular imports at module load
                from phase5.batch_sim import run_batch_simulation
                from phase5.metrics import compute_all_metrics

                # Run all 1,000 transactions through the risk engine
                df = run_batch_simulation()

                # Compute all metrics from the resulting DataFrame
                results = compute_all_metrics(df)

                # Store in session_state so results survive Streamlit reruns
                # Without this, the simulation would re-run on every interaction
                st.session_state["phase5_df"]      = df
                st.session_state["phase5_results"] = results

                st.success(f"✅ Simulation complete — {len(df):,} transactions processed.")

            except Exception as e:
                st.error(f"Simulation failed: {e}")
                return

    # ── SECTION: Guard Clause ────────────────────────────────────────
    # If simulation has not been run yet, show info message and stop rendering.
    # Everything below this point only executes after the button has been clicked.
    if "phase5_results" not in st.session_state:
        st.info("Click **Run Batch Simulation** to generate metrics.")
        return

    # Pull results from session_state — no re-computation needed
    df      = st.session_state["phase5_df"]
    results = st.session_state["phase5_results"]

    st.divider()

    # ── SECTION: Summary KPIs ────────────────────────────────────────
    # Three top-level numbers giving a quick overview of the simulation
    # All values derived directly from the DataFrame
    st.subheader("Summary")

    k1, k2, k3 = st.columns(3)

    # len(df)                     — total rows in DataFrame = total transactions
    # df["is_fraud"].sum()        — count of all 1s in is_fraud = actual fraud cases
    # df["predicted_fraud"].sum() — count of all 1s in predicted_fraud = BLOCK decisions
    k1.metric("Total Transactions", f"{len(df):,}")
    k2.metric("Actual Fraud",       f"{df['is_fraud'].sum():,}")
    k3.metric("Predicted Blocks",   f"{df['predicted_fraud'].sum():,}")

    st.divider()

    # ── SECTION: Decision Distribution Bar Chart ─────────────────────
    # Shows how many transactions fell into each decision bucket:
    # APPROVE / CHALLENGE / BLOCK
    st.subheader("Decision Distribution")

    # Count occurrences of each decision and reshape into a clean DataFrame
    decision_counts = df["decision"].value_counts().reset_index()
    decision_counts.columns = ["Decision", "Count"]

    # Colour map — green approve, orange challenge, red block
    color_map = {
        "APPROVE":   "#2ecc71",
        "CHALLENGE": "#f39c12",
        "BLOCK":     "#e74c3c",
    }
    # Get colour per decision — default grey if unexpected value appears
    colors = [color_map.get(d, "#95a5a6") for d in decision_counts["Decision"]]

    # Build bar chart with count labels displayed above each bar
    fig_dist = go.Figure(
        go.Bar(
            x=decision_counts["Decision"],
            y=decision_counts["Count"],
            marker_color=colors,
            text=decision_counts["Count"],
            textposition="outside",
        )
    )

    # Transparent background to match Streamlit dark theme
    fig_dist.update_layout(
        yaxis_title="Count",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=320,
        margin=dict(t=10, b=10),
    )

    st.plotly_chart(fig_dist, use_container_width=True)

    st.divider()

    # ── SECTION: Confusion Matrix Heatmap ───────────────────────────
    # Displays the four classification outcomes as a colour coded 2x2 grid:
    # TN (legit correctly approved) | FP (legit incorrectly blocked)
    # FN (fraud incorrectly approved) | TP (fraud correctly blocked)
    st.subheader("Confusion Matrix")

    # Pull the four values from the results dict computed in metrics.py
    tp = results["TP"]
    fp = results["FP"]
    tn = results["TN"]
    fn = results["FN"]

    # Build the 2x2 grid — rows = Actual label, cols = Predicted label
    z_vals = [[tn, fp], [fn, tp]]
    z_text = [
        [f"TN\n{tn}", f"FP\n{fp}"],
        [f"FN\n{fn}", f"TP\n{tp}"],
    ]

    # Annotated heatmap — darker blue = higher count
    fig_cm = ff.create_annotated_heatmap(
        z=z_vals,
        x=["Predicted: Not Fraud", "Predicted: Fraud"],
        y=["Actual: Not Fraud",    "Actual: Fraud"],
        annotation_text=z_text,
        colorscale="Blues",
        showscale=True,
    )

    fig_cm.update_layout(
        height=320,
        margin=dict(t=10),
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(side="bottom"),
    )

    st.plotly_chart(fig_cm, use_container_width=True)

    st.divider()

    # ── SECTION: Classification Metrics ─────────────────────────────
    # Displays Precision, Recall and F1 as colour coded metric cards
    # Green >= 0.70 (good) | Orange >= 0.40 (decent) | Red < 0.40 (poor)
    st.subheader("Classification Metrics")

    # Pull each metric from the results dict
    precision = results["precision"]
    recall    = results["recall"]
    f1        = results["f1"]

    # Helper — returns a colour based on metric performance band
    def get_color(value: float) -> str:
        if value >= 0.70:
            return "#2ecc71"   # green — good
        elif value >= 0.40:
            return "#f39c12"   # orange — decent
        else:
            return "#e74c3c"   # red — poor

    # Three side by side columns — one card per metric
    m1, m2, m3 = st.columns(3)

    for col, label, value in zip(
        [m1, m2, m3],
        ["Precision", "Recall", "F1 Score"],
        [precision, recall, f1],
    ):
        color = get_color(value)
        # Render styled card with coloured border and faint background tint
        # {color}22 appends hex opacity — makes background a faint tint of the color
        col.markdown(
            f"""
            <div style="text-align:center; padding:12px; border-radius:8px;
                        border:1px solid {color}; background:{color}22;">
                <div style="font-size:0.85rem; color:#888; margin-bottom:4px;">{label}</div>
                <div style="font-size:2rem; font-weight:700; color:{color};">
                    {value:.3f}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Caption explaining each metric in plain English
    st.caption(
        "**Precision** — of all BLOCKed transactions, how many were real fraud. "
        "**Recall** — of all actual fraud cases, how many were caught. "
        "**F1** — harmonic mean of precision and recall — punishes imbalance between the two."
    )

    st.divider()

    # ── SECTION: ROC Curve ───────────────────────────────────────────
    # Plots True Positive Rate (Recall) vs False Positive Rate
    # across every possible risk score threshold from 0 to 100.
    # The diagonal dashed line represents a random classifier (AUC = 0.50).
    # The shaded area under the curve represents the AUC score.
    st.subheader(f"ROC Curve  (AUC = {results['auc']:.4f})")

    # Pull ROC data from results dict
    fpr = results["fpr"]
    tpr = results["tpr"]
    auc = results["auc"]

    fig_roc = go.Figure()

    # Diagonal reference line — random classifier baseline
    fig_roc.add_trace(
        go.Scatter(
            x=[0, 1], y=[0, 1],
            mode="lines",
            line=dict(dash="dash", color="#888", width=1),
            name="Random (AUC = 0.50)",
        )
    )

    # Actual ROC curve — shaded area beneath represents AUC
    fig_roc.add_trace(
        go.Scatter(
            x=fpr,
            y=tpr,
            mode="lines",
            line=dict(color="#3498db", width=2.5),
            name=f"Rule Engine (AUC = {auc:.4f})",
            fill="tozeroy",
            fillcolor="rgba(52,152,219,0.12)",
        )
    )

    fig_roc.update_layout(
        xaxis_title="False Positive Rate",
        yaxis_title="True Positive Rate (Recall)",
        height=400,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, 1], gridcolor="#333"),
        yaxis=dict(range=[0, 1], gridcolor="#333"),
        legend=dict(x=0.6, y=0.1),
        margin=dict(t=10),
    )

    st.plotly_chart(fig_roc, use_container_width=True)

    st.divider()

    # ── SECTION: Model Verdict ───────────────────────────────────────
    # Interprets the AUC score and renders a plain English verdict
    # on overall rule engine performance with colour coded styling
    st.subheader("Model Verdict")

    # Three performance bands — standard ML practice thresholds
    if auc >= 0.80:
        verdict = "Good"
        color   = "#2ecc71"
        comment = (
            "The rule engine is doing a strong job separating fraud from legitimate "
            "transactions. The Phase 6 ML layer should push this even higher."
        )
    elif auc >= 0.65:
        verdict = "Decent"
        color   = "#f39c12"
        comment = (
            "The rule engine has reasonable detection ability but leaves room for "
            "improvement — a strong case for the Phase 6 ML layer to close the gap."
        )
    else:
        verdict = "Poor"
        color   = "#e74c3c"
        comment = (
            "The rule engine is struggling to separate fraud from legitimate transactions. "
            "Consider tuning rule thresholds before moving to Phase 6."
        )

    # Render verdict as a full width styled banner
    st.markdown(
        f"""
        <div style="padding:20px; border-radius:8px;
                    border:1px solid {color}; background:{color}22;
                    text-align:center;">
            <div style="font-size:0.85rem; color:#888; margin-bottom:4px;">Model Verdict</div>
            <div style="font-size:2rem; font-weight:700; color:{color};">
                {verdict} — AUC {auc:.4f}
            </div>
            <div style="font-size:0.95rem; margin-top:8px; color:#ccc;">{comment}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )