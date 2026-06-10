# api/dependencies.py
# Shared utilities injected into FastAPI endpoints via Depends().
# Centralises DB access and JWT authentication so no endpoint
# handles these concerns directly.

import os
from datetime import datetime, timedelta

# psycopg2 — PostgreSQL driver replacing sqlite3
# Connects to Render's managed PostgreSQL via DATABASE_URL environment variable
import psycopg2
import psycopg2.extras

# FastAPI security and HTTP exception utilities
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# JWT encoding/decoding — requires: pip install python-jose[cryptography]
from jose import JWTError, jwt

from dotenv import load_dotenv

load_dotenv()

# ── Environment variables ─────────────────────────────────────────────────────
# DATABASE_URL points to Render's managed PostgreSQL in production
# Falls back to None locally — local dev still uses SQLite via phase files
DATABASE_URL       = os.getenv("DATABASE_URL")
JWT_SECRET_KEY     = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM      = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", 60))

# Dashboard credentials — loaded from .env, never hardcoded
DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_db():
    """
    Opens and returns a PostgreSQL connection using DATABASE_URL from .env.
    Used as a FastAPI dependency — injected into endpoints via Depends(get_db).
    cursor_factory = RealDictCursor allows column access by name (row["amount"])
    mirroring the sqlite3.Row behaviour from the previous implementation.

    Centralised here so every endpoint shares the same connection logic
    and DATABASE_URL is never duplicated across files.

    Tables accessed across endpoints:
        users, accounts, sessions, transactions,
        behavior_profiles, alerts, fraud_labels
    """
    # Connect to PostgreSQL using the full connection URL from environment
    # RealDictCursor returns rows as dicts instead of tuples
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
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
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode and verify the token — raises JWTError if invalid or expired
        payload  = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")

        if username is None:
            raise credentials_exception

        return username

    except JWTError:
        raise credentials_exception