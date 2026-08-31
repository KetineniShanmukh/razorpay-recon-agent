"""Stage 2: fuzzy matching.

Handles ledger rows stage 1 couldn't resolve: rows with a reference ID that
almost matches (amount/date drifted beyond stage 1's tight tolerance), and
rows with no usable reference ID at all (matched by description + amount +
date proximity instead).
"""

from datetime import date, datetime, timezone

import pandas as pd
from rapidfuzz import fuzz

AMOUNT_TOLERANCE_PCT = 0.06
DATE_WINDOW_DAYS = 5
DESCRIPTION_MATCH_THRESHOLD = 75  # rapidfuzz score (0-100) below which we don't trust it
AMBIGUITY_MARGIN = 5  # if best and second-best candidate scores are this close, don't guess


def _to_date(value) -> date:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()


def _match_by_reference(row, payments_by_id, amount_tolerance_pct, date_window_days):
    """A reference ID is present but stage 1 rejected it — retry with widened tolerance."""
    ref_id = row.get("reference_id")
    if not ref_id or ref_id not in payments_by_id:
        return None

    payment = payments_by_id[ref_id]
    payment_amount = payment["amount"] / 100
    amount_diff = abs(payment_amount - row["amount"])
    amount_diff_pct = amount_diff / payment_amount if payment_amount else 1.0
    date_diff_days = abs((_to_date(row["date"]) - _to_date(payment["created_at"])).days)

    if amount_diff_pct <= amount_tolerance_pct and date_diff_days <= date_window_days:
        confidence = max(round(0.9 - (amount_diff_pct * 2) - (date_diff_days * 0.02), 3), 0.5)
        return {
            "ledger_id": row["ledger_id"],
            "payment_id": ref_id,
            "stage": "fuzzy_reference_tolerance",
            "confidence": confidence,
            "reason": (
                f"Reference ID matches; amount off by {amount_diff_pct:.1%}, "
                f"date off by {date_diff_days}d (within widened tolerance)"
            ),
        }
    return None


def _match_by_description(row, candidate_payments, amount_tolerance_pct, date_window_days):
    """No usable reference ID — search by amount/date proximity, disambiguate by description."""
    row_date = _to_date(row["date"])
    scored = []
    for payment in candidate_payments:
        payment_amount = payment["amount"] / 100
        amount_diff_pct = abs(payment_amount - row["amount"]) / payment_amount if payment_amount else 1.0
        date_diff_days = abs((row_date - _to_date(payment["created_at"])).days)
        if amount_diff_pct > amount_tolerance_pct or date_diff_days > date_window_days:
            continue
        score = fuzz.token_sort_ratio(row.get("description", ""), payment.get("description", ""))
        scored.append((score, amount_diff_pct, date_diff_days, payment))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_amount_pct, best_date_days, best_payment = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0

    if best_score < DESCRIPTION_MATCH_THRESHOLD:
        return None
    if len(scored) > 1 and (best_score - second_score) < AMBIGUITY_MARGIN:
        return None  # too ambiguous to call automatically — leave for stage 3 / exception review

    confidence = round((best_score / 100) * 0.85, 3)
    return {
        "ledger_id": row["ledger_id"],
        "payment_id": best_payment["id"],
        "stage": "fuzzy_description",
        "confidence": confidence,
        "reason": (
            f"No usable reference ID; matched by description similarity "
            f"({best_score:.0f}/100), amount off {best_amount_pct:.1%}, date off {best_date_days}d"
        ),
    }


def match_fuzzy(
    unresolved_ledger: list[dict],
    available_payments: list[dict],
    amount_tolerance_pct: float = AMOUNT_TOLERANCE_PCT,
    date_window_days: int = DATE_WINDOW_DAYS,
) -> list[dict]:
    """Attempt to resolve ledger rows stage 1 left unmatched.

    `available_payments` should exclude payments stage 1 already claimed.
    """
    payments_by_id = {p["id"]: p for p in available_payments}
    results = []

    for row in unresolved_ledger:
        match = _match_by_reference(row, payments_by_id, amount_tolerance_pct, date_window_days)
        if match is None:
            match = _match_by_description(row, available_payments, amount_tolerance_pct, date_window_days)
        if match is not None:
            results.append(match)

    return results
