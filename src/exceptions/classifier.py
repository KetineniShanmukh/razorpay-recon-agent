"""Exception classifier.

Every ledger row the matching engine couldn't resolve gets tagged with WHY,
not just left as a bare "unresolved" — this is one of the buildathon's
explicitly required deliverables, not an optional extra. Core categories
match the brief's named exception types: amount mismatch, missing
counterpart, likely duplicate, currency/fee delta. Two bonus categories
(`date_drift`, `ambiguous_match`) give more precise, still-honest labels for
cases that don't neatly fit those four — `ambiguous_match` in particular is
exactly the kind of case stage 3 (LLM-assisted resolution) exists to help
with.

This module re-derives near-miss information the matching stages don't keep
around (they only report accepted matches, not close-but-rejected
candidates) — it's intentionally independent logic, not a reuse of the
matching internals, since "why didn't this match" is a different question
from "does this match."
"""

from datetime import date, datetime, timezone

import pandas as pd
from rapidfuzz import fuzz

from src.matching.fuzzy import DATE_WINDOW_DAYS

NEGLIGIBLE_AMOUNT_DIFF_PCT = 0.001  # float-rounding noise, not a real mismatch
FEE_DELTA_TOLERANCE_PCT = 0.01      # how close amount-diff must be to fee+tax to call it a fee delta
NEAR_MISS_DESCRIPTION_THRESHOLD = 50  # below this, don't even suggest a "closest candidate"
AMBIGUITY_MARGIN = 5


def _to_date(value) -> date:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()


def _classify_by_reference(ledger_row: dict, payment: dict) -> dict:
    """Reference ID points at a real payment, but it wasn't a confident enough match."""
    payment_amount = payment["amount"] / 100
    amount_diff = payment_amount - ledger_row["amount"]
    amount_diff_pct = abs(amount_diff) / payment_amount if payment_amount else 1.0
    date_diff_days = abs((_to_date(ledger_row["date"]) - _to_date(payment["created_at"])).days)

    fee_plus_tax = (payment.get("fee", 0) + payment.get("tax", 0)) / 100
    looks_like_fee_delta = (
        fee_plus_tax > 0
        and abs(abs(amount_diff) - fee_plus_tax) / fee_plus_tax <= FEE_DELTA_TOLERANCE_PCT
    )
    has_amount_issue = amount_diff_pct > NEGLIGIBLE_AMOUNT_DIFF_PCT
    has_date_issue = date_diff_days > DATE_WINDOW_DAYS

    if looks_like_fee_delta:
        return {
            "exception_type": "currency_fee_delta",
            "explanation": (
                f"Reference ID matches payment {payment['id']}, but the ledger amount is short by "
                f"Rs.{abs(amount_diff):.2f} - almost exactly that payment's fee+tax "
                f"(Rs.{fee_plus_tax:.2f}). Looks like the ledger recorded a net-of-fee amount."
            ),
        }
    if has_amount_issue and has_date_issue:
        return {
            "exception_type": "amount_mismatch",
            "explanation": (
                f"Reference ID matches payment {payment['id']}, but amount is off by "
                f"{amount_diff_pct:.1%} (Rs.{abs(amount_diff):.2f}) AND date is off by "
                f"{date_diff_days} days - too far on both axes to auto-resolve."
            ),
        }
    if has_amount_issue:
        return {
            "exception_type": "amount_mismatch",
            "explanation": (
                f"Reference ID matches payment {payment['id']}, but amount differs by "
                f"{amount_diff_pct:.1%} (Rs.{abs(amount_diff):.2f}) - beyond auto-match tolerance."
            ),
        }
    return {
        "exception_type": "date_drift",
        "explanation": (
            f"Reference ID matches payment {payment['id']}, amount checks out, but date is off "
            f"by {date_diff_days} days - beyond the {DATE_WINDOW_DAYS}-day auto-match window."
        ),
    }


def _classify_without_reference(ledger_row: dict, all_payments: list[dict]) -> dict:
    """No usable reference ID — explain the best near-miss, if any."""
    row_date = _to_date(ledger_row["date"])
    scored = []
    for payment in all_payments:
        payment_amount = payment["amount"] / 100
        amount_diff_pct = abs(payment_amount - ledger_row["amount"]) / payment_amount if payment_amount else 1.0
        date_diff_days = abs((row_date - _to_date(payment["created_at"])).days)
        score = fuzz.token_sort_ratio(ledger_row.get("description", ""), payment.get("description", ""))
        scored.append((score, amount_diff_pct, date_diff_days, payment))
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored or scored[0][0] < NEAR_MISS_DESCRIPTION_THRESHOLD:
        row_desc = ledger_row.get("description") or "(no description)"
        return {
            "exception_type": "missing_counterpart",
            "explanation": (
                f"No reference ID. Ledger shows Rs.{ledger_row['amount']:.2f} on {ledger_row['date']} "
                f"for \"{row_desc}\", but no payment in the dataset has a similar description, "
                f"amount, or date within tolerance."
            ),
        }

    best_score, best_amount_pct, best_date_days, best_payment = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0

    if second_score >= NEAR_MISS_DESCRIPTION_THRESHOLD and (best_score - second_score) < AMBIGUITY_MARGIN:
        return {
            "exception_type": "ambiguous_match",
            "explanation": (
                f"No reference ID, and multiple candidates score similarly close (top description "
                f"scores {best_score:.0f} and {second_score:.0f}/100) - needs manual review or "
                f"LLM judgment to disambiguate, not a safe auto-match."
            ),
        }

    return {
        "exception_type": "missing_counterpart",
        "explanation": (
            f"No reference ID. Closest candidate is payment {best_payment['id']} (description "
            f"similarity {best_score:.0f}/100, amount off {best_amount_pct:.1%}, date off "
            f"{best_date_days}d) - not confident enough to auto-match."
        ),
    }


def _classify_unresolved(ledger_row: dict, payments_by_id: dict, all_payments: list[dict]) -> dict:
    ref_id = ledger_row.get("reference_id")

    if ref_id and ref_id in payments_by_id:
        return _classify_by_reference(ledger_row, payments_by_id[ref_id])
    if ref_id and ref_id not in payments_by_id:
        return {
            "exception_type": "missing_counterpart",
            "explanation": (
                f"Ledger row references '{ref_id}', but no payment with that ID exists in the "
                f"payment source at all."
            ),
        }
    return _classify_without_reference(ledger_row, all_payments)


def classify_exceptions(results: list[dict], payments: list[dict], ledger: list[dict]) -> list[dict]:
    """Return `results` with every unmatched row given an `exception_type` + `explanation`.

    Matched rows, and rows the engine already tagged during conflict
    resolution (`likely_duplicate`), pass through with an `explanation`
    added but their `exception_type` unchanged.
    """
    payments_by_id = {p["id"]: p for p in payments}
    ledger_by_id = {row["ledger_id"]: row for row in ledger}

    classified = []
    for r in results:
        if r["matched"] or r.get("exception_type") == "likely_duplicate":
            classified.append({**r, "explanation": r["reason"]})
            continue

        ledger_row = ledger_by_id[r["ledger_id"]]
        classification = _classify_unresolved(ledger_row, payments_by_id, payments)
        classified.append({**r, **classification})

    return classified


def summarize_exceptions(classified_results: list[dict]) -> dict:
    """Count exceptions by type — the headline "honest exception list" summary."""
    counts: dict[str, int] = {}
    for r in classified_results:
        if r["matched"]:
            continue
        counts[r["exception_type"]] = counts.get(r["exception_type"], 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))
