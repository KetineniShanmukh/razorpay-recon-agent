from src.ingest.synthetic_ledger import generate_ledger
from src.ingest.synthetic_transactions import generate_transactions


def test_generate_transactions_count_and_shape():
    txns = generate_transactions(n=50, seed=1)
    assert len(txns) == 50
    for t in txns:
        assert t["payment_id"].startswith("pay_")
        assert t["amount"] > 0
        assert t["currency"] == "INR"


def test_generate_transactions_reproducible_with_seed():
    a = generate_transactions(n=20, seed=7)
    b = generate_transactions(n=20, seed=7)
    assert [t["payment_id"] for t in a] == [t["payment_id"] for t in b]


def test_generate_ledger_ground_truth_consistency():
    txns = generate_transactions(n=60, seed=3)
    ledger_rows, ground_truth = generate_ledger(txns, seed=3, extra_ledger_only_rows=4)

    ledger_ids_in_rows = {row["ledger_id"] for row in ledger_rows}
    ledger_ids_in_truth = {t["ledger_id"] for t in ground_truth["ledger_truth"]}
    assert ledger_ids_in_rows == ledger_ids_in_truth

    # Every non-null true_payment_id in the truth key must exist among the
    # generated transactions.
    real_payment_ids = {t["payment_id"] for t in txns}
    for truth_row in ground_truth["ledger_truth"]:
        if truth_row["true_payment_id"] is not None:
            assert truth_row["true_payment_id"] in real_payment_ids

    # Ledger-only rows (no real transaction) must be tagged accordingly.
    ledger_only = [t for t in ground_truth["ledger_truth"] if t["true_payment_id"] is None]
    assert len(ledger_only) == 4
    assert all(t["noise_type"] == "ledger_only_no_counterpart" for t in ledger_only)


def test_missing_counterpart_payments_have_no_ledger_row():
    txns = generate_transactions(n=80, seed=9)
    ledger_rows, ground_truth = generate_ledger(txns, seed=9)

    referenced_ids = {row["reference_id"] for row in ledger_rows if row["reference_id"]}
    for payment_id in ground_truth["unmatched_payment_ids"]:
        assert payment_id not in referenced_ids
