"""
UAE Fraud Detection AI — Phase 2
Behavior Profile Tracker
Author: Amogh Ganesh Shenoy

Baseline Protection Layers (designed during security review):
  Layer 1 — Per-transaction cap: limits how much a single transaction
             can shift avg_transaction_amount (max 15% per update)
  Layer 2 — Drift detector: flags and freezes updates when the current
             average has drifted more than 40% from the historical baseline
"""

import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/fraud.db")


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# BASELINE PROTECTION — LAYER 1
# Cap on per-transaction influence
# ══════════════════════════════════════════════════════════════════════════════

def apply_avg_cap(current_avg: float, new_avg: float, max_shift_pct: float = 0.15) -> float:
    """
    Limits how much the average transaction amount can shift in a single
    profile update. Prevents a single small transaction from dragging
    the baseline down significantly.

    Example:
        current_avg = 2000 AED
        new_avg     = 800  AED  (attacker submitted many small transactions)
        max_shift   = 15%  → allowed movement = 300 AED
        capped_avg  = 1700 AED  (not 800)

    Args:
        current_avg:    The existing average in behavior_profiles
        new_avg:        The newly calculated average from all transactions
        max_shift_pct:  Maximum allowed percentage shift per update (default 15%)

    Returns:
        Capped new average — constrained to ±15% of current average
    """
    if current_avg <= 0:
        return new_avg  # No baseline to protect yet

    max_shift = current_avg * max_shift_pct
    delta = new_avg - current_avg

    if abs(delta) > max_shift:
        # Clamp the movement to the allowed range
        direction = 1 if delta > 0 else -1
        return current_avg + (direction * max_shift)

    return new_avg


# ══════════════════════════════════════════════════════════════════════════════
# BASELINE PROTECTION — LAYER 2
# Drift detector
# ══════════════════════════════════════════════════════════════════════════════

def check_baseline_drift(
    user_id: str,
    new_avg: float,
    conn: sqlite3.Connection,
    drift_threshold: float = 0.40,
) -> bool:
    """
    Detects whether the behavioral baseline has drifted too far from its
    historical anchor. If drift exceeds the threshold, the update is
    blocked and a drift alert is logged.

    This defends against slow, patient data poisoning attacks where an
    attacker spaces out transactions to avoid velocity rules but
    gradually shifts the average over days or weeks.

    Drift threshold: 40% (within the 30-50% range agreed during design)
    — Conservative enough to catch meaningful manipulation
    — Permissive enough not to flag legitimate spending changes

    Args:
        user_id:          User whose profile is being updated
        new_avg:          The newly computed average amount
        conn:             Active database connection
        drift_threshold:  Maximum allowed drift fraction (default 0.40 = 40%)

    Returns:
        True  → drift detected, update should be BLOCKED
        False → drift within acceptable range, update is safe
    """
    profile = conn.execute("""
        SELECT avg_transaction_amount, historical_baseline_amount
        FROM behavior_profiles
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    if not profile:
        return False  # No profile yet — nothing to protect

    historical = profile["historical_baseline_amount"]

    # If no historical baseline is stored yet, this is the first update
    if not historical or historical <= 0:
        return False

    # Calculate drift as percentage change from historical baseline
    drift = abs(new_avg - historical) / historical

    if drift > drift_threshold:
        print(
            f"[profile_tracker] ⚠️  DRIFT ALERT — user {user_id[:8]}...\n"
            f"  Historical baseline : AED {historical:,.2f}\n"
            f"  Proposed new avg    : AED {new_avg:,.2f}\n"
            f"  Drift detected      : {drift:.1%}  (threshold: {drift_threshold:.0%})\n"
            f"  Profile update BLOCKED."
        )
        return True  # Block the update

    return False


# ══════════════════════════════════════════════════════════════════════════════
# PROFILE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_profile(user_id: str) -> dict | None:
    """Fetches current profile row for a user — used by Phase 3 risk engine."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM behavior_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


# ══════════════════════════════════════════════════════════════════════════════
# CORE PROFILE RECALCULATION
# ══════════════════════════════════════════════════════════════════════════════

def recalculate_profile(user_id: str) -> None:
    """
    Recalculates one user's behavior profile from all historical transactions
    and sessions. Applies both baseline protection layers before writing.

    Protection flow:
        1. Compute new average from transaction history
        2. Apply per-transaction cap (Layer 1) — limits movement per update
        3. Check drift against historical baseline (Layer 2) — blocks if > 40%
        4. Only write to DB if both layers pass

    Note: This function is called from Phase 4 run_risk_engine() ONLY when
    the decision is not BLOCK. This is the first line of data poisoning
    defence — blocked transactions never influence the profile.

    Args:
        user_id: UUID of the user whose profile to recalculate
    """
    conn = get_db()
    try:
        # ── Fetch all transactions for this user ──────────────────────────────
        transactions = conn.execute("""
            SELECT t.amount, t.location, t.timestamp,
                   s.device_type, s.login_time
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            JOIN sessions s ON t.session_id = s.session_id
            WHERE a.user_id = ?
            ORDER BY t.timestamp DESC
        """, (user_id,)).fetchall()

        if not transactions:
            return

        # ── Fetch current profile for baseline comparison ─────────────────────
        current_profile = conn.execute("""
            SELECT * FROM behavior_profiles WHERE user_id = ?
        """, (user_id,)).fetchone()

        current_avg = (
            current_profile["avg_transaction_amount"]
            if current_profile and current_profile["avg_transaction_amount"]
            else 0
        )

        # ── Compute new baseline values ───────────────────────────────────────
        amounts = [t["amount"] for t in transactions]
        raw_new_avg = sum(amounts) / len(amounts)

        # Count location frequency
        from collections import Counter
        locations = [t["location"] for t in transactions if t["location"]]
        usual_location = Counter(locations).most_common(1)[0][0] if locations else None

        # Count device frequency
        devices = [t["device_type"] for t in transactions if t["device_type"]]
        typical_device = Counter(devices).most_common(1)[0][0] if devices else None

        # Average login hour
        login_hours = []
        for t in transactions:
            try:
                hour = datetime.fromisoformat(t["login_time"]).hour
                login_hours.append(hour)
            except (ValueError, TypeError):
                pass
        typical_login_hour = (
            round(sum(login_hours) / len(login_hours)) if login_hours else None
        )

        # ── LAYER 1: Apply per-transaction cap ────────────────────────────────
        capped_avg = apply_avg_cap(current_avg, raw_new_avg, max_shift_pct=0.15)

        # ── LAYER 2: Check drift against historical baseline ──────────────────
        if check_baseline_drift(user_id, capped_avg, conn, drift_threshold=0.40):
            # Drift detected — freeze the update, do not write to DB
            return

        # ── Write updated profile ─────────────────────────────────────────────
        # On first write: store the initial average as the historical baseline
        # On subsequent writes: preserve the historical baseline unchanged
        historical_baseline = (
            current_profile["historical_baseline_amount"]
            if current_profile and current_profile.get("historical_baseline_amount")
            else capped_avg  # First time — set baseline to this initial average
        )

        conn.execute("""
            UPDATE behavior_profiles
            SET avg_transaction_amount    = ?,
                usual_location            = ?,
                typical_device            = ?,
                typical_login_hour        = ?,
                historical_baseline_amount = ?
            WHERE user_id = ?
        """, (
            capped_avg,
            usual_location,
            typical_device,
            typical_login_hour,
            historical_baseline,
            user_id,
        ))
        conn.commit()

        print(
            f"[profile_tracker] ✓ Profile updated — user {user_id[:8]}...\n"
            f"  Raw avg    : AED {raw_new_avg:,.2f}\n"
            f"  Capped avg : AED {capped_avg:,.2f}\n"
            f"  Historical : AED {historical_baseline:,.2f}"
        )

    except Exception as e:
        print(f"[profile_tracker] Error recalculating profile: {e}")

    finally:
        conn.close()


def recalculate_all_profiles() -> None:
    """
    Loops through all users and recalculates every profile.
    Used by Phase 5 batch simulation after bulk inserts.
    All baseline protection layers still apply per user.
    """
    with get_db() as conn:
        users = conn.execute("SELECT user_id FROM users").fetchall()

    for user in users:
        recalculate_profile(user["user_id"])

    print(f"[profile_tracker] All {len(users)} profiles recalculated.")