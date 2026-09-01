"""Builds the dashboard's results table, exception list, and downloadable
report from a matching run. Kept out of dashboard/app.py so this logic is
testable without Streamlit.
"""

from datetime import datetime, timezone

import pandas as pd

from src.exceptions.classifier import summarize_exceptions


def results_to_dataframe(results: list[dict], ledger: list[dict]) -> pd.DataFrame:
    ledger_by_id = {row["ledger_id"]: row for row in ledger}
    rows = []
    for r in results:
        ledger_row = ledger_by_id.get(r["ledger_id"], {})
        rows.append({
            "ledger_id": r["ledger_id"],
            "reference_id": ledger_row.get("reference_id"),
            "ledger_amount": ledger_row.get("amount"),
            "ledger_date": ledger_row.get("date"),
            "description": ledger_row.get("description"),
            "matched": r["matched"],
            "payment_id": r.get("payment_id"),
            "stage": r.get("stage"),
            "confidence": r.get("confidence"),
            "exception_type": r.get("exception_type"),
            "explanation": r.get("explanation", r.get("reason", "")),
        })
    return pd.DataFrame(rows)


def build_summary_text(results: list[dict], ledger: list[dict], scored: dict | None = None) -> str:
    n_total = len(results)
    n_matched = sum(1 for r in results if r["matched"])
    match_rate = n_matched / n_total if n_total else 0.0
    exception_summary = summarize_exceptions(results)

    lines = [
        "Reconciliation Report",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Total ledger rows: {n_total}",
        f"Matched: {n_matched} ({match_rate:.1%})",
        f"Unresolved: {n_total - n_matched}",
    ]
    if scored is not None:
        lines.append(f"Measured accuracy (vs ground truth): {scored['overall_accuracy']:.1%}")
    else:
        lines.append("Measured accuracy: N/A (no ground truth available for this dataset)")

    lines.append("")
    lines.append("Exception breakdown:")
    if exception_summary:
        for exception_type, count in exception_summary.items():
            lines.append(f"  {exception_type}: {count}")
    else:
        lines.append("  (none - every ledger row was resolved)")

    lines.append("")
    lines.append("Full exception list:")
    unresolved = [r for r in results if not r["matched"]]
    if unresolved:
        for r in unresolved:
            lines.append(f"  [{r.get('exception_type')}] {r['ledger_id']}: {r.get('explanation', r.get('reason', ''))}")
    else:
        lines.append("  (none)")

    return "\n".join(lines)
