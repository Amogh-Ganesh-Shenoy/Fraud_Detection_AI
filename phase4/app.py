"""
UAE Fraud Detection AI — Phase 4
Streamlit Dashboard with Interactive Play Mode
Author: Amogh Ganesh Shenoy
Security: Auth gate, input sanitisation, rate limiting, IDOR protection
"""
import sys
import os
sys.path.insert(0, os.path.abspath("."))
import re
import time
import sqlite3
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
import certifi

from phase5.dashboard_tab import render_phase5_tab

import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv()

DB_PATH          = os.getenv("DB_PATH", "data/fraud.db")
DASHBOARD_USER   = os.getenv("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASS   = os.getenv("DASHBOARD_PASSWORD", "fraud2024")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
ALERT_EMAIL      = os.getenv("ALERT_EMAIL", "")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UAE Fraud Detection AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Syne:wght@400;600;700;800&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
    background-color: #0a0e1a;
    color: #e2e8f0;
}

/* ── Header ── */
.fraud-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
    border: 1px solid #1e3a5f;
    border-radius: 12px;
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}
.fraud-header::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #00d4ff, #0066ff, transparent);
}
.fraud-header h1 {
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    margin: 0;
    color: #f8fafc;
}
.fraud-header .subtitle {
    font-family: 'Share Tech Mono', monospace;
    color: #00d4ff;
    font-size: 0.8rem;
    margin-top: 0.4rem;
    letter-spacing: 0.12em;
}

/* ── Cards ── */
.card {
    background: #0f172a;
    border: 1px solid #1e3a5f;
    border-radius: 10px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.card-title {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    color: #64748b;
    text-transform: uppercase;
    margin-bottom: 1rem;
    font-family: 'Share Tech Mono', monospace;
}

/* ── Decision banners ── */
.decision-approve {
    background: linear-gradient(135deg, #052e16, #14532d);
    border: 1px solid #16a34a;
    border-radius: 10px;
    padding: 1.5rem 2rem;
    text-align: center;
}
.decision-challenge {
    background: linear-gradient(135deg, #1c1400, #3d2800);
    border: 1px solid #d97706;
    border-radius: 10px;
    padding: 1.5rem 2rem;
    text-align: center;
}
.decision-block {
    background: linear-gradient(135deg, #1c0000, #3d0000);
    border: 1px solid #dc2626;
    border-radius: 10px;
    padding: 1.5rem 2rem;
    text-align: center;
}
.decision-text {
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    margin: 0;
}
.decision-sub {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.75rem;
    letter-spacing: 0.1em;
    margin-top: 0.5rem;
    opacity: 0.8;
}

/* ── Reason badges ── */
.badge-container { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.75rem; }
.badge {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.7rem;
    padding: 0.3rem 0.75rem;
    border-radius: 4px;
    border: 1px solid #dc2626;
    background: rgba(220,38,38,0.1);
    color: #fca5a5;
    letter-spacing: 0.05em;
}

/* ── Score display ── */
.score-number {
    font-family: 'Share Tech Mono', monospace;
    font-size: 3.5rem;
    font-weight: 700;
    text-align: center;
    line-height: 1;
}
.score-label {
    font-size: 0.65rem;
    letter-spacing: 0.2em;
    text-align: center;
    color: #64748b;
    margin-top: 0.3rem;
    font-family: 'Share Tech Mono', monospace;
}

/* ── Auth ── */
.auth-container {
    max-width: 420px;
    margin: 6rem auto;
    background: #0f172a;
    border: 1px solid #1e3a5f;
    border-radius: 12px;
    padding: 2.5rem;
}
.auth-logo {
    text-align: center;
    font-size: 3rem;
    margin-bottom: 1rem;
}
.auth-title {
    text-align: center;
    font-size: 1.3rem;
    font-weight: 800;
    color: #f8fafc;
    margin-bottom: 0.25rem;
}
.auth-sub {
    text-align: center;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.7rem;
    color: #00d4ff;
    letter-spacing: 0.12em;
    margin-bottom: 2rem;
}

/* ── Metric chips ── */
.metric-row { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
.metric-chip {
    flex: 1;
    min-width: 120px;
    background: #0f172a;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
}
.metric-chip .val {
    font-family: 'Share Tech Mono', monospace;
    font-size: 1.4rem;
    font-weight: 700;
    color: #00d4ff;
}
.metric-chip .lbl {
    font-size: 0.6rem;
    letter-spacing: 0.15em;
    color: #64748b;
    text-transform: uppercase;
    margin-top: 0.2rem;
}

/* ── Streamlit overrides ── */
.stButton > button {
    background: linear-gradient(135deg, #0066ff, #00d4ff);
    color: #0a0e1a;
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    border: none;
    border-radius: 6px;
    padding: 0.6rem 1.5rem;
    letter-spacing: 0.05em;
    width: 100%;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85; }
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div {
    background: #0f172a !important;
    border: 1px solid #1e3a5f !important;
    color: #e2e8f0 !important;
    border-radius: 6px !important;
    font-family: 'Share Tech Mono', monospace !important;
}
div[data-testid="stDataFrame"] { border: 1px solid #1e3a5f; border-radius: 8px; overflow: hidden; }
.stAlert { border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECURITY LAYER
# ══════════════════════════════════════════════════════════════════════════════

# ── Rate limiter (in-memory per session) ─────────────────────────────────────
if "rate_limit" not in st.session_state:
    st.session_state.rate_limit = {"calls": [], "blocked_until": None}

def check_rate_limit(max_calls: int = 10, window_seconds: int = 60) -> bool:
    """Returns True if call is allowed, False if rate limit exceeded."""
    rl = st.session_state.rate_limit
    now = datetime.now()

    # Check if currently in a block window
    if rl["blocked_until"] and now < rl["blocked_until"]:
        remaining = int((rl["blocked_until"] - now).total_seconds())
        st.error(f"⛔ Rate limit exceeded. Please wait {remaining}s before retrying.")
        return False

    # Purge calls outside the window
    rl["calls"] = [t for t in rl["calls"] if now - t < timedelta(seconds=window_seconds)]

    if len(rl["calls"]) >= max_calls:
        rl["blocked_until"] = now + timedelta(seconds=30)
        st.error("⛔ Too many requests. You are blocked for 30 seconds.")
        return False

    rl["calls"].append(now)
    return True


# ── Input sanitisation ────────────────────────────────────────────────────────
def sanitise_text(value: str, field_name: str = "field") -> str | None:
    """Strip dangerous characters. Allow letters, numbers, spaces, hyphens, dots."""
    if not value or not value.strip():
        st.warning(f"⚠️ {field_name} cannot be empty.")
        return None
    cleaned = re.sub(r"[^a-zA-Z0-9\s\-\.\,]", "", value.strip())
    if len(cleaned) < 2:
        st.warning(f"⚠️ {field_name} contains invalid characters or is too short.")
        return None
    if len(cleaned) > 100:
        st.warning(f"⚠️ {field_name} exceeds maximum length.")
        return None
    return cleaned


def sanitise_amount(value: float) -> float | None:
    """Validate AED amount — must be positive, numeric, under AED 500,000."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        st.warning("⚠️ Amount must be a numeric value.")
        return None
    if amount <= 0:
        st.warning("⚠️ Amount must be greater than 0.")
        return None
    if amount > 500_000:
        st.warning("⚠️ Amount exceeds the maximum allowed limit of AED 500,000.")
        return None
    return round(amount, 2)


# ── Password check (hashed comparison) ───────────────────────────────────────
def check_credentials(username: str, password: str) -> bool:
    entered_hash = hashlib.sha256(password.encode()).hexdigest()
    stored_hash  = hashlib.sha256(DASHBOARD_PASS.encode()).hexdigest()
    return username == DASHBOARD_USER and entered_hash == stored_hash


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE HELPERS  (server-side ID resolution — IDOR protection)
# ══════════════════════════════════════════════════════════════════════════════

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_users() -> list[dict]:
    """Return display-safe list: name + internal user_id. IDs never shown in UI."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT user_id, full_name, city FROM users ORDER BY full_name"
        ).fetchall()
    return [{"label": f"{r['full_name']} — {r['city']}", "user_id": r["user_id"]} for r in rows]


def resolve_user_id(display_label: str, users: list[dict]) -> str | None:
    """Resolve display label back to internal UUID. Never exposes UUID in UI."""
    for u in users:
        if u["label"] == display_label:
            return u["user_id"]
    return None


def fetch_account_id(user_id: str) -> str | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT account_id FROM accounts WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row["account_id"] if row else None


def fetch_user_profile(user_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM behavior_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def fetch_recent_alerts(limit: int = 10) -> list[dict]:
    """Fetch last N alerts — display safe columns only, no raw IDs shown."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                a.risk_score,
                a.decision,
                a.reason_codes,
                a.timestamp,
                t.amount,
                t.merchant,
                t.location
            FROM alerts a
            JOIN transactions t ON a.transaction_id = t.transaction_id
            ORDER BY a.timestamp DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# RISK ENGINE INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

def run_risk_engine(account_id: str, session_id: str,
                    amount: float, merchant: str,
                    transaction_type: str, location: str,
                    user_id: str) -> dict | None:
    """
    Calls Phase 2 ingest + Phase 3 risk engine.
    Profile only updates if decision != BLOCK (data poisoning defence).
    """
    try:
        

        from phase2.ingest import ingest_transaction
        from phase3.risk_engine import score_transaction

        # Ingest transaction
        transaction_id = ingest_transaction(
            account_id=account_id,
            session_id=session_id,
            amount=amount,
            merchant=merchant,
            transaction_type=transaction_type,
            location=location,
        )

        # Score FIRST
        result = score_transaction(transaction_id, session_id)

        # Only update profile if NOT blocked (data poisoning defence)
        if result and result.get("decision") != "BLOCK":
            from phase2.profile_tracker import recalculate_profile
            recalculate_profile(user_id)

        return result

    except Exception as e:
        st.error(f"Risk engine error: {e}")
        st.exception(e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL ALERT (SendGrid)
# ══════════════════════════════════════════════════════════════════════════════

def send_block_alert(result: dict) -> None:
    # Force Python to use certifi's CA bundle for SSL verification
    os.environ["SSL_CERT_FILE"] = certifi.where()
    print("SENDGRID KEY:", os.getenv("SENDGRID_API_KEY", "NOT FOUND"))
    """Fire SendGrid email on BLOCK decisions only."""
    if not SENDGRID_API_KEY or not ALERT_EMAIL:
        st.info("ℹ️ SendGrid not configured — email alert skipped.")
        return
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        body = f"""
FRAUD ALERT — TRANSACTION BLOCKED

Amount:     AED {result['amount']:,.2f}
Merchant:   {result['merchant']}
Location:   {result['location']}
Risk Score: {result['risk_score']} / 100
Decision:   {result['decision']}
Reasons:    {', '.join(result['reason_codes'])}
Time:       {result['timestamp']}
        """.strip()

        message = Mail(
            from_email="moghly.shenoy@gmail.com",
            to_emails=ALERT_EMAIL,
            subject="🚨 FRAUD BLOCK ALERT — UAE Fraud Detection AI",
            plain_text_content=body,
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        st.success("📧 Block alert email sent successfully.")
    except Exception as e:
        st.warning(f"Email alert failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════

def render_gauge(score: int) -> None:
    """Plotly gauge — 0-100 with colour zones."""
    if score <= 30:
        bar_color = "#16a34a"
    elif score <= 70:
        bar_color = "#d97706"
    else:
        bar_color = "#dc2626"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        gauge={
            "axis": {
                "range": [0, 100],
                "tickwidth": 1,
                "tickcolor": "#334155",
                "tickfont": {"color": "#64748b", "size": 10},
            },
            "bar": {"color": bar_color, "thickness": 0.25},
            "bgcolor": "#0f172a",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 30],  "color": "rgba(22,163,74,0.12)"},
                {"range": [30, 70], "color": "rgba(217,119,6,0.12)"},
                {"range": [70, 100],"color": "rgba(220,38,38,0.12)"},
            ],
            "threshold": {
                "line": {"color": bar_color, "width": 3},
                "thickness": 0.8,
                "value": score,
            },
        },
        number={"font": {"color": bar_color, "size": 48, "family": "Share Tech Mono"}},
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#e2e8f0"},
        height=220,
        margin=dict(t=20, b=0, l=20, r=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_decision_banner(decision: str, score: int) -> None:
    messages = {
        "APPROVE":   ("✅ APPROVED",   "#16a34a", "Transaction cleared — risk within acceptable range.", "decision-approve"),
        "CHALLENGE": ("⚠️ CHALLENGE",  "#d97706", "Elevated risk — OTP or security question required.",  "decision-challenge"),
        "BLOCK":     ("🚫 BLOCKED",    "#dc2626", "High fraud risk — transaction has been stopped.",      "decision-block"),
    }
    label, color, sub, css_class = messages.get(decision, messages["APPROVE"])
    st.markdown(f"""
        <div class="{css_class}">
            <p class="decision-text" style="color:{color}">{label}</p>
            <p class="decision-sub" style="color:{color}">{sub}</p>
        </div>
    """, unsafe_allow_html=True)


def render_reason_codes(codes: list[str]) -> None:
    if not codes:
        st.markdown('<p style="color:#64748b;font-size:0.8rem;">No risk rules triggered.</p>', unsafe_allow_html=True)
        return
    badges = "".join(f'<span class="badge">{c}</span>' for c in codes)
    st.markdown(f'<div class="badge-container">{badges}</div>', unsafe_allow_html=True)


def render_profile_card(profile: dict) -> None:
    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-chip">
            <div class="val">AED {profile.get('avg_transaction_amount', 0):,.0f}</div>
            <div class="lbl">Avg Amount</div>
        </div>
        <div class="metric-chip">
            <div class="val">{profile.get('usual_location', 'N/A')}</div>
            <div class="lbl">Usual Location</div>
        </div>
        <div class="metric-chip">
            <div class="val">{profile.get('typical_device', 'N/A')}</div>
            <div class="lbl">Typical Device</div>
        </div>
        <div class="metric-chip">
            <div class="val">{int(profile.get('typical_login_hour', 0)):02d}:00</div>
            <div class="lbl">Usual Login Hour</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# AUTH GATE
# ══════════════════════════════════════════════════════════════════════════════

def render_auth_gate() -> None:
    st.markdown("""
        <div class="auth-container">
            <div class="auth-logo">🛡️</div>
            <div class="auth-title">UAE Fraud Detection AI</div>
            <div class="auth-sub">SECURE ACCESS · AUTHORISED PERSONNEL ONLY</div>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        if st.button("Access Dashboard"):
            if check_credentials(username, password):
                st.session_state.authenticated = True
                st.session_state.auth_attempts = 0
                st.rerun()
            else:
                st.session_state.auth_attempts = st.session_state.get("auth_attempts", 0) + 1
                attempts = st.session_state.auth_attempts
                if attempts >= 5:
                    st.error("⛔ Too many failed attempts. Refresh to try again.")
                    st.stop()
                else:
                    st.error(f"❌ Invalid credentials. Attempt {attempts}/5.")


# ══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE PLAY MODE
# ══════════════════════════════════════════════════════════════════════════════

def render_interactive_mode(users: list[dict]) -> None:
    st.markdown('<div class="card-title">▸ SELECT USER</div>', unsafe_allow_html=True)

    user_labels = [u["label"] for u in users]
    selected_label = st.selectbox("User", user_labels, label_visibility="collapsed")
    user_id = resolve_user_id(selected_label, users)

    if not user_id:
        st.error("Could not resolve user. Please refresh.")
        st.exception(e)
        return

    # Profile card
    profile = fetch_user_profile(user_id)
    if profile:
        st.markdown('<div class="card-title" style="margin-top:1.5rem">▸ BEHAVIORAL BASELINE</div>', unsafe_allow_html=True)
        render_profile_card(profile)

    st.markdown("---")
    st.markdown('<div class="card-title">▸ SESSION DETAILS</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        device_type   = st.selectbox("Device Type", ["mobile", "desktop", "tablet"])
        login_location = st.text_input("Login Location", placeholder="e.g. Dubai")
    with col2:
        vpn_detected  = st.toggle("VPN Detected", value=False)

    st.markdown('<div class="card-title" style="margin-top:1.5rem">▸ TRANSACTION DETAILS</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        amount_input  = st.number_input("Amount (AED)", min_value=0.0, max_value=500000.0, value=500.0, step=50.0)
        merchant_input = st.text_input("Merchant", placeholder="e.g. Carrefour Dubai")
    with col4:
        txn_location  = st.text_input("Transaction Location", placeholder="e.g. Abu Dhabi")
        txn_type      = st.selectbox("Transaction Type", ["purchase", "transfer", "withdrawal", "online"])

    st.markdown("<br>", unsafe_allow_html=True)
    run_button = st.button("🔍 Run Fraud Detection")

    if run_button:
        
        # ── Rate limit check ──────────────────────────────────────────────
        if not check_rate_limit(max_calls=10, window_seconds=60):
            return

        # ── Input sanitisation ────────────────────────────────────────────
        amount   = sanitise_amount(amount_input)
        merchant = sanitise_text(merchant_input, "Merchant")
        loc      = sanitise_text(txn_location, "Transaction Location")
        login_loc = sanitise_text(login_location, "Login Location")

        if not all([amount, merchant, loc, login_loc]):
            return  # Warnings already shown by sanitisers

        
        # ── Ingest session ────────────────────────────────────────────────
        try:
            from phase2.ingest import ingest_session, get_account_by_user
            session_id = ingest_session(
                user_id=user_id,
                ip_address="127.0.0.1",
                device_type=device_type,
                location=login_loc,
                vpn_detected=vpn_detected,
            )
           
            account_row = get_account_by_user(user_id)
            if not account_row:
                st.error("No account found for this user.")
                return
            account_id = account_row[0]
        except Exception as e:
            st.error(f"Session ingestion failed: {e}")
            return

        # ── Run engine ────────────────────────────────────────────────────
        with st.spinner("Analysing transaction..."):
            result = run_risk_engine(
                account_id=account_id,
                session_id=session_id,
                amount=amount,
                merchant=merchant,
                transaction_type=txn_type,
                location=loc,
                user_id=user_id,
            )
        
        if not result:
            return

        # ── Render results ────────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div class="card-title">▸ RISK ASSESSMENT RESULT</div>', unsafe_allow_html=True)

        r_col1, r_col2 = st.columns([1, 2])

        with r_col1:
            render_gauge(result["risk_score"])
            st.markdown(f'<p class="score-label">RISK SCORE / 100</p>', unsafe_allow_html=True)

        with r_col2:
            render_decision_banner(result["decision"], result["risk_score"])
            st.markdown('<div class="card-title" style="margin-top:1.5rem">▸ TRIGGERED RULES</div>', unsafe_allow_html=True)
            render_reason_codes(result.get("reason_codes", []))

            # Detail chips
            st.markdown(f"""
            <div class="metric-row" style="margin-top:1rem">
                <div class="metric-chip"><div class="val">AED {result['amount']:,.0f}</div><div class="lbl">Amount</div></div>
                <div class="metric-chip"><div class="val">{result['merchant']}</div><div class="lbl">Merchant</div></div>
                <div class="metric-chip"><div class="val">{result['location']}</div><div class="lbl">Location</div></div>
                <div class="metric-chip"><div class="val">{'YES' if result['vpn'] else 'NO'}</div><div class="lbl">VPN</div></div>
            </div>
            """, unsafe_allow_html=True)

        # ── Email alert on BLOCK ──────────────────────────────────────────
        if result["decision"] == "BLOCK":
            send_block_alert(result)

        st.session_state["last_result"] = result


# ══════════════════════════════════════════════════════════════════════════════
# ALERT HISTORY TABLE
# ══════════════════════════════════════════════════════════════════════════════

def render_alert_history() -> None:
    st.markdown('<div class="card-title">▸ RECENT ALERT HISTORY</div>', unsafe_allow_html=True)
    alerts = fetch_recent_alerts(10)
    if not alerts:
        st.info("No alerts recorded yet.")
        return

    import pandas as pd

    def colour_decision(val):
        colours = {"APPROVE": "#16a34a", "CHALLENGE": "#d97706", "BLOCK": "#dc2626"}
        c = colours.get(val, "#64748b")
        return f"color: {c}; font-weight: 700"

    df = pd.DataFrame(alerts)
    df = df.rename(columns={
        "risk_score": "Score",
        "decision": "Decision",
        "reason_codes": "Reasons",
        "timestamp": "Time",
        "amount": "Amount (AED)",
        "merchant": "Merchant",
        "location": "Location",
    })
    df["Amount (AED)"] = df["Amount (AED)"].apply(lambda x: f"{x:,.2f}")
    df["Time"] = pd.to_datetime(df["Time"], format="mixed").dt.strftime("%d %b %H:%M")

    styled = df.style.map(colour_decision, subset=["Decision"])

    st.dataframe(styled, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # ── Session state init ────────────────────────────────────────────────────
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "auth_attempts" not in st.session_state:
        st.session_state.auth_attempts = 0

    # ── Auth gate ─────────────────────────────────────────────────────────────
    if not st.session_state.authenticated:
        render_auth_gate()
        return

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
        <div class="fraud-header">
            <h1>🛡️ UAE Fraud Detection AI</h1>
            <div class="subtitle">REAL-TIME TRANSACTION RISK SCORING · RULE-BASED ENGINE · PHASE 4</div>
        </div>
    """, unsafe_allow_html=True)

    # ── Logout ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🛡️ UAE Fraud AI")
        st.markdown("---")
        st.markdown(f"**Logged in as:** `{DASHBOARD_USER}`")
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.rerun()
        st.markdown("---")
        st.markdown("**Rate Limit Status**")
        calls_made = len(st.session_state.rate_limit.get("calls", []))
        st.progress(calls_made / 10, text=f"{calls_made}/10 calls (60s window)")

    # ── Load users ────────────────────────────────────────────────────────────
    try:
        users = fetch_users()
    except Exception as e:
        st.error(f"Could not connect to database: {e}")
        st.stop()

    if not users:
        st.warning("No users found in database. Run Phase 1 scripts first.")
        st.stop()

    # ── Mode tabs ─────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["🎮 Interactive Play Mode", "📋 Alert History", "📊 Phase 5 — Model Evaluation"])

    with tab1:
        render_interactive_mode(users)

    with tab2:
        render_alert_history()
    
    with tab3:
        render_phase5_tab()

if __name__ == "__main__":
    main()