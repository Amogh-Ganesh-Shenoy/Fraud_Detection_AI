# Phase 4 — Streamlit Dashboard

## Overview

Phase 4 is the original interactive frontend for the UAE Fraud Detection AI.
It provides a secure, authenticated dashboard with three tabs: interactive
transaction scoring, alert history, and the Phase 5 model evaluation panel.
Built entirely in Streamlit with a custom dark UI theme.

> **Note:** Phase 4 is superseded by the Phase 7 React/Next.js frontend and
> FastAPI backend. `app.py` is no longer called at runtime in production. It
> is preserved in the repository as a working prototype and portfolio reference.
> All production traffic flows through `api/main.py` and the Vercel frontend.

---

## Files

| File | Purpose |
|------|---------|
| `phase4/app.py` | Main Streamlit application — auth, UI, risk engine integration |

---

## How to Run

```bash
# From project root
streamlit run phase4/app.py
```

Default credentials are set via `.env`:

```
DASHBOARD_USERNAME=your_username_here
DASHBOARD_PASSWORD=your_password_here
```

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `DB_PATH` | Path to SQLite database (default: `data/fraud.db`) |
| `DASHBOARD_USERNAME` | Login username |
| `DASHBOARD_PASSWORD` | Login password |
| `SENDGRID_API_KEY` | SendGrid API key for BLOCK email alerts |
| `ALERT_EMAIL` | Recipient email for BLOCK alerts |

---

## Security Features

### Authentication
- SHA-256 password hashing — plaintext is never compared directly
- 5 failed attempt lockout — `st.stop()` is called after the 5th failure
- Credentials loaded from `.env`, never hardcoded

### Rate Limiting
- 10 calls per 60 second window per session
- Exceeding the limit triggers a 30 second block
- Tracked in `st.session_state` — in-memory per session, resets on page refresh
- Defends against data poisoning — stops an attacker flooding the engine to shift behavioral baselines

### Input Sanitisation
- `sanitise_text()` — strips all characters except letters, numbers, spaces, hyphens, dots, commas
- `sanitise_amount()` — enforces float, positive, maximum AED 500,000
- All inputs sanitised before any database query or engine call

### IDOR Protection
- Internal UUIDs are never exposed in the UI
- `fetch_users()` returns display labels only (`Name — City`)
- `resolve_user_id()` maps label back to UUID server-side
- No UUID ever appears in a URL, dropdown value, or rendered text

---

## Dashboard Tabs

### Tab 1 — Interactive Play Mode
Allows manual transaction scoring against any user in the database.

**Flow:**
1. Select user from dropdown — UUID resolved server-side
2. View user's behavioral baseline (avg amount, usual location, typical device, login hour)
3. Enter session details (device type, login location, VPN toggle)
4. Enter transaction details (amount, merchant, location, type)
5. Click Run Fraud Detection
6. View risk score gauge, decision banner, and triggered rule badges
7. BLOCK decision automatically fires SendGrid email alert

### Tab 2 — Alert History
Displays the last 10 alerts from the `alerts` table with colour-coded
decisions (green / amber / red) and transaction details. No raw IDs shown.

### Tab 3 — Phase 5 — Model Evaluation
Renders the full Phase 5 batch simulation results and metrics panel.
Calls `render_phase5_tab()` from `phase5/dashboard_tab.py`.

---

## Risk Engine Integration

```
User submits transaction
        │
        ▼
ingest_session()              ← phase2/ingest.py → sessions table
        │
        ▼
ingest_transaction()          ← phase2/ingest.py → transactions table
        │
        ▼
score_transaction()           ← phase3/risk_engine.py → alerts table
        │
        ▼
decision == BLOCK?
    ┌───┴───┐
   YES      NO
    │        │
Send email   recalculate_profile()   ← phase2/profile_tracker.py
             (data poisoning defence — only updates on safe transactions)
```

**Critical design decision:** `score_transaction()` is called before
`recalculate_profile()`. Blocked transactions never influence the behavioral
baseline. Reversing this order would create a data poisoning vulnerability.

---

## UI Components

| Function | Purpose |
|----------|---------|
| `render_gauge(score)` | Plotly gauge — 0–100 with green/amber/red colour zones |
| `render_decision_banner(decision, score)` | Coloured banner with APPROVE / CHALLENGE / BLOCK and explanation text |
| `render_reason_codes(codes)` | Renders each triggered rule as a styled badge |
| `render_profile_card(profile)` | Displays user's behavioral baseline as metric chips |
| `render_auth_gate()` | Login screen with SHA-256 credential check and attempt lockout |
| `render_interactive_mode(users)` | Full transaction submission form and result display |
| `render_alert_history()` | Styled DataFrame of last 10 alerts with colour-coded decisions |

---

## Email Alerts

SendGrid integration fires on BLOCK decisions only. APPROVE and CHALLENGE
do not trigger emails — this mirrors real UAE banking systems where not every
flag generates an alert.

Alert email contains:
- Transaction amount, merchant, location
- Risk score and decision
- All triggered rule codes
- Timestamp

If `SENDGRID_API_KEY` or `ALERT_EMAIL` are not set, the alert is silently
skipped with an info message — the app does not crash.

---

## UI Theme

Custom dark theme injected via `st.markdown()` CSS:

| Element | Value |
|---------|-------|
| Heading font | Syne (Google Fonts) |
| Data / code font | Share Tech Mono (Google Fonts) |
| Background | `#0a0e1a` (deep navy) |
| Card background | `#0f172a` |
| Border colour | `#1e3a5f` |
| Accent | `#00d4ff` (cyan) |
| APPROVE | `#16a34a` (green) |
| CHALLENGE | `#d97706` (amber) |
| BLOCK | `#dc2626` (red) |

All Streamlit default components are overridden for visual consistency.

---

## Dependencies

```
streamlit
plotly
pandas
python-dotenv
sendgrid
certifi
```

---

## Notes

- `app.py` connects to SQLite via `DB_PATH` — it does not use PostgreSQL.
  This is intentional for local development use. The Phase 7 production
  backend uses PostgreSQL exclusively.
- `profile_tracker.py` (called by `run_risk_engine()`) also targets SQLite —
  both files share the same local-only limitation.
- The `sys.path.insert(0, os.path.abspath("."))` at the top of `app.py` is
  required — Streamlit does not automatically add the project root to the
  Python path. Without it, all `phase2/`, `phase3/`, and `phase5/` imports fail.
- `certifi` is explicitly set via `os.environ["SSL_CERT_FILE"]` to fix SSL
  certificate verification errors that occur on some Windows environments
  when SendGrid makes outbound HTTPS calls.