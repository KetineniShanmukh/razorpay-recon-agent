"""Loads payments/ledger data from uploaded CSV files into the exact record
shape the matching engine expects (the same shape
razorpay_style_generator.generate_payments / synthetic_ledger.generate_ledger
produce in memory).

CSV round-tripping loses the distinction between int/float/str, and pandas'
numpy scalar types don't reliably satisfy the isinstance() checks the
matching code relies on (e.g. np.int64 doesn't always pass `isinstance(x,
int)`) - so this does explicit, native-type casting rather than trusting
pandas' inferred dtypes.
"""

import pandas as pd

PAYMENT_INT_FIELDS = ["amount", "fee", "tax", "created_at"]
PAYMENT_STR_FIELDS = [
    "id", "entity", "currency", "status", "order_id", "method",
    "description", "email", "contact",
]
PAYMENT_OPTIONAL_STR_FIELDS = ["card_id", "bank", "wallet", "vpa", "error_code", "error_description"]

LEDGER_STR_FIELDS = ["ledger_id", "reference_id", "date", "description", "vendor_contact"]


def _to_native_str(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)


def load_payments_csv(file) -> list[dict]:
    """Parse an uploaded payments CSV into native-typed records."""
    df = pd.read_csv(file)
    records = []
    for _, row in df.iterrows():
        record: dict = {}
        for field in PAYMENT_INT_FIELDS:
            record[field] = int(row[field]) if field in row.index and pd.notna(row[field]) else 0
        for field in PAYMENT_STR_FIELDS:
            record[field] = _to_native_str(row[field]) if field in row.index else None
        for field in PAYMENT_OPTIONAL_STR_FIELDS:
            record[field] = _to_native_str(row[field]) if field in row.index else None
        if "captured" in row.index and pd.notna(row["captured"]):
            record["captured"] = bool(row["captured"])
        else:
            record["captured"] = record.get("status") == "captured"
        records.append(record)
    return records


def load_ledger_csv(file) -> list[dict]:
    """Parse an uploaded internal ledger CSV into native-typed records."""
    df = pd.read_csv(file)
    records = []
    for _, row in df.iterrows():
        record: dict = {}
        for field in LEDGER_STR_FIELDS:
            value = row[field] if field in row.index else None
            record[field] = _to_native_str(value) or ""
        record["amount"] = float(row["amount"]) if "amount" in row.index and pd.notna(row["amount"]) else 0.0
        records.append(record)
    return records
