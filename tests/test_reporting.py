import io

import pandas as pd

from src.exceptions.classifier import classify_exceptions
from src.ingest.razorpay_style_generator import generate_payments
from src.ingest.synthetic_ledger import generate_ledger
from src.matching.engine import run_matching
from src.reporting.loaders import load_ledger_csv, load_payments_csv
from src.reporting.report import build_summary_text, results_to_dataframe


def _csv_bytes(records: list[dict]) -> io.BytesIO:
    df = pd.DataFrame(records)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


def test_load_payments_csv_round_trip_preserves_native_types():
    payments = generate_payments(n=20, seed=1)
    loaded = load_payments_csv(_csv_bytes(payments))

    assert len(loaded) == 20
    for record in loaded:
        assert isinstance(record["amount"], int)
        assert isinstance(record["created_at"], int)
        assert isinstance(record["id"], str)
        # isinstance(True, int) is True in Python, so exclude bool explicitly
        # to actually verify amount/created_at aren't numpy scalars in disguise.
        assert type(record["amount"]) is int
        assert type(record["created_at"]) is int


def test_load_ledger_csv_round_trip_preserves_native_types():
    payments = generate_payments(n=20, seed=2)
    ledger, _ = generate_ledger(payments, seed=2)
    loaded = load_ledger_csv(_csv_bytes(ledger))

    assert len(loaded) == len(ledger)
    for record in loaded:
        assert type(record["amount"]) is float
        assert isinstance(record["ledger_id"], str)
        assert isinstance(record["date"], str)


def test_uploaded_csv_data_runs_through_matching_engine_without_error():
    payments = generate_payments(n=40, seed=3)
    ledger, _ = generate_ledger(payments, seed=3)

    loaded_payments = load_payments_csv(_csv_bytes(payments))
    loaded_ledger = load_ledger_csv(_csv_bytes(ledger))

    output = run_matching(loaded_payments, loaded_ledger)
    assert output["stats"]["matched"] > 0


def test_missing_reference_round_trips_as_empty_string_not_nan():
    payments = generate_payments(n=40, seed=5)
    ledger, _ = generate_ledger(payments, seed=5)
    assert any(row["reference_id"] == "" for row in ledger), "expected some missing-reference rows in this seed"

    loaded_ledger = load_ledger_csv(_csv_bytes(ledger))
    for record in loaded_ledger:
        assert record["reference_id"] is not None
        assert not (isinstance(record["reference_id"], float))  # never a stray NaN float


def test_results_to_dataframe_has_expected_columns():
    payments = generate_payments(n=30, seed=6)
    ledger, _ = generate_ledger(payments, seed=6)
    output = run_matching(payments, ledger)
    classified = classify_exceptions(output["results"], payments, ledger)

    df = results_to_dataframe(classified, ledger)
    assert len(df) == len(ledger)
    for col in ["ledger_id", "matched", "payment_id", "stage", "exception_type", "explanation"]:
        assert col in df.columns


def test_build_summary_text_includes_key_sections():
    payments = generate_payments(n=30, seed=7)
    ledger, _ = generate_ledger(payments, seed=7)
    output = run_matching(payments, ledger)
    classified = classify_exceptions(output["results"], payments, ledger)

    summary = build_summary_text(classified, ledger)
    assert "Total ledger rows:" in summary
    assert "Exception breakdown:" in summary
    assert "Measured accuracy: N/A" in summary  # no ground truth passed
