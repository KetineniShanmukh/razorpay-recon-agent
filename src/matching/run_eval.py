"""Runs the full matching pipeline against a freshly generated synthetic
dataset and reports measured accuracy against the hidden ground truth.

    python -m src.matching.run_eval -n 80
"""

import argparse

from src.ingest.synthetic_ledger import generate_ledger
from src.ingest.synthetic_transactions import generate_transactions
from src.matching.engine import run_matching
from src.matching.evaluate import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the matching engine and score it against ground truth.")
    parser.add_argument("-n", "--num-transactions", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    transactions = generate_transactions(n=args.num_transactions, seed=args.seed)
    ledger, ground_truth = generate_ledger(transactions, seed=args.seed)

    output = run_matching(transactions, ledger)
    scored = evaluate(output["results"], ground_truth)

    print(f"Ledger rows:                  {scored['total_ledger_rows']}")
    print(f"Engine match rate:            {output['stats']['match_rate']:.1%}")
    print(f"Measured accuracy (vs truth): {scored['overall_accuracy']:.1%}")
    print()
    print("Breakdown:")
    print(f"  Correct matches:                 {scored['correct_matches']}")
    print(f"  Correctly flagged as duplicate:  {scored['correctly_flagged_duplicate']}")
    print(f"  Correctly left unresolved:       {scored['correctly_left_unresolved']}")
    print(f"  Missed matches (had an answer, engine found none): {scored['incorrectly_unresolved']}")
    print(f"  Wrong matches (matched the wrong payment):          {scored['wrong_matches']}")
    print(f"  False positives (matched something that shouldn't have): {scored['false_positive_matches']}")
    print()
    print("Matches by stage:")
    for stage, count in output["stats"]["by_stage"].items():
        print(f"  {stage}: {count}")

    if scored["mistakes"]:
        print()
        print(f"{len(scored['mistakes'])} mistake(s) - honest list, not cherry-picked:")
        for m in scored["mistakes"]:
            print(
                f"  [{m['error_type']}] ledger={m['ledger_id']} engine_said={m['payment_id']} "
                f"truth={m['true_payment_id']} reason={m['reason']}"
            )
    else:
        print()
        print("No mistakes on this run.")


if __name__ == "__main__":
    main()
