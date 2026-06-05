# API — FastAPI Backend & JWT Authentication

## Overview
The `api/` layer is the production backend for the UAE Fraud Detection AI.
It exposes 6 HTTP endpoints that the React dashboard calls to retrieve data,
submit transactions, and receive ensemble scoring results. All phase logic
(ingestion, rule engine, ML models) is called from here — the frontend never
touches phase files directly.

---

## Files

| File | Purpose |
|------|---------|
| `api/models.py` | Pydantic request and response models — validates all incoming and outgoing data |
| `api/dependencies.py` | Shared DB connection and JWT authentication helpers |
| `api/main.py` | FastAPI application — all 6 endpoints wired to existing phase logic |

---

## How to Run

```bash
# Start the FastAPI server
uvicorn api.main:app --reload
```

Then open `http://localhost:8000/docs` for the interactive Swagger UI.

> **Note:** The React frontend runs on `localhost:3000`. FastAPI runs on `localhost:8000`.
> CORS is configured in `main.py` to allow cross-origin requests between the two.

---

## Endpoints

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| `POST` | `/login` | ❌ | Validate credentials, return JWT token |
| `GET` | `/users` | ✅ | Return all users for dropdown selector |
| `GET` | `/users/{user_id}/profile` | ✅ | Return behavioral baseline for one user |
| `GET` | `/alerts` | ✅ | Return recent alert history |
| `GET` | `/metrics` | ✅ | Return static model evaluation metrics |
| `POST` | `/session` | ✅ | Create a session, return session_id |
| `POST` | `/score` | ✅ | Run full ensemble, return scoring result |

> All protected endpoints require a valid JWT token in the `Authorization: Bearer <token>` header.

---

## Authentication Flow

```
1. React sends POST /login with username + password
2. FastAPI validates against .env credentials
3. FastAPI returns a signed JWT token (expires in 60 minutes)
4. React attaches token to every subsequent request header
5. FastAPI verifies token on every protected endpoint
6. Invalid or expired token → HTTP 401 → React redirects to login
```

---

## Pydantic Models (`api/models.py`)

| Model | Used By | Purpose |
|-------|---------|---------|
| `Decision` | ScoreRequest, ScoreResponse | Enum restricting decisions to APPROVE / CHALLENGE / BLOCK |
| `ScoreRequest` | `POST /score` | 8 fields from the React play mode form |
| `ScoreResponse` | `POST /score` | Full ensemble result — all 3 model outputs combined |
| `UserSummary` | `GET /users` | user_id, full_name, city for dropdown |
| `UserProfile` | `GET /users/{user_id}/profile` | Behavioral baseline from behavior_profiles table |
| `AlertSummary` | `GET /alerts` | Alert row joined with transaction data |
| `ModelMetrics` | `GET /metrics` | Precision, recall, F1, AUC per model |
| `MetricsResponse` | `GET /metrics` | All 4 models + feature importances |
| `SessionResponse` | `POST /session` | Generated session_id |

---

## POST /score — Data Flow

The core endpoint. Wires all phase files together end to end.

```
React (ScoreRequest)
        ↓
api/main.py → POST /score
        ↓
phase2/ingest.py → ingest_session()      → writes to sessions table
phase2/ingest.py → ingest_transaction()  → writes to transactions table
        ↓
phase6/ensemble.py → ensemble_score()
        ├── phase3/risk_engine.py  → score_transaction()  → writes to alerts table
        ├── phase6/zscore_model.py → score_zscore()
        └── phase6/random_forest_model.py → predict_single()
        ↓
ScoreResponse → React
```

---

## Database Tables Accessed

| Endpoint | Tables |
|----------|--------|
| `GET /users` | `users` |
| `GET /users/{user_id}/profile` | `behavior_profiles` |
| `GET /alerts` | `alerts` JOIN `transactions` |
| `GET /metrics` | None — static values |
| `POST /session` | `sessions` (write) |
| `POST /score` | `accounts`, `sessions` (write), `transactions` (write), `alerts` (write) |

---

## Environment Variables Required

Add these to your `.env` file before running:

```
DB_PATH=data/fraud.db
DASHBOARD_USERNAME=your_username
DASHBOARD_PASSWORD=your_password
JWT_SECRET_KEY=your_generated_secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
```

---

## Dependencies

```
fastapi
uvicorn
pydantic
python-jose[cryptography]
python-multipart
python-dotenv
```

Install with:

```bash
pip install fastapi uvicorn python-jose[cryptography] python-multipart pydantic python-dotenv
```

---

## Notes

- `POST /score` internally creates both a session and a transaction before running
  the ensemble — a separate call to `POST /session` is not required from the frontend.
- `GET /metrics` returns hardcoded evaluation results from Phase 5 and Phase 6 —
  it does not recompute metrics on each call.
- The `alerts` table column is named `timestamp` — renamed from `created_at` in Phase 4.
  All queries in `main.py` use `timestamp`.
- CORS is currently restricted to `localhost:3000` — update `allow_origins` in
  `main.py` before deploying to production.