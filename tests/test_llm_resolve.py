"""Tests for stage 3 use a fake Anthropic client - no real API calls, no
cost, no network dependency, and no ANTHROPIC_API_KEY needed to run the
test suite (including in CI)."""

import json
from types import SimpleNamespace

from src.exceptions.classifier import classify_exceptions
from src.ingest.razorpay_style_generator import generate_payments
from src.ingest.synthetic_ledger import generate_ledger
from src.matching.engine import run_matching
from src.matching.llm_resolve import resolve_with_llm


class FakeMessages:
    def __init__(self, response_text: str, stop_reason: str = "end_turn", stop_details=None):
        self._response_text = response_text
        self._stop_reason = stop_reason
        self._stop_details = stop_details
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self._response_text)],
            stop_reason=self._stop_reason,
            stop_details=self._stop_details,
        )


class FakeClient:
    def __init__(self, response_text: str, stop_reason: str = "end_turn", stop_details=None):
        self.messages = FakeMessages(response_text, stop_reason, stop_details)


def _setup(seed: int = 42, n: int = 80):
    payments = generate_payments(n=n, seed=seed)
    ledger, _ = generate_ledger(payments, seed=seed)
    output = run_matching(payments, ledger)
    classified = classify_exceptions(output["results"], payments, ledger)
    return payments, ledger, output, classified


def test_llm_match_decision_flips_row_to_matched():
    payments, ledger, output, classified = _setup()
    unresolved = [r for r in classified if not r["matched"]]
    assert unresolved, "expected at least one unresolved row in this dataset"
    target = unresolved[0]

    # Whatever candidate the eligible row would be shown, claim a match on it.
    from src.matching.llm_resolve import _find_candidates
    ledger_by_id = {row["ledger_id"]: row for row in ledger}
    candidates = _find_candidates(
        ledger_by_id[target["ledger_id"]],
        [p for p in payments if p["id"] in output["unmatched_payment_ids"]],
    )
    fake_payment_id = candidates[0]["id"] if candidates else "pay_FAKE00000001"

    response_json = json.dumps({
        "decision": "match", "payment_id": fake_payment_id,
        "confidence": "high", "reasoning": "Same vendor, date just recorded late.",
    })
    client = FakeClient(response_json)

    updated, audit_log = resolve_with_llm(
        classified, payments, ledger, output["unmatched_payment_ids"], client=client,
    )

    if target.get("exception_type") in {
        "ambiguous_match", "missing_counterpart", "date_drift", "amount_mismatch", "currency_fee_delta",
    }:
        result = next(r for r in updated if r["ledger_id"] == target["ledger_id"])
        assert result["matched"] is True
        assert result["stage"] == "llm_assisted"
        assert result["payment_id"] == fake_payment_id
        assert any(a["ledger_id"] == target["ledger_id"] for a in audit_log)


def test_llm_no_match_decision_keeps_row_unresolved_with_reasoning_appended():
    payments, ledger, output, classified = _setup()
    eligible = [
        r for r in classified
        if not r["matched"] and r.get("exception_type") in {
            "ambiguous_match", "missing_counterpart", "date_drift", "amount_mismatch", "currency_fee_delta",
        }
    ]
    assert eligible, "expected at least one stage-3-eligible row in this dataset"
    target = eligible[0]

    response_json = json.dumps({
        "decision": "no_match", "payment_id": None,
        "confidence": "high", "reasoning": "No candidate plausibly matches this row.",
    })
    client = FakeClient(response_json)

    updated, audit_log = resolve_with_llm(
        classified, payments, ledger, output["unmatched_payment_ids"], client=client,
    )

    result = next(r for r in updated if r["ledger_id"] == target["ledger_id"])
    assert result["matched"] is False
    assert "LLM reviewed" in result["explanation"]


def test_malformed_llm_response_is_handled_gracefully_not_crashed():
    payments, ledger, output, classified = _setup()
    eligible = [
        r for r in classified
        if not r["matched"] and r.get("exception_type") in {
            "ambiguous_match", "missing_counterpart", "date_drift", "amount_mismatch", "currency_fee_delta",
        }
    ]
    assert eligible

    client = FakeClient("This is not JSON at all, the model misbehaved.")

    updated, audit_log = resolve_with_llm(
        classified, payments, ledger, output["unmatched_payment_ids"], client=client,
    )

    # Should not crash, and every malformed response should be logged as a
    # no_match with the parse failure visible in the audit trail.
    for entry in audit_log:
        assert entry["decision"] == "no_match"
        assert "could not be parsed" in entry["reasoning"]


def test_empty_response_from_max_tokens_is_diagnosed_not_silently_swallowed():
    payments, ledger, output, classified = _setup()
    eligible = [
        r for r in classified
        if not r["matched"] and r.get("exception_type") in {
            "ambiguous_match", "missing_counterpart", "date_drift", "amount_mismatch", "currency_fee_delta",
        }
    ]
    assert eligible

    # Reproduces a real failure seen in manual testing: Opus 5's adaptive
    # thinking consumed the whole token budget, leaving no text response.
    client = FakeClient("", stop_reason="max_tokens")

    _, audit_log = resolve_with_llm(
        classified, payments, ledger, output["unmatched_payment_ids"], client=client,
    )

    for entry in audit_log:
        assert entry["decision"] == "no_match"
        assert "max_tokens" in entry["reasoning"]


def test_model_refusal_is_diagnosed_with_category_not_silently_swallowed():
    payments, ledger, output, classified = _setup()
    eligible = [
        r for r in classified
        if not r["matched"] and r.get("exception_type") in {
            "ambiguous_match", "missing_counterpart", "date_drift", "amount_mismatch", "currency_fee_delta",
        }
    ]
    assert eligible

    # Reproduces a real refusal seen in manual testing on a benign
    # reconciliation prompt - rare, but must degrade safely and explain why.
    stop_details = SimpleNamespace(category="frontier_llm")
    client = FakeClient("", stop_reason="refusal", stop_details=stop_details)

    _, audit_log = resolve_with_llm(
        classified, payments, ledger, output["unmatched_payment_ids"], client=client,
    )

    for entry in audit_log:
        assert entry["decision"] == "no_match"
        assert "refusal" in entry["reasoning"]
        assert "frontier_llm" in entry["reasoning"]


def test_llm_never_double_books_a_payment_across_rows():
    payments, ledger, output, classified = _setup()
    eligible = [
        r for r in classified
        if not r["matched"] and r.get("exception_type") in {
            "ambiguous_match", "missing_counterpart", "date_drift", "amount_mismatch", "currency_fee_delta",
        }
    ]
    if len(eligible) < 2:
        return  # not enough eligible rows in this dataset to meaningfully test collision

    # Every eligible row's candidate search picks the SAME payment (an
    # adversarial fake client) - it should only ever get claimed once.
    from src.matching.llm_resolve import _find_candidates
    ledger_by_id = {row["ledger_id"]: row for row in ledger}
    first_candidates = _find_candidates(
        ledger_by_id[eligible[0]["ledger_id"]],
        [p for p in payments if p["id"] in output["unmatched_payment_ids"]],
    )
    if not first_candidates:
        return
    shared_payment_id = first_candidates[0]["id"]

    response_json = json.dumps({
        "decision": "match", "payment_id": shared_payment_id,
        "confidence": "high", "reasoning": "Claims to match.",
    })
    client = FakeClient(response_json)

    updated, _ = resolve_with_llm(classified, payments, ledger, output["unmatched_payment_ids"], client=client)

    matched_payment_ids = [r["payment_id"] for r in updated if r["matched"]]
    assert len(matched_payment_ids) == len(set(matched_payment_ids)), "a payment was claimed by more than one row"
