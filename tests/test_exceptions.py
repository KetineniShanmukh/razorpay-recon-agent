from datetime import datetime, timedelta, timezone

from src.exceptions.classifier import classify_exceptions
from src.ingest.razorpay_style_generator import generate_payments
from src.ingest.synthetic_ledger import generate_ledger
from src.matching.engine import run_matching

NOW = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())


def _payment(**overrides) -> dict:
    base = {
        "id": "pay_TESTPAYMENT01",
        "entity": "payment",
        "amount": 10000,  # Rs.100.00 in paise
        "currency": "INR",
        "status": "captured",
        "captured": True,
        "description": "Payment for Acme Corp",
        "fee": 200,   # Rs.2.00
        "tax": 36,    # Rs.0.36
        "created_at": NOW,
    }
    base.update(overrides)
    return base


def _ledger_row(**overrides) -> dict:
    base = {
        "ledger_id": "LDG00001",
        "reference_id": "pay_TESTPAYMENT01",
        "amount": 100.00,
        "date": datetime.fromtimestamp(NOW, tz=timezone.utc).date().isoformat(),
        "description": "Payment for Acme Corp",
        "vendor_contact": "555-0100",
    }
    base.update(overrides)
    return base


def _run(payments, ledger):
    output = run_matching(payments, ledger)
    return classify_exceptions(output["results"], payments, ledger)


def test_classifies_currency_fee_delta():
    # Small payment amount so fee+tax is a large % of it (>6% fuzzy tolerance),
    # guaranteeing stage 2 can't absorb the delta and this reaches the classifier.
    payment = _payment(amount=2000, fee=200, tax=36)  # Rs.20.00, fee+tax Rs.2.36 (11.8%)
    ledger_row = _ledger_row(amount=20.00 - 2.36)  # net of fee+tax
    classified = _run([payment], [ledger_row])

    result = next(r for r in classified if r["ledger_id"] == "LDG00001")
    assert result["exception_type"] == "currency_fee_delta"


def test_classifies_amount_mismatch():
    payment = _payment()
    ledger_row = _ledger_row(amount=80.00)  # 20% off, not a fee-sized delta
    classified = _run([payment], [ledger_row])

    result = next(r for r in classified if r["ledger_id"] == "LDG00001")
    assert result["exception_type"] == "amount_mismatch"


def test_classifies_date_drift():
    payment = _payment()
    drifted_date = (datetime.fromtimestamp(NOW, tz=timezone.utc) + timedelta(days=10)).date().isoformat()
    ledger_row = _ledger_row(amount=100.00, date=drifted_date)
    classified = _run([payment], [ledger_row])

    result = next(r for r in classified if r["ledger_id"] == "LDG00001")
    assert result["exception_type"] == "date_drift"


def test_classifies_missing_counterpart_for_invalid_reference():
    # Amount/description deliberately don't point back at the one real payment
    # either, so stage 2's fuzzy fallback can't rescue it via other signals.
    payment = _payment(description="Payment for Zeta Industries")
    ledger_row = _ledger_row(
        reference_id="pay_DOESNOTEXIST0", amount=500.00, description="Unrelated Manual Entry",
    )
    classified = _run([payment], [ledger_row])

    result = next(r for r in classified if r["ledger_id"] == "LDG00001")
    assert result["exception_type"] == "missing_counterpart"


def test_classifies_missing_counterpart_for_no_reference_no_candidate():
    payment = _payment(description="Payment for Zeta Industries")
    ledger_row = _ledger_row(
        reference_id="",
        amount=999999.99,
        description="Completely Unrelated Manual Entry",
    )
    classified = _run([payment], [ledger_row])

    result = next(r for r in classified if r["ledger_id"] == "LDG00001")
    assert result["exception_type"] == "missing_counterpart"


def test_classifies_ambiguous_match_for_close_candidates():
    # Identical descriptions guarantee a tied fuzzy score between two
    # candidates, both within amount/date tolerance - genuine ambiguity,
    # not a tie broken by chance.
    payment_a = _payment(id="pay_CANDIDATEA001", description="Payment for Acme Corp", amount=10000)
    payment_b = _payment(id="pay_CANDIDATEB001", description="Payment for Acme Corp", amount=10050)
    ledger_row = _ledger_row(reference_id="", amount=100.00, description="Payment for Acme Corp")
    classified = _run([payment_a, payment_b], [ledger_row])

    result = next(r for r in classified if r["ledger_id"] == "LDG00001")
    assert result["exception_type"] == "ambiguous_match"


def test_likely_duplicate_passes_through_from_engine():
    payment = _payment()
    original = _ledger_row(ledger_id="LDG00001")
    duplicate = _ledger_row(ledger_id="LDG00002")
    classified = _run([payment], [original, duplicate])

    duplicate_result = next(r for r in classified if r["exception_type"] == "likely_duplicate")
    assert duplicate_result["matched"] is False
    assert "explanation" in duplicate_result


def test_classify_exceptions_on_real_generated_dataset_covers_all_unresolved():
    payments = generate_payments(n=80, seed=42)
    ledger, _ = generate_ledger(payments, seed=42)
    output = run_matching(payments, ledger)

    classified = classify_exceptions(output["results"], payments, ledger)

    # Every unmatched row must get a non-null exception_type and explanation.
    for r in classified:
        if not r["matched"]:
            assert r["exception_type"] is not None
            assert r["explanation"]
