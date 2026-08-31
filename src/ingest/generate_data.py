"""CLI entry point: generate synthetic payments + settlements + noisy
internal ledger, write them to data/generated/, and print a summary.

Run from the project root:
    python -m src.ingest.generate_data
"""

import argparse
from pathlib import Path

import pandas as pd

from src.ingest.razorpay_style_generator import generate_payments, generate_settlements
from src.ingest.synthetic_ledger import generate_ledger

OUTPUT_DIR = Path("data/generated")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic reconciliation data.")
    parser.add_argument("-n", "--num-transactions", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--extra-ledger-only", type=int, default=4)
    args = parser.parse_args()

    payments = generate_payments(n=args.num_transactions, seed=args.seed)
    settlements = generate_settlements(payments, seed=args.seed)
    ledger_rows, ground_truth = generate_ledger(
        payments, seed=args.seed, extra_ledger_only_rows=args.extra_ledger_only
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payments_df = pd.DataFrame(payments)
    settlements_df = pd.DataFrame(settlements)
    ledger_df = pd.DataFrame(ledger_rows)
    truth_df = pd.DataFrame(ground_truth["ledger_truth"])

    payments_df.to_csv(OUTPUT_DIR / "payments.csv", index=False)
    settlements_df.to_csv(OUTPUT_DIR / "settlements.csv", index=False)
    ledger_df.to_csv(OUTPUT_DIR / "internal_ledger.csv", index=False)
    truth_df.to_csv(OUTPUT_DIR / "ground_truth.csv", index=False)
    pd.Series(ground_truth["unmatched_payment_ids"], name="payment_id").to_csv(
        OUTPUT_DIR / "ground_truth_unmatched_payments.csv", index=False
    )

    print(f"Payments (synthetic, Razorpay-schema): {len(payments_df)}  -> {OUTPUT_DIR / 'payments.csv'}")
    print(f"Settlements (synthetic, Razorpay-schema): {len(settlements_df)}  -> {OUTPUT_DIR / 'settlements.csv'}")
    print(f"Internal ledger rows: {len(ledger_df)}  -> {OUTPUT_DIR / 'internal_ledger.csv'}")
    print(f"Ground truth rows:    {len(truth_df)}  -> {OUTPUT_DIR / 'ground_truth.csv'}")
    print(f"Payments with NO ledger row at all: {len(ground_truth['unmatched_payment_ids'])}")
    print()
    print("Noise type breakdown (ledger rows):")
    print(truth_df["noise_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
