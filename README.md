# Fraud_Detection_AI# Phase 7 — FastAPI Backend & React Frontend

## Overview

Phase 7 is the production web layer of the UAE Fraud Detection AI. It replaces
the Phase 4 Streamlit dashboard with a FastAPI REST API backend and a
React/Next.js frontend, deployed to Render and Vercel respectively.

The backend wraps all phase logic (Phases 2–6) behind typed REST endpoints.
The React frontend consumes these endpoints and renders the full dashboard —
interactive scoring, alert history, model metrics, and feature importances.

---

## Live Deployment

| Layer | Platform | URL |
|-------|----------|-----|
| Frontend | Vercel | https://fraud-detection-ai-six.vercel.app |
| Backend | Render | https://fraud-detection-ai-oqy9.onrender.com |
| Database | Render PostgreSQL | Internal URL via `DATABASE_URL` env var |

---

## Files

### Backend

| File | Purpose |
|------|---------|
| `api/main.py` | All 7 FastAPI endpoints |
| `api/dependencies.py` | PostgreSQL connection, JWT token creation and verification |
| `api/models.py` | Pydantic request/response models — validated at the API boundary |
| `migrate.py` | One-time SQLite → PostgreSQL migration script — keep, do not delete |

### Frontend

| File | Purpose |
|------|---------|
| `frontend/app/page.tsx` | Login page — auth gate at `/` |
| `frontend/app/dashboard/page.tsx` | Main dashboard — Score and Analytics tabs |
| `frontend/app/layout.tsx` | Root layout — fonts and body wrapper |
| `frontend/components/ScoreForm.tsx` | Transaction simulator form — calls POST /score |
| `frontend/components/ResultCard.tsx` | Full ensemble result breakdown |
| `frontend/components/GaugeChart.tsx` | Semicircle gauge — ensemble_score visualisation |
| `frontend/components/AlertTable.tsx` | Recent alert history table |
| `frontend/components/MetricsPanel.tsx` | Model performance comparison table |
| `frontend/components/FeatureBar.tsx` | Random Forest feature importance bar chart |
| `frontend/components/ProfileCard.tsx` | User behavioral baseline display |
| `frontend/lib/api.ts` | Centralised API client — all fetch() calls |
| `frontend/types/index.ts` | TypeScript interfaces mirroring Pydantic models |

---

## How to Run Locally

```bash
# Terminal 1 — FastAPI backend (from project root)
uvicorn api.main:app --reload

# Terminal 2 — React frontend
cd frontend
npm run dev
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Swagger UI: `http://localhost:8000/docs`

---

## Architecture

```
React/Next.js (Vercel)
        │
        │ HTTPS + JWT (Authorization: Bearer <token>)
        ▼
FastAPI (Render — Python 3.14, uvicorn, $PORT)
        │
        ├── POST /login        → JWT auth
        ├── GET  /users        → users table
        ├── GET  /users/{id}/profile → behavior_profiles table
        ├── GET  /alerts       → alerts JOIN transactions
        ├── GET  /metrics      → static hardcoded evaluation metrics
        ├── POST /session      → phase2/ingest.py → sessions table
        └── POST /score        → phase2/ingest.py → transactions + sessions
                               → phase3/risk_engine.py → alerts table
                               → phase6/zscore_model.py
                               → phase6/random_forest_model.py (loads random_forest.pkl)
                               → phase6/ensemble.py → combined result
        │
        ▼
Render PostgreSQL
(7 tables: users, accounts, sessions, transactions,
 behavior_profiles, alerts, fraud_labels)
```

**Critical principle:** React never imports Python modules directly.
All data flows through FastAPI endpoints. This is the key architectural
difference from Phase 4 where Streamlit called Python functions in the
same process.

---

## API Endpoints

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| `POST` | `/login` | No | Validates credentials, returns JWT token |
| `GET` | `/users` | Yes | All users for dropdown selector |
| `GET` | `/users/{user_id}/profile` | Yes | Behavioral baseline for ProfileCard |
| `GET` | `/alerts` | Yes | Recent alert history for AlertTable |
| `GET` | `/metrics` | Yes | Static model evaluation metrics |
| `POST` | `/session` | Yes | Creates session, returns session_id |
| `POST` | `/score` | Yes | Full ensemble — ingests, scores, returns result |

All protected endpoints require `Authorization: Bearer <token>` header.
React attaches this automatically via `apiFetch()` in `frontend/lib/api.ts`.

---

## POST /score — Full Data Flow

```
ScoreForm submits transaction
        │
        ▼
POST /score (api/main.py)
        │
        ├── Fetch account_id from accounts table
        ├── ingest_session()      → writes to sessions table
        ├── ingest_transaction()  → writes to transactions table
        └── ensemble_score()
                │
                ├── score_transaction()   → phase3/risk_engine.py
                │                           writes alert to alerts table
                ├── score_zscore()        → phase6/zscore_model.py
                └── predict_single()      → phase6/random_forest_model.py
                                            loads random_forest.pkl
        │
        ▼
ScoreResponse → ResultCard + GaugeChart
```

---

## Authentication

JWT tokens are issued by `POST /login` and verified on every protected endpoint.

| Component | Detail |
|-----------|--------|
| Library | `python-jose[cryptography]` |
| Algorithm | HS256 |
| Expiry | 60 minutes (configurable via `JWT_EXPIRE_MINUTES`) |
| Storage | React `localStorage` via `saveToken()` in `lib/api.ts` |
| Header | `Authorization: Bearer <token>` |
| Verification | `verify_token()` in `api/dependencies.py` via `Depends()` |

On 401 responses, `clearToken()` is called automatically and the user
is redirected to the login page.

---

## Frontend Components

### ScoreForm
- Fetches users from `GET /users` on mount
- Fetches behavioral profile from `GET /users/{id}/profile` when user changes
- Submits `ScoreRequest` to `POST /score`
- Passes `ScoreResponse` up to dashboard via `onResult()` callback
- Device type dropdown uses exact values from `behavior_profiles.typical_device`
  — any divergence causes `NEW_DEVICE` to fire on every transaction

### ResultCard
- Pure display — receives `ScoreResponse` from dashboard state
- Shows ensemble score, all three sub-scores (rule engine, RF, Z-Score)
- Renders reason codes as badges
- Shows model contribution breakdown with progress bars

### GaugeChart
- Renders a Recharts `RadialBarChart` semicircle
- Score displayed as percentage of 0.0–1.0 ensemble score
- Colour changes with decision: green / yellow / red
- Threshold markers at 0.30 (APPROVE→CHALLENGE) and 0.45 (CHALLENGE→BLOCK)

### AlertTable
- Fetches `GET /alerts` on mount — self-contained
- `reason_codes` arrives as a comma-space string from the `alerts` table
  and is split into individual badges by the component

### MetricsPanel
- Fetches `GET /metrics` on mount — self-contained
- Displays all 4 models: Phase 5 Rule Engine, Z-Score, Random Forest, Ensemble
- RF and Ensemble rows highlighted as best performers

### FeatureBar
- Pure display — receives `feature_importances` from dashboard state
- Horizontal Recharts `BarChart` sorted highest → lowest importance
- Colour-coded by contribution tier: dominant / moderate / minor

### ProfileCard
- Pure display — receives `UserProfile` prop
- Shows avg transaction amount, usual location, typical device, login hour
- Inline note explains which rule is triggered by deviations from baseline

---

## Pydantic Models (api/models.py)

| Model | Endpoint | Direction |
|-------|----------|-----------|
| `ScoreRequest` | POST /score | Request |
| `ScoreResponse` | POST /score | Response |
| `UserSummary` | GET /users | Response |
| `UserProfile` | GET /users/{id}/profile | Response |
| `AlertSummary` | GET /alerts | Response |
| `ModelMetrics` | GET /metrics (nested) | Response |
| `MetricsResponse` | GET /metrics | Response |
| `SessionResponse` | POST /session | Response |
| `Decision` | ScoreRequest/Response | Enum |

TypeScript interfaces in `frontend/types/index.ts` mirror these exactly.
Any change to a Pydantic model must be reflected in the TypeScript types
to keep the frontend in sync.

---

## GET /metrics — Static Values

`GET /metrics` returns hardcoded values from the last offline evaluation run.
No recomputation happens at runtime. After retraining or re-evaluating:

1. Run `python -m phase5.batch_sim` for rule engine metrics
2. Run `python -m phase6.random_forest_model` for RF metrics
3. Run `python -m phase6.ensemble` for ensemble metrics
4. Update the hardcoded values in `api/main.py → get_metrics()`
5. Redeploy to Render

---

## migrate.py — SQLite to PostgreSQL

One-time migration script used to port the SQLite database built across
Phases 1–6 to Render's managed PostgreSQL. Keep this file — do not delete.

- Creates all 7 tables in PostgreSQL using `IF NOT EXISTS`
- Copies all rows using `ON CONFLICT DO NOTHING` — safe to re-run
- Must use the **External** PostgreSQL URL when run locally
- Uses `psycopg2` (not psycopg3) — only needed for this one-time script

```bash
# Run once from project root with external DATABASE_URL in .env
python migrate.py
```

---

## Environment Variables

### Render Web Service

| Key | Notes |
|-----|-------|
| `DATABASE_URL` | Internal PostgreSQL URL from Render DB dashboard |
| `DASHBOARD_USERNAME` | Admin login username |
| `DASHBOARD_PASSWORD` | Admin login password |
| `JWT_SECRET_KEY` | Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ALGORITHM` | `HS256` |
| `JWT_EXPIRE_MINUTES` | `60` |
| `SENDGRID_API_KEY` | For BLOCK decision email alerts |
| `ALERT_EMAIL` | Recipient for BLOCK alerts |
| `DB_PATH` | `data/fraud.db` — legacy, unused at runtime |

### Vercel

| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_API_URL` | `https://fraud-detection-ai-oqy9.onrender.com` |

### Local `.env`
Same as Render plus `DATABASE_URL` set to the **External** PostgreSQL URL.

---

## Key Changes Made During Phase 7

### psycopg2 → psycopg3 Migration
Render defaults to Python 3.14. `psycopg2-binary`'s C extension is
incompatible with Python 3.14's ABI. `psycopg3` (`psycopg[binary]==3.2.13`)
ships native 3.14 wheels. All six database-connected runtime files were
updated — import syntax changed from
`psycopg2.connect(..., cursor_factory=RealDictCursor)` to
`psycopg.connect(..., row_factory=dict_row)`.

### float() Casts on PostgreSQL NUMERIC Columns
PostgreSQL returns `NUMERIC` columns as Python `decimal.Decimal`. Python
disallows `decimal.Decimal * float` arithmetic. All database-sourced numeric
values used in arithmetic are wrapped with `float()` before use.

### Bulk Query Optimisation for Batch Evaluation
Offline evaluation originally made 7,000+ network round trips to Render's
PostgreSQL. All evaluation functions were rewritten to pre-fetch all data
in 5 bulk queries, process in memory, and run a single batch
`predict_proba()` call. Zero DB calls occur inside evaluation loops.

### Batch Evaluation Does Not Write Alerts
Calling `score_transaction()` per transaction in evaluation would insert
1,100 rows into the live `alerts` table. Evaluation functions replicate
scoring logic in memory and never call `score_transaction()`.

### Git History Scrubbed
`git filter-repo` was used to rewrite all 20 commits and remove hardcoded
credentials (`x`, `y`) from history. Force-pushed to GitHub.
`.env.example` added with placeholder values for developer reference.

### CORS Updated for Vercel
`api/main.py` CORS middleware updated to allow both `http://localhost:3000`
and `https://fraud-detection-ai-six.vercel.app`. If the Vercel URL changes,
CORS must be updated and Render redeployed.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend framework | Next.js 15 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS |
| Charts | Recharts |
| Icons | lucide-react |
| Backend | FastAPI, Uvicorn, Python 3.14 (Render) |
| Auth | JWT via python-jose |
| Database | PostgreSQL via psycopg3 |
| ML | scikit-learn, pandas, numpy |
| Email | SendGrid (BLOCK decisions only) |
| Frontend hosting | Vercel |
| Backend hosting | Render |

---

## Dependencies

### Backend (`requirements.txt`)

```
fastapi
uvicorn
python-jose[cryptography]
python-multipart
pydantic
python-dotenv
sendgrid
certifi
scikit-learn
pandas
numpy
passlib
cryptography
psycopg[binary]
```

### Frontend

```
next
react
typescript
tailwindcss
recharts
lucide-react
```

---

## Notes

- `ProfileCard` is imported in `dashboard/page.tsx` but profile state was
  removed from the dashboard — `ScoreForm` displays the baseline inline.
  `ProfileCard` remains available as a standalone component if needed.
- `reason_codes` is `string[]` from `POST /score` but a comma-space `string`
  from `GET /alerts` — both cases are handled in their respective components.
- `random_forest.pkl` (320KB) is committed to GitHub and deploys with the
  codebase — no retraining occurs on Render at runtime.
- Swagger UI at `/docs` is enabled in production — disable by setting
  `docs_url=None` in `FastAPI()` after deployment is verified.
- `profile_tracker.py` (Phase 2) still targets SQLite and is not functional
  in production. Behavioral baselines do not update at runtime on Render.