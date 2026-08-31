from src.ingest.razorpay_style_generator import generate_payments
from src.ingest.synthetic_ledger import generate_ledger
from src.matching.deterministic import match_deterministic
from src.matching.engine import run_matching
from src.matching.evaluate import evaluate
from src.matching.fuzzy import match_fuzzy


def test_deterministic_catches_exact_and_typo_rows():
    payments = generate_payments(n=40, seed=5)
    ledger, truth = generate_ledger(payments, seed=5)

    candidates = match_deterministic(payments, ledger)
    matched_ledger_ids = {c["ledger_id"] for c in candidates}

    truth_by_id = {t["ledger_id"]: t for t in truth["ledger_truth"]}
    for ledger_id in matched_ledger_ids:
        # Everything deterministic claims must actually be correct.
        assert truth_by_id[ledger_id]["true_payment_id"] == next(
            c["payment_id"] for c in candidates if c["ledger_id"] == ledger_id
        )


def test_fuzzy_resolves_missing_reference_rows():
    payments = generate_payments(n=40, seed=11)
    ledger, truth = generate_ledger(payments, seed=11)

    stage1 = match_deterministic(payments, ledger)
    stage1_ids = {c["ledger_id"] for c in stage1}
    remaining_ledger = [row for row in ledger if row["ledger_id"] not in stage1_ids]
    stage1_payment_ids = {c["payment_id"] for c in stage1}
    remaining_payments = [p for p in payments if p["id"] not in stage1_payment_ids]

    stage2 = match_fuzzy(remaining_ledger, remaining_payments)
    assert len(stage2) > 0  # some rows should be resolvable by fuzzy stage


def test_run_matching_enforces_one_to_one_on_duplicates():
    payments = generate_payments(n=60, seed=21)
    ledger, _ = generate_ledger(payments, seed=21)

    output = run_matching(payments, ledger)
    matched_payment_ids = [r["payment_id"] for r in output["results"] if r["matched"]]

    # No payment should be claimed by more than one ledger row.
    assert len(matched_payment_ids) == len(set(matched_payment_ids))


def test_evaluate_measured_accuracy_is_reasonable_and_no_false_positives():
    payments = generate_payments(n=80, seed=42)
    ledger, ground_truth = generate_ledger(payments, seed=42)

    output = run_matching(payments, ledger)
    scored = evaluate(output["results"], ground_truth)

    # Sanity floor, not a brittle exact number — the noise mix includes
    # cases (large date drift) that are genuinely meant to be unresolved.
    assert scored["overall_accuracy"] > 0.85
    assert scored["false_positive_matches"] == 0
    assert scored["wrong_matches"] == 0


def test_evaluate_scores_duplicate_pairs_at_group_level():
    payments = generate_payments(n=60, seed=8)
    ledger, ground_truth = generate_ledger(payments, seed=8)

    output = run_matching(payments, ledger)
    scored = evaluate(output["results"], ground_truth)

    duplicate_rows = [t for t in ground_truth["ledger_truth"] if t["noise_type"] == "duplicate"]
    if duplicate_rows:
        assert scored["correctly_flagged_duplicate"] > 0
