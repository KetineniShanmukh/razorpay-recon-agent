"""Stage 1: deterministic matching.

Exact match on reference ID + amount (tight tolerance for rounding only) +
date within a narrow window. This is the cheapest, highest-confidence
stage — anything it can't resolve falls through to fuzzy matching.
"""

from datetime import date, datetime

import pandas as pd

AMOUNT_TOLERANCE_RUPEES = 0.01
DATE_WINDOW_DAYS = 1


def _to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()


def match_deterministic(
    payments: list[dict],
    ledger: list[dict],
    amount_tolerance: float = AMOUNT_TOLERANCE_RUPEES,
    date_window_days: int = DATE_WINDOW_DAYS,
) -> list[dict]:
    """Return one candidate match per ledger row with an unambiguous exact match.

    Each result: {"ledger_id", "payment_id", "stage", "confidence", "reason"}.
    Ledger rows with no reference ID, or no exact match, are simply absent
    from the output — the caller decides what happens to them next.
    """
    payments_by_id = {p["payment_id"]: p for p in payments}
    results = []

    for row in ledger:
        ref_id = row.get("reference_id")
        if not ref_id or ref_id not in payments_by_id:
            continue

        payment = payments_by_id[ref_id]
        payment_amount_rupees = payment["amount"] / 100
        payment_date = _to_date(payment["created_at"])
        ledger_date = _to_date(row["date"])

        amount_diff = abs(payment_amount_rupees - row["amount"])
        date_diff_days = abs((ledger_date - payment_date).days)

        if amount_diff <= amount_tolerance and date_diff_days <= date_window_days:
            results.append({
                "ledger_id": row["ledger_id"],
                "payment_id": ref_id,
                "stage": "deterministic",
                "confidence": 1.0,
                "reason": (
                    f"Exact reference ID match, amount diff Rs.{amount_diff:.2f}, "
                    f"date diff {date_diff_days}d"
                ),
            })

    return results
