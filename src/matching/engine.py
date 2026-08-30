"""Matching engine orchestrator.

Runs the multi-stage pipeline (deterministic -> fuzzy -> LLM-assisted) over
a payments list and a ledger list, resolves conflicts where multiple ledger
rows claim the same payment (duplicates), and returns one final verdict per
ledger row plus a list of payments with no ledger row at all.

Stage 3 (LLM-assisted) is not wired in yet — anything stage 1 and 2 can't
resolve is reported as an honest, unresolved exception rather than silently
guessed at. See PROGRESS.md for the plan to add it once an LLM API key is
available.
"""

from src.matching.deterministic import match_deterministic
from src.matching.fuzzy import match_fuzzy

MATCHED_STAGES = ("deterministic", "fuzzy_reference_tolerance", "fuzzy_description")


def run_matching(payments: list[dict], ledger: list[dict]) -> dict:
    """Run the full matching pipeline.

    Returns:
        {
          "results": [  # one row per ledger entry
              {"ledger_id", "payment_id" (or None), "stage", "confidence",
               "reason", "matched", "exception_type"}
          ],
          "unmatched_payment_ids": [payment_id, ...],  # payments no ledger row landed on
          "stats": {...}
        }
    """
    stage1_candidates = match_deterministic(payments, ledger)
    stage1_ledger_ids = {c["ledger_id"] for c in stage1_candidates}
    stage1_payment_ids = {c["payment_id"] for c in stage1_candidates}

    remaining_ledger = [row for row in ledger if row["ledger_id"] not in stage1_ledger_ids]
    remaining_payments = [p for p in payments if p["payment_id"] not in stage1_payment_ids]

    stage2_candidates = match_fuzzy(remaining_ledger, remaining_payments)

    all_candidates = stage1_candidates + stage2_candidates

    # --- Conflict resolution: at most one ledger row wins each payment ID ---
    by_payment: dict[str, list[dict]] = {}
    for c in all_candidates:
        by_payment.setdefault(c["payment_id"], []).append(c)

    final_by_ledger_id: dict[str, dict] = {}
    duplicate_flags: dict[str, dict] = {}

    for payment_id, claims in by_payment.items():
        claims.sort(key=lambda c: c["confidence"], reverse=True)
        winner = claims[0]
        final_by_ledger_id[winner["ledger_id"]] = winner
        for loser in claims[1:]:
            duplicate_flags[loser["ledger_id"]] = {
                "ledger_id": loser["ledger_id"],
                "payment_id": None,
                "stage": "conflict_resolution",
                "confidence": 0.0,
                "reason": (
                    f"Also matched payment {payment_id}, already claimed by ledger row "
                    f"{winner['ledger_id']} with higher confidence - flagged as likely duplicate"
                ),
                "exception_type": "likely_duplicate",
            }

    results = []
    for row in ledger:
        lid = row["ledger_id"]
        if lid in final_by_ledger_id:
            results.append({**final_by_ledger_id[lid], "matched": True, "exception_type": None})
        elif lid in duplicate_flags:
            results.append({**duplicate_flags[lid], "matched": False})
        else:
            results.append({
                "ledger_id": lid,
                "payment_id": None,
                "stage": "unresolved",
                "confidence": 0.0,
                "reason": "No stage 1 or stage 2 match found within tolerance",
                "matched": False,
                "exception_type": None,  # to be filled in by the exception classifier
            })

    matched_payment_ids = {r["payment_id"] for r in results if r["matched"]}
    unmatched_payment_ids = [p["payment_id"] for p in payments if p["payment_id"] not in matched_payment_ids]

    n_matched = sum(1 for r in results if r["matched"])
    stats = {
        "total_ledger_rows": len(ledger),
        "matched": n_matched,
        "unresolved": len(results) - n_matched,
        "match_rate": round(n_matched / len(ledger), 4) if ledger else 0.0,
        "by_stage": {
            stage: sum(1 for r in results if r["matched"] and r["stage"] == stage)
            for stage in MATCHED_STAGES
        },
        "unmatched_payments": len(unmatched_payment_ids),
    }

    return {
        "results": results,
        "unmatched_payment_ids": unmatched_payment_ids,
        "stats": stats,
    }
