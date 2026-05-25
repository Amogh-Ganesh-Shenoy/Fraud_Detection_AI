"""
UAE Fraud Detection AI — Phase 3
Location Risk Scorer
Author: Amogh Ganesh Shenoy

Sub-features:
  1. UNUSUAL_LOGIN_LOCATION        +5  — login city ≠ usual location
  2. UNUSUAL_TRANSACTION_LOCATION  +5  — transaction city ≠ usual location
  3. LOGIN_TRANSACTION_MISMATCH    +5  — login city ≠ transaction city
  Maximum combined: +15
"""

from datetime import datetime


# ══════════════════════════════════════════════════════════════════════════════
# MAIN LOCATION RISK SCORER
# ══════════════════════════════════════════════════════════════════════════════

def score_location_risk(
    login_city: str,
    txn_city: str,
    usual_city: str,
) -> tuple[int, list[str]]:
    """
    Runs 3 location sub-features and returns a combined
    location risk score and list of triggered reason codes.

    Args:
        login_city:   City from session login
        txn_city:     City of the transaction merchant
        usual_city:   User's usual location from behavior profile

    Returns:
        (score, reason_codes) tuple
        score is 0-15, reason_codes is a list of triggered rule names
    """
    score = 0
    reason_codes = []

    # ── Sub-feature 1: UNUSUAL_LOGIN_LOCATION ────────────────────────────────
    if usual_city and login_city:
        if login_city.strip().lower() != usual_city.strip().lower():
            score += 5
            reason_codes.append("UNUSUAL_LOGIN_LOCATION")

    # ── Sub-feature 2: UNUSUAL_TRANSACTION_LOCATION ─────────────────────────
    if usual_city and txn_city:
        if txn_city.strip().lower() != usual_city.strip().lower():
            score += 5
            reason_codes.append("UNUSUAL_TRANSACTION_LOCATION")

    # ── Sub-feature 3: LOGIN_TRANSACTION_MISMATCH ────────────────────────────
    if login_city and txn_city:
        if login_city.strip().lower() != txn_city.strip().lower():
            score += 5
            reason_codes.append("LOGIN_TRANSACTION_MISMATCH")

    return score, reason_codes