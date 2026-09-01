"""Runs the full matching pipeline against a freshly generated synthetic
dataset and reports measured accuracy against the hidden ground truth.

    python -m src.matching.run_eval -n 80
    python -m src.matching.run_eval -n 80 --use-llm   # also run stage 3 (costs a few API calls)
"""

import argparse
import json
from pathlib import Path

from src.exceptions.classifier import classify_exceptions, summarize_exceptions
from src.ingest.razorpay_style_generator import generate_payments
from src.ingest.synthetic_ledger import generate_ledger
from src.matching.engine import run_matching
from src.matching.evaluate import evaluate
from src.matching.llm_resolve import resolve_with_llm

AUDIT_LOG_PATH = Path("data/generated/stage3_audit_log.json")


def _print_report(label: str, results: list[dict], ground_truth: dict) -> None:
    scored = evaluate(results, ground_truth)
    n_matched = sum(1 for r in results if r["matched"])
    print(f"--- {label} ---")
    print(f"Match rate:                   {n_matched / len(results):.1%}")
    print(f"Measured accuracy (vs truth): {scored['overall_accuracy']:.1%}")
    print(
        f"  correct={scored['correct_matches']} "
        f"correctly_flagged_duplicate={scored['correctly_flagged_duplicate']} "
        f"correctly_unresolved={scored['correctly_left_unresolved']} "
        f"missed={scored['incorrectly_unresolved']} "
        f"wrong={scored['wrong_matches']} "
        f"false_positive={scored['false_positive_matches']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the matching engine and score it against ground truth.")
    parser.add_argument("-n", "--num-transactions", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--use-llm", action="store_true", help="Also run stage 3 (LLM-assisted resolution).")
    args = parser.parse_args()

    payments = generate_payments(n=args.num_transactions, seed=args.seed)
    ledger, ground_truth = generate_ledger(payments, seed=args.seed)

    output = run_matching(payments, ledger)
    classified_results = classify_exceptions(output["results"], payments, ledger)

    print(f"Ledger rows: {len(ledger)}")
    print()
    _print_report("Stages 1+2 (deterministic + fuzzy)", output["results"], ground_truth)

    final_results = classified_results
    if args.use_llm:
        print()
        print("Running stage 3 (LLM-assisted resolution)...")
        final_results, audit_log = resolve_with_llm(
            classified_results, payments, ledger, output["unmatched_payment_ids"],
        )
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        AUDIT_LOG_PATH.write_text(json.dumps(audit_log, indent=2))
        print(f"Stage 3 made {len(audit_log)} LLM call(s) - full audit trail written to {AUDIT_LOG_PATH}")
        print()
        _print_report("Stages 1+2+3 (with LLM-assisted resolution)", final_results, ground_truth)

    exception_summary = summarize_exceptions(final_results)
    total_exceptions = sum(exception_summary.values())
    print()
    print(f"Exception list: {total_exceptions} unresolved row(s), classified by reason:")
    for exception_type, count in exception_summary.items():
        print(f"  {exception_type}: {count}")

    print()
    print("Full exception list (honest - every unresolved row, not cherry-picked):")
    for r in final_results:
        if r["matched"]:
            continue
        print(f"  [{r['exception_type']}] ledger={r['ledger_id']} - {r['explanation']}")

    scored = evaluate(final_results, ground_truth)
    if scored["mistakes"]:
        print()
        print(f"{len(scored['mistakes'])} scoring mistake(s) vs ground truth - honest, not cherry-picked:")
        for m in scored["mistakes"]:
            print(
                f"  [{m['error_type']}] ledger={m['ledger_id']} engine_said={m['payment_id']} "
                f"truth={m['true_payment_id']} reason={m['reason']}"
            )
    else:
        print()
        print("No scoring mistakes on this run (vs ground truth).")


if __name__ == "__main__":
    main()
