from src.ingest.razorpay_style_generator import generate_payments, generate_settlements
from src.ingest.synthetic_ledger import generate_ledger


def test_generate_payments_count_and_shape():
    payments = generate_payments(n=50, seed=1)
    assert len(payments) == 50
    for p in payments:
        assert p["id"].startswith("pay_")
        assert p["entity"] == "payment"
        assert p["amount"] > 0
        assert p["currency"] == "INR"
        assert isinstance(p["created_at"], int)  # Unix timestamp, matching real Razorpay API


def test_generate_payments_reproducible_with_seed():
    a = generate_payments(n=20, seed=7)
    b = generate_payments(n=20, seed=7)
    assert [p["id"] for p in a] == [p["id"] for p in b]


def test_generate_payments_method_specific_fields_are_exclusive():
    payments = generate_payments(n=100, seed=4)
    for p in payments:
        populated = [f for f in ("card_id", "bank", "wallet", "vpa") if p[f] is not None]
        assert len(populated) == 1, f"expected exactly one method field set, got {populated}"


def test_generate_settlements_batches_only_captured_payments():
    payments = generate_payments(n=60, seed=6)
    settlements = generate_settlements(payments, seed=6)

    assert len(settlements) > 0
    for s in settlements:
        assert s["id"].startswith("setl_")
        assert s["entity"] == "settlement"
        assert s["status"] == "processed"

    total_settled = sum(s["amount"] + s["fees"] + s["tax"] for s in settlements)
    total_captured = sum(p["amount"] for p in payments if p["captured"])
    assert total_settled == total_captured


def test_generate_ledger_ground_truth_consistency():
    payments = generate_payments(n=60, seed=3)
    ledger_rows, ground_truth = generate_ledger(payments, seed=3, extra_ledger_only_rows=4)

    ledger_ids_in_rows = {row["ledger_id"] for row in ledger_rows}
    ledger_ids_in_truth = {t["ledger_id"] for t in ground_truth["ledger_truth"]}
    assert ledger_ids_in_rows == ledger_ids_in_truth

    # Every non-null true_payment_id in the truth key must exist among the
    # generated payments.
    real_payment_ids = {p["id"] for p in payments}
    for truth_row in ground_truth["ledger_truth"]:
        if truth_row["true_payment_id"] is not None:
            assert truth_row["true_payment_id"] in real_payment_ids

    # Ledger-only rows (no real payment) must be tagged accordingly.
    ledger_only = [t for t in ground_truth["ledger_truth"] if t["true_payment_id"] is None]
    assert len(ledger_only) == 4
    assert all(t["noise_type"] == "ledger_only_no_counterpart" for t in ledger_only)


def test_missing_counterpart_payments_have_no_ledger_row():
    payments = generate_payments(n=80, seed=9)
    ledger_rows, ground_truth = generate_ledger(payments, seed=9)

    referenced_ids = {row["reference_id"] for row in ledger_rows if row["reference_id"]}
    for payment_id in ground_truth["unmatched_payment_ids"]:
        assert payment_id not in referenced_ids
