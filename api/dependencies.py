# api/dependencies.py
# Shared utilities injected into FastAPI endpoints via Depends().
# Centralises DB access and JWT authentication so no endpoint
# handles these concerns directly.

import sqlite3
import os
from datetime import datetime, timedelta

# FastAPI security and HTTP exception utilities
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# JWT encoding/decoding — requires: pip install python-jose[cryptography]
from jose import JWTError, jwt

from dotenv import load_dotenv

load_dotenv()

# ── Environment variables ─────────────────────────────────────────────────────
# All three JWT values come from .env — never hardcode these
# DB_PATH points to the SQLite database built in Phase 1
DB_PATH           = os.getenv("DB_PATH", "data/fraud.db")
JWT_SECRET_KEY    = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM     = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", 60))

# Dashboard credentials — same values used in Phase 4 Streamlit auth gate
DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "fraud2024")


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_db() -> sqlite3.Connection:
    """
    Opens and returns a SQLite connection.
    Used as a FastAPI dependency — injected into endpoints via Depends(get_db).
    row_factory = sqlite3.Row allows column access by name (row["amount"])
    rather than position (row[0]).

    Centralised here so every endpoint shares the same connection logic
    and DB_PATH is never duplicated across files.

    Tables accessed across endpoints:
        users, accounts, sessions, transactions,
        behavior_profiles, alerts, fraud_labels
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# JWT — TOKEN CREATION
# ══════════════════════════════════════════════════════════════════════════════

def create_access_token(data: dict) -> str:
    """
    Creates a signed JWT token containing the provided data payload.
    Called by POST /login after credentials are verified.

    Steps:
        1. Copy the payload dict so we don't mutate the original
        2. Calculate expiry time = now + JWT_EXPIRE_MINUTES
        3. Add expiry to the payload as "exp" — jose reads this automatically
        4. Sign and encode using JWT_SECRET_KEY and JWT_ALGORITHM

    Args:
        data: dict containing the claims to embed (e.g. {"sub": "admin"})

    Returns:
        Signed JWT token string sent back to React on successful login
    """
    payload = data.copy()
    expiry  = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload.update({"exp": expiry})

    # jwt.encode signs the payload — only our server can produce this signature
    # because only we know JWT_SECRET_KEY
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ══════════════════════════════════════════════════════════════════════════════
# JWT — TOKEN VERIFICATION (FastAPI Dependency)
# ══════════════════════════════════════════════════════════════════════════════

# OAuth2PasswordBearer tells FastAPI where to expect the token —
# React sends it in the Authorization header as: Bearer <token>
# tokenUrl is the login endpoint that issues the token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def verify_token(token: str = Depends(oauth2_scheme)) -> str:
    """
    FastAPI dependency — verifies the JWT token on every protected endpoint.
    Injected via Depends(verify_token) in main.py.

    Steps:
        1. Decode the token using JWT_SECRET_KEY
        2. jose automatically checks the "exp" field — raises JWTError if expired
        3. Extract the "sub" (subject) claim — this is the username
        4. Return username if valid, raise 401 if anything fails

    Returns:
        Username string extracted from the token payload

    Raises:
        HTTP 401 Unauthorized if token is missing, expired, or tampered with
        — React intercepts this and redirects the user to the login page
    """
    # Define the 401 response we'll raise on any token failure
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode and verify the token — raises JWTError if invalid or expired
        payload  = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")

        # "sub" must be present — a token without a subject is malformed
        if username is None:
            raise credentials_exception

        return username

    except JWTError:
        # Catches expired tokens, tampered signatures, and malformed tokens
        raise credentials_exception