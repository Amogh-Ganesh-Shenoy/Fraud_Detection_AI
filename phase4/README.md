# Phase 4 — Streamlit Dashboard

## Overview
Phase 4 is the interactive front-end for the UAE Fraud Detection AI. It provides
a secure, authenticated dashboard with three tabs: interactive transaction scoring,
alert history, and the Phase 5 model evaluation panel. Built entirely in Streamlit
with a custom dark UI theme.

---

## Files
| File | Purpose |
|------|---------|
| `app.py` | Main Streamlit application — auth, UI, risk engine integration |

---

## How to Run

```bash
streamlit run app.py
```

Default credentials (set via `.env`):

DASHBOARD_USERNAME=your_username_here
DASHBOARD_PASSWORD=your_password_here

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `DB_PATH` | Path to SQLite database (default: `data/fraud.db`) |
| `DASHBOARD_USERNAME` | Login username |
| `DASHBOARD_PASSWORD` | Login password |
| `SENDGRID_API_KEY` | SendGrid API key for email alerts |
| `ALERT_EMAIL` | Recipient email for BLOCK alerts |

---

## Security Features

### Authentication
- SHA-256 password hashing — plaintext never compared directly
- 5 failed attempt lockout before session is blocked
- Session state managed via `st.session_state`

### Rate Limiting
- 10 calls per 60 second window per session
- Exceeding limit triggers a 30 second block
- In-memory per session — resets on page refresh

### Input Sanitisation
- All text fields stripped of dangerous characters
- Allowed: letters, numbers, spaces, hyphens, dots
- Amount validated: must be positive, numeric, under AED 500,000

### IDOR Protection
- Internal UUIDs never exposed in the UI
- User selection via display label only
- Server-side UUID resolution before any database query

---

## Dashboard Tabs

### Tab 1 — Interactive Play Mode
Allows manual transaction scoring against any user in the database.

**Flow:**
1. Select user from dropdown
2. View user's behavioral baseline (avg amount, location, device, login hour)
3. Enter session details (device, location, VPN toggle)
4. Enter transaction details (amount, merchant, location, type)
5. Run fraud detection — see risk score gauge, decision banner, triggered rules

### Tab 2 — Alert History
Displays the last 10 alerts from the `alerts` table with colour-coded
decisions (green/amber/red) and transaction details.

### Tab 3 — Phase 5 Model Evaluation
Renders the full Phase 5 batch simulation and metrics panel.
See Phase 5 README for details.

---

## Risk Engine Integration

User submits transaction
│
▼
ingest_session()         ← Phase 2
│
▼
ingest_transaction()     ← Phase 2
│
▼
score_transaction()      ← Phase 3
│
▼
decision == BLOCK?
┌────┴────┐
YES       NO
│         │
Send      recalculate_profile()  ← Phase 2
email     (data poisoning defence)

---

## Email Alerts
SendGrid integration fires on BLOCK decisions only. Alert email contains:
- Transaction amount, merchant, location
- Risk score and decision
- All triggered rule codes
- Timestamp

If `SENDGRID_API_KEY` or `ALERT_EMAIL` are not set, the alert is silently
skipped with an info message.

---

## UI Theme
Custom dark theme built with injected CSS:
- Font: Syne (headings) + Share Tech Mono (data/code)
- Colour palette: navy backgrounds, cyan accents, red/amber/green decisions
- All Streamlit default components overridden for consistency

---

## Dependencies
streamlit
plotly
pandas
python-dotenv
sendgrid
certifi

