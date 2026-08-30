"""Generates a synthetic "internal ledger" — the second reconciliation data source.

Takes a set of ground-truth gateway transactions (see synthetic_transactions.py)
and derives a noisy internal ledger from them: typos, date drift (including
drift wide enough that no matching stage can resolve it automatically),
duplicate entries, amount mismatches, fee/tax deltas, and missing reference
IDs, plus rows that genuinely have no counterpart on either side.

Crucially, this also returns a ground-truth answer key (which ledger row
really maps to which payment, and what noise was applied). That key must be
kept OUT of the matching engine's input — it exists only so we can measure
the engine's real accuracy afterwards instead of eyeballing the results.
"""

import random
from datetime import timedelta

# Noise applied per ledger row derived from a real transaction.
NOISE_WEIGHTS = {
    "clean": 0.45,
    "typo": 0.12,
    "date_drift": 0.10,
    "amount_mismatch": 0.08,
    "missing_reference": 0.06,
    "duplicate": 0.05,
    "missing_counterpart": 0.04,  # payment exists, ledger never records it -> true exception
    "large_date_drift": 0.05,     # drift beyond both matching stages' windows -> genuinely unresolved
    "currency_fee_delta": 0.05,   # ledger recorded net-of-fee amount, not gross -> real bookkeeping mismatch
}

FAKE_VENDOR_LABELS = [
    "Unknown Vendor",
    "Manual Entry - Office Supplies",
    "Petty Cash Adjustment",
    "Unreconciled Transfer",
]


def _typo(text: str) -> str:
    """Apply one random character-level typo (swap, drop, or duplicate)."""
    if len(text) < 4:
        return text
    i = random.randint(1, len(text) - 2)
    chars = list(text)
    op = random.choice(["swap", "drop", "dup"])
    if op == "swap":
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
    elif op == "drop":
        del chars[i]
    else:
        chars.insert(i, chars[i])
    return "".join(chars)


def generate_ledger(
    transactions: list[dict],
    seed: int = 42,
    extra_ledger_only_rows: int = 4,
) -> tuple[list[dict], dict]:
    """Build a noisy internal ledger from ground-truth transactions.

    Returns (ledger_rows, ground_truth) where ground_truth is:
        {
          "ledger_truth": [{"ledger_id", "true_payment_id" (or None), "noise_type"}, ...],
          "unmatched_payment_ids": [payment_id, ...],  # payments with no ledger row at all
        }
    """
    random.seed(seed)
    ledger_rows: list[dict] = []
    ledger_truth: list[dict] = []
    unmatched_payment_ids: list[str] = []
    ledger_id_counter = 1

    noise_names = list(NOISE_WEIGHTS.keys())
    noise_probs = list(NOISE_WEIGHTS.values())

    for txn in transactions:
        noise = random.choices(noise_names, weights=noise_probs, k=1)[0]

        if noise == "missing_counterpart":
            # No ledger row is created for this payment at all.
            unmatched_payment_ids.append(txn["payment_id"])
            continue

        row = {
            "ledger_id": f"LDG{ledger_id_counter:05d}",
            "reference_id": txn["payment_id"],
            "amount": round(txn["amount"] / 100, 2),  # ledger kept in rupees, gateway in paise
            "date": txn["created_at"].date().isoformat(),
            "description": txn["description"],
            "vendor_contact": txn["contact"],
        }

        if noise == "typo":
            row["description"] = _typo(row["description"])
        elif noise == "date_drift":
            drift_days = random.choice([-3, -2, -1, 1, 2, 3])
            row["date"] = (txn["created_at"] + timedelta(days=drift_days)).date().isoformat()
        elif noise == "amount_mismatch":
            delta_pct = random.uniform(0.01, 0.05) * random.choice([-1, 1])
            row["amount"] = round(row["amount"] * (1 + delta_pct), 2)
        elif noise == "missing_reference":
            row["reference_id"] = ""
        elif noise == "large_date_drift":
            drift_days = random.choice([-10, -9, -8, -7, -6, 6, 7, 8, 9, 10])
            row["date"] = (txn["created_at"] + timedelta(days=drift_days)).date().isoformat()
        elif noise == "currency_fee_delta":
            # Ledger recorded the net-of-fee amount instead of the gross amount —
            # a real bookkeeping mismatch, not random noise.
            net_paise = txn["amount"] - txn["fee"] - txn["tax"]
            row["amount"] = round(net_paise / 100, 2)

        ledger_rows.append(row)
        ledger_truth.append({
            "ledger_id": row["ledger_id"],
            "true_payment_id": txn["payment_id"],
            "noise_type": noise,
        })
        ledger_id_counter += 1

        if noise == "duplicate":
            dup_row = dict(row)
            dup_row["ledger_id"] = f"LDG{ledger_id_counter:05d}"
            ledger_rows.append(dup_row)
            ledger_truth.append({
                "ledger_id": dup_row["ledger_id"],
                "true_payment_id": txn["payment_id"],
                "noise_type": "duplicate",
            })
            ledger_id_counter += 1

    # Ledger-only rows: bookkeeping entries with no real gateway transaction
    # behind them at all -> guaranteed true exceptions on the ledger side.
    base_date = transactions[0]["created_at"] if transactions else None
    for _ in range(extra_ledger_only_rows):
        row = {
            "ledger_id": f"LDG{ledger_id_counter:05d}",
            "reference_id": "",
            "amount": round(random.uniform(200, 5000), 2),
            "date": (base_date + timedelta(days=random.randint(0, 29))).date().isoformat()
            if base_date else None,
            "description": random.choice(FAKE_VENDOR_LABELS),
            "vendor_contact": "",
        }
        ledger_rows.append(row)
        ledger_truth.append({
            "ledger_id": row["ledger_id"],
            "true_payment_id": None,
            "noise_type": "ledger_only_no_counterpart",
        })
        ledger_id_counter += 1

    random.shuffle(ledger_rows)

    ground_truth = {
        "ledger_truth": ledger_truth,
        "unmatched_payment_ids": unmatched_payment_ids,
    }
    return ledger_rows, ground_truth
