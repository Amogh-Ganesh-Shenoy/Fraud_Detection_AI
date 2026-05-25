# Phase 4 — Streamlit Dashboard & Interactive Play Mode

## Overview
A secure, interactive web dashboard for real-time transaction fraud scoring.
Integrates Phase 2 (event ingestion), Phase 3 (risk engine), and SendGrid
email alerts into a single production-grade UI.

## Run
```powershell
# From project root: Fraud_Detection_AI/
streamlit run phase4/app.py
```

## Files
- `app.py` — full dashboard application

---

## Security Layers

| Layer | Implementation |
|-------|---------------|
| **Auth gate** | SHA-256 password hash comparison. 5 failed attempts triggers `st.stop()` |
| **Rate limiter** | 10 calls per 60 seconds per session. 30 second block on breach |
| **Input sanitisation** | `sanitise_text()` strips dangerous characters. `sanitise_amount()` enforces float, max AED 500,000 |
| **IDOR protection** | `fetch_users()` returns display labels only. `resolve_user_id()` maps label to UUID server-side — UUIDs never exposed in UI |
| **Data poisoning defence** | `recalculate_profile()` only called when decision != BLOCK |
| **SSL fix** | `certifi` CA bundle explicitly set at runtime to resolve Python SSL misconfiguration on Windows |

---

## Key Functions

| Function | Description |
|----------|-------------|
| `check_rate_limit()` | Enforces 10 calls/60s per session, 30s block on breach |
| `sanitise_text()` | Strips dangerous characters from string inputs |
| `sanitise_amount()` | Validates AED amount — positive float, max 500,000 |
| `check_credentials()` | SHA-256 hash comparison for login |
| `fetch_users()` | Returns display-safe user labels — UUIDs server-side only |
| `resolve_user_id()` | Maps display label back to UUID |
| `fetch_account_id()` | Fetches account UUID for a given user |
| `fetch_user_profile()` | Fetches behavioral baseline for display |
| `fetch_recent_alerts()` | Last 10 alerts — display-safe columns only |
| `run_risk_engine()` | Orchestrates Phase 2 ingest + Phase 3 scoring + profile update |
| `send_block_alert()` | SendGrid email — fires on BLOCK only, gracefully skips if unconfigured |
| `render_gauge()` | Plotly gauge — colour-coded 0-100 risk score display |
| `render_decision_banner()` | APPROVE / CHALLENGE / BLOCK result banner |
| `render_reason_codes()` | Triggered rule badges |
| `render_profile_card()` | User behavioral baseline metric chips |
| `render_interactive_mode()` | Full interactive transaction simulation UI |
| `render_alert_history()` | Paginated alert history table with decision colouring |

---

## UI Sections

| Tab | Description |
|-----|-------------|
| **Interactive Play Mode** | Select a user, enter session and transaction details, run fraud detection and see live results |
| **Alert History** | Last 10 scored transactions with risk score, decision, triggered rules, amount, merchant |

---

## Environment Variables Required

| Variable | Description |
|----------|-------------|
| `DB_PATH` | Path to SQLite database |
| `DASHBOARD_USERNAME` | Login username |
| `DASHBOARD_PASSWORD` | Login password |
| `SENDGRID_API_KEY` | SendGrid API key for email alerts |
| `ALERT_EMAIL` | Recipient email for BLOCK alerts |

---

## Bugs Fixed in This Phase
- `applymap()` → `map()` in pandas Styler for newer pandas versions
- `created_at` → `timestamp` in all alert queries
- `sys.path.insert` moved to top of file before all imports
- SSL certificate verification fixed via certifi CA bundle
- SendGrid sender verified — from address must match SendGrid verified sender

---

## Known Limitations
- Login location currently requires manual entry — future phases should derive this from session IP
- `use_container_width` deprecation warnings — will be updated to `width='stretch'` in future