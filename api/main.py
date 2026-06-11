# api/main.py
# FastAPI application — all endpoints for the Phase 7 backend.
# React never calls phase files directly; all data flows through these endpoints.
# Build order: read-only endpoints first, then session/score last.

import uuid
from datetime import datetime
from typing import Optional



from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

# api/models.py — Pydantic request and response models for all endpoints
from api.models import (
    ScoreRequest, ScoreResponse,
    UserSummary, UserProfile,
    AlertSummary, MetricsResponse, ModelMetrics,
    SessionResponse, Decision,
)

# api/dependencies.py — shared DB connection and JWT auth helpers
from api.dependencies import (
    get_db,
    create_access_token,
    verify_token,
    DASHBOARD_USERNAME,
    DASHBOARD_PASSWORD,
)

# phase2/ingest.py — ingest_session() and ingest_transaction() for POST /session and POST /score
from phase2.ingest import ingest_session, ingest_transaction

# phase6/ensemble.py — ensemble_score() orchestrates all 3 models for POST /score
from phase6.ensemble import ensemble_score


# ══════════════════════════════════════════════════════════════════════════════
# APP INITIALISATION
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="UAE Fraud Detection AI",
    description="Phase 7 — FastAPI backend serving the React dashboard",
    version="7.0.0",
)

# ── CORS Middleware ───────────────────────────────────────────────────────────
# Allows the React frontend (localhost:3000 and Vercel) to call this API.
# Without this, the browser blocks cross-origin requests by default.
# allow_credentials=True is required for JWT token headers to be accepted.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://fraud-detection-ai-six.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# POST /login — Auth Gate
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Validates dashboard credentials from .env and returns a signed JWT token.
    React stores this token and attaches it to every subsequent API call.
    Credentials are compared against DASHBOARD_USERNAME and DASHBOARD_PASSWORD
    from api/dependencies.py, which reads them from the .env file.
    """
    # Compare submitted credentials against .env values
    if form_data.username != DASHBOARD_USERNAME or form_data.password != DASHBOARD_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create and return a signed JWT token — React attaches this to all requests
    token = create_access_token(data={"sub": form_data.username})
    return {"access_token": token, "token_type": "bearer"}


# ══════════════════════════════════════════════════════════════════════════════
# GET /users — User Dropdown
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/users", response_model=list[UserSummary])
def get_users(
    db=Depends(get_db),
    _: str = Depends(verify_token),
):
    """
    Returns all users for the dropdown selector in the React play mode form.
    Pulls user_id, full_name, city from the users table (Phase 1 schema).
    Protected — requires valid JWT token.
    """
    # RealDictCursor returns rows as dicts — no conversion needed unlike sqlite3.Row
    # Source: users table, populated by Phase 1 generate_users()
    cur = db.cursor()
    cur.execute("""
        SELECT user_id, full_name, city
        FROM users
        ORDER BY full_name ASC
    """)
    rows = cur.fetchall()
    db.close()

    return list(rows)


# ══════════════════════════════════════════════════════════════════════════════
# GET /users/{user_id}/profile — Behavioral Baseline
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/users/{user_id}/profile", response_model=UserProfile)
def get_user_profile(
    user_id: str,
    db=Depends(get_db),
    _: str = Depends(verify_token),
):
    """
    Returns the behavioral baseline for a single user for the ProfileCard component.
    Pulls avg_transaction_amount, usual_location, typical_device, typical_login_hour
    from behavior_profiles table (built by Phase 1 generate_behavior_profiles()).
    Protected — requires valid JWT token.
    """
    # %s replaces ? for PostgreSQL parameter binding — functionally identical
    # Source: behavior_profiles table, keyed by user_id
    cur = db.cursor()
    cur.execute("""
        SELECT avg_transaction_amount, usual_location,
               typical_device, typical_login_hour
        FROM behavior_profiles
        WHERE user_id = %s
    """, (user_id,))
    row = cur.fetchone()
    db.close()

    # Return 404 if no profile exists for this user
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No behavior profile found for user {user_id}."
        )

    return dict(row)


# ══════════════════════════════════════════════════════════════════════════════
# GET /alerts — Alert History Table
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/alerts", response_model=list[AlertSummary])
def get_alerts(
    limit: int = 10,
    db=Depends(get_db),
    _: str = Depends(verify_token),
):
    """
    Returns recent alert history for the AlertTable component in React.
    JOINs alerts + transactions to include amount, merchant, and location
    alongside risk_score, decision, reason_codes, and timestamp.

    Tables:
        alerts       — alert_id, transaction_id, risk_score, decision,
                       reason_codes, timestamp
        transactions — amount, merchant, location

    Query param: limit (default 10) — number of most recent alerts to return.
    Protected — requires valid JWT token.
    """
    # LIMIT %s instead of LIMIT ? — PostgreSQL parameter binding syntax
    # Source: alerts JOIN transactions, ordered by most recent first
    cur = db.cursor()
    cur.execute("""
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
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    db.close()

    return list(rows)


# ══════════════════════════════════════════════════════════════════════════════
# GET /metrics — Model Evaluation Metrics
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/metrics", response_model=MetricsResponse)
def get_metrics(_: str = Depends(verify_token)):
    """
    Returns static Phase 5 and Phase 6 evaluation metrics for the
    MetricsPanel and FeatureBar components in React.
    No DB query needed — these are the final validated results from
    Phase 5 batch simulation and Phase 6 model evaluation.
    Protected — requires valid JWT token.
    """
    return {
        # Phase 5 rule engine baseline — from phase5 batch simulation
        "phase5": {
            "precision": 0.9412,
            "recall":    0.8,
            "f1":        0.8649,
            "auc":       0.8916,
        },
        # Z-Score standalone performance — from phase6/zscore_model.py evaluate_zscore()
        "zscore": {
            "precision": 0.75,
            "recall":    0.18,
            "f1":        0.2903,
            "auc":       None,
        },
        # Random Forest test set performance — from phase6/random_forest_model.py
        "random_forest": {
            "precision": 1.0,
            "recall":    1.0,
            "f1":        1.0,
            "auc":       1.0,
        },
        # Ensemble full DB performance — from phase6/ensemble.py evaluate_ensemble()
        "ensemble": {
            "precision": 1.0,
            "recall":    0.8,
            "f1":        0.8889,
            "auc":       None,
        },
        # Feature importances from Random Forest — phase6/random_forest_model.py
        "feature_importances": {
            "velocity_count":          0.5422,
            "amount_ratio":            0.2582,
            "unusual_login_location":  0.0998,
            "vpn_flag":                0.0522,
            "hour_deviation":          0.0183,
            "unusual_txn_location":    0.0128,
            "login_txn_mismatch":      0.0111,
            "new_device_flag":         0.0054,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# POST /session — Create Session
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/session", response_model=SessionResponse)
def create_session(
    user_id: str,
    device_type: str,
    location: str,
    vpn_detected: bool = False,
    _: str = Depends(verify_token),
):
    """
    Creates a new session and returns the generated session_id.
    Called by React before POST /score to obtain a valid session_id.

    Calls: phase2/ingest.py → ingest_session()
    Writes to: sessions table
        session_id, user_id, ip_address, device_type,
        location, vpn_detected, login_time

    React passes the returned session_id into the POST /score request body.
    Protected — requires valid JWT token.
    """
    # Generate a placeholder IP — real IP detection can be added later
    # ingest_session() writes the session to PostgreSQL and returns session_id
    session_id = ingest_session(
        user_id=user_id,
        ip_address="0.0.0.0",
        device_type=device_type,
        location=location,
        vpn_detected=int(vpn_detected),
    )

    return {"session_id": session_id}


# ══════════════════════════════════════════════════════════════════════════════
# POST /score — Full Ensemble Scoring
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/score", response_model=ScoreResponse)
def score_transaction_endpoint(
    payload: ScoreRequest,
    db=Depends(get_db),
    _: str = Depends(verify_token),
):
    """
    Runs the full ensemble for a single transaction and returns the combined result.
    This is the core endpoint — wires together all phase files end to end.

    Flow:
        1. Fetch account_id for this user from accounts table
        2. Create session via phase2/ingest.py → ingest_session()
        3. Create transaction via phase2/ingest.py → ingest_transaction()
        4. Run full ensemble via phase6/ensemble.py → ensemble_score()
        5. Return combined result to React

    Writes to:
        sessions table     — via ingest_session()
        transactions table — via ingest_transaction()
        alerts table       — via phase3/risk_engine.py inside ensemble_score()

    Protected — requires valid JWT token.
    """

    # ── Step 1: Fetch account_id for this user ────────────────────────────────
    # ingest_transaction() requires account_id, not user_id directly.
    # accounts table links user_id → account_id (Phase 1 schema).
    # %s replaces ? for PostgreSQL parameter binding
    cur = db.cursor()
    cur.execute("""
        SELECT account_id FROM accounts WHERE user_id = %s
    """, (payload.user_id,))
    account = cur.fetchone()
    db.close()

    if not account:
        raise HTTPException(
            status_code=404,
            detail=f"No account found for user {payload.user_id}."
        )

    account_id = account["account_id"]

    # ── Step 2: Create session ────────────────────────────────────────────────
    # Calls phase2/ingest.py → ingest_session()
    # Writes to sessions table and returns session_id
    session_id = ingest_session(
        user_id=payload.user_id,
        ip_address="0.0.0.0",
        device_type=payload.device_type,
        location=payload.login_location,
        vpn_detected=int(payload.vpn_detected),
    )

    # ── Step 3: Create transaction ────────────────────────────────────────────
    # Calls phase2/ingest.py → ingest_transaction()
    # Writes to transactions table and returns transaction_id
    transaction_id = ingest_transaction(
        account_id=account_id,
        session_id=session_id,
        amount=payload.amount,
        merchant=payload.merchant,
        transaction_type=payload.transaction_type,
        location=payload.location,
    )

    # ── Step 4: Run full ensemble ─────────────────────────────────────────────
    # Calls phase6/ensemble.py → ensemble_score()
    # Internally calls phase3/risk_engine.py, phase6/zscore_model.py,
    # phase6/random_forest_model.py and writes alert to alerts table
    result = ensemble_score(
        transaction_id=transaction_id,
        session_id=session_id,
        user_id=payload.user_id,
    )

    if not result:
        raise HTTPException(
            status_code=500,
            detail="Ensemble scoring failed. Check phase logs for details."
        )

    # ── Step 5: Map ensemble result to ScoreResponse ──────────────────────────
    # ensemble_score() returns rule_decision as a string — we map it to
    # the Decision enum so Pydantic validates it matches APPROVE/CHALLENGE/BLOCK
    return ScoreResponse(
        transaction_id=transaction_id,
        risk_score=result["risk_score"],
        rule_decision=Decision(result["rule_decision"]),
        anomaly_score=result["anomaly_score"],
        is_anomaly=result["is_anomaly"],
        fraud_probability=result["fraud_probability"],
        ensemble_score=result["ensemble_score"],
        final_decision=Decision(result["final_decision"]),
        reason_codes=result["reason_codes"],
        norm_rule=result["norm_rule"],
        norm_zscore=result["norm_zscore"],
        norm_rf=result["norm_rf"],
        weights=result["weights"],
    )