"""Stage 3: LLM-assisted resolution.

Runs after stages 1 (deterministic) and 2 (fuzzy) have done what they can,
and after the exception classifier has explained what's left. This stage
only touches rows a human would resolve by judgment, not rule: a valid
reference ID whose amount/date drifted past auto-match tolerance
(`date_drift`, `amount_mismatch`, `currency_fee_delta`), a near-miss with no
reference ID (`missing_counterpart`), or genuinely tied candidates
(`ambiguous_match`). It's deliberately low-volume and per-row, not a bulk
classifier — in our test runs this is a handful of calls, not hundreds.

For each eligible row, Claude is shown the ledger row, up to 3 candidate
payments (still-unclaimed only, so it can't double-book a payment another
row already matched), and the classifier's own rule-based explanation for
context. It must return a decision plus reasoning; every call's full prompt
and response is kept in the returned audit log, not just the final verdict —
that's the audit trail the brief asks for.
"""

import json
import os
from datetime import date, datetime, timezone

import anthropic
import pandas as pd
from dotenv import load_dotenv
from rapidfuzz import fuzz

MODEL = "claude-opus-5"
MAX_CANDIDATES = 3
# Opus 5 runs adaptive thinking by default (unlike Opus 4.8/4.7) - at 1024
# max_tokens, thinking alone could consume the whole budget and leave zero
# tokens for the actual JSON response, which is exactly what happened in
# testing (an empty response that failed to parse). Room to think AND answer.
MAX_TOKENS = 4096

# Exception types a human would resolve by judgment rather than a hard rule.
# `likely_duplicate` is excluded: conflict resolution already has a definitive
# winner elsewhere, there's nothing ambiguous left to judge.
STAGE3_ELIGIBLE_TYPES = {
    "ambiguous_match",
    "missing_counterpart",
    "date_drift",
    "amount_mismatch",
    "currency_fee_delta",
}

CONFIDENCE_TO_SCORE = {"high": 0.85, "medium": 0.65, "low": 0.45}


def _to_date(value) -> date:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()


def _find_candidates(ledger_row: dict, available_payments: list[dict], max_candidates: int = MAX_CANDIDATES) -> list[dict]:
    """Pick candidates to show the LLM. A valid reference ID is decisive on
    its own; otherwise rank by a loose combined amount/date/description
    relevance score (looser than the deterministic tolerance checks - this
    is just for choosing what to show, not for deciding a match)."""
    ref_id = ledger_row.get("reference_id")
    payments_by_id = {p["id"]: p for p in available_payments}

    if ref_id and ref_id in payments_by_id:
        return [payments_by_id[ref_id]]

    row_date = _to_date(ledger_row["date"])
    scored = []
    for payment in available_payments:
        payment_amount = payment["amount"] / 100
        amount_diff_pct = abs(payment_amount - ledger_row["amount"]) / payment_amount if payment_amount else 1.0
        date_diff_days = abs((row_date - _to_date(payment["created_at"])).days)
        desc_score = fuzz.token_sort_ratio(ledger_row.get("description", ""), payment.get("description", ""))
        relevance = desc_score - (amount_diff_pct * 100) - (date_diff_days * 2)
        scored.append((relevance, payment))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [payment for _, payment in scored[:max_candidates]]


def _format_payment(payment: dict) -> str:
    return (
        f"id={payment['id']}, amount=Rs.{payment['amount'] / 100:.2f}, "
        f"date={_to_date(payment['created_at']).isoformat()}, "
        f"description=\"{payment['description']}\", method={payment.get('method')}, "
        f"fee=Rs.{payment.get('fee', 0) / 100:.2f}, tax=Rs.{payment.get('tax', 0) / 100:.2f}"
    )


def _build_prompt(ledger_row: dict, candidates: list[dict], classifier_explanation: str) -> str:
    candidates_text = (
        "\n".join(f"  Candidate {i + 1}: {_format_payment(p)}" for i, p in enumerate(candidates))
        if candidates else "  (no plausible candidates found)"
    )

    return f"""You are helping reconcile an internal finance ledger against payment gateway records.

Ledger row (internal bookkeeping record, may contain typos or manual-entry noise):
  reference_id="{ledger_row.get('reference_id') or '(none)'}", amount=Rs.{ledger_row['amount']:.2f}, date={ledger_row['date']}, description="{ledger_row.get('description', '')}"

Candidate payment(s) from the gateway (already filtered to unclaimed payments only):
{candidates_text}

A rule-based system already checked this row and could not confidently auto-match it. Its own explanation was: "{classifier_explanation}"

Decide: does this ledger row genuinely correspond to one of the candidate payments (small noise like a typo, a late-recorded date, or a fee deduction is fine and should still count as a match), or is it a real exception with no true match among the candidates?

Respond with ONLY a JSON object, no other text, in exactly this shape:
{{"decision": "match" or "no_match", "payment_id": "<id of the matching candidate, or null>", "confidence": "high" or "medium" or "low", "reasoning": "<one or two sentences explaining your decision>"}}"""


def _call_llm(client, prompt: str) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        # Medium effort: this is a bounded judgment call on a few fields, not
        # deep multi-step reasoning - keeps thinking token spend (and cost)
        # proportionate to the task instead of defaulting to "high".
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = "".join(block.text for block in response.content if block.type == "text").strip()

    cleaned = raw_text
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            failure_note = f"Model declined to answer (refusal, category={category}) - treated as unresolved."
        elif not raw_text and response.stop_reason == "max_tokens":
            failure_note = f"Response was empty - hit max_tokens ({MAX_TOKENS}) before producing text, likely spent on thinking."
        elif not raw_text:
            failure_note = f"Response was empty (stop_reason={response.stop_reason})."
        else:
            failure_note = f"Response could not be parsed as JSON: {raw_text[:200]}"
        parsed = {"decision": "no_match", "payment_id": None, "confidence": "low", "reasoning": failure_note}
    return {"raw_response": raw_text, "parsed": parsed, "stop_reason": response.stop_reason}


def resolve_with_llm(
    classified_results: list[dict],
    payments: list[dict],
    ledger: list[dict],
    unmatched_payment_ids: list[str],
    client=None,
    api_key: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """Run stage 3 over rows the classifier flagged as judgment calls.

    Returns (updated_results, audit_log):
    - `updated_results`: `classified_results` with stage-3-resolved rows
      flipped to matched (stage="llm_assisted"); everything else unchanged.
    - `audit_log`: one entry per LLM call - ledger_id, candidates shown, full
      prompt, raw response, and parsed decision. This is the audit trail.
    """
    if client is None:
        load_dotenv()
        client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))

    ledger_by_id = {row["ledger_id"]: row for row in ledger}
    available_payment_ids = set(unmatched_payment_ids)
    results_by_id = {r["ledger_id"]: dict(r) for r in classified_results}
    audit_log = []

    for r in classified_results:
        if r["matched"] or r.get("exception_type") not in STAGE3_ELIGIBLE_TYPES:
            continue

        ledger_row = ledger_by_id[r["ledger_id"]]
        available_payments = [p for p in payments if p["id"] in available_payment_ids]
        candidates = _find_candidates(ledger_row, available_payments)

        prompt = _build_prompt(ledger_row, candidates, r.get("explanation", r.get("reason", "")))
        call_result = _call_llm(client, prompt)
        parsed = call_result["parsed"]

        audit_log.append({
            "ledger_id": r["ledger_id"],
            "candidates_shown": [c["id"] for c in candidates],
            "prompt": prompt,
            "raw_response": call_result["raw_response"],
            "stop_reason": call_result.get("stop_reason"),
            "decision": parsed.get("decision"),
            "llm_payment_id": parsed.get("payment_id"),
            "confidence": parsed.get("confidence"),
            "reasoning": parsed.get("reasoning"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": MODEL,
        })

        decided_payment_id = parsed.get("payment_id")
        current = results_by_id[r["ledger_id"]]

        if parsed.get("decision") == "match" and decided_payment_id in available_payment_ids:
            results_by_id[r["ledger_id"]] = {
                **current,
                "payment_id": decided_payment_id,
                "matched": True,
                "stage": "llm_assisted",
                "exception_type": None,
                "confidence": CONFIDENCE_TO_SCORE.get(parsed.get("confidence"), 0.5),
                "reason": f"LLM-assisted match: {parsed.get('reasoning', '')}",
                "explanation": f"LLM-assisted match: {parsed.get('reasoning', '')}",
            }
            available_payment_ids.discard(decided_payment_id)
        else:
            results_by_id[r["ledger_id"]] = {
                **current,
                "explanation": (
                    f"{current.get('explanation', '')} "
                    f"[LLM reviewed, confirmed exception: {parsed.get('reasoning', '')}]"
                ).strip(),
            }

    updated_results = [results_by_id[r["ledger_id"]] for r in classified_results]
    return updated_results, audit_log
