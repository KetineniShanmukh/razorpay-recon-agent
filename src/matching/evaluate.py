"""Scores the matching engine's output against the hidden ground-truth key.

This is what turns "match rate" from a self-reported number into a measured
one: for every ledger row we know the correct answer (from
synthetic_ledger.generate_ledger), so we can report real accuracy instead of
just "X rows got matched to something."

Duplicate pairs need group-level scoring, not row-level: when a ledger row
is duplicated, ground truth says both physical rows trace back to the same
real payment, but the *correct* reconciliation outcome is to match exactly
one of them and flag the other as a duplicate exception — not literally
match both. So rows sharing a true_payment_id are scored as a group: correct
if exactly one of them ended up matched and the rest ended up unresolved.
"""


def evaluate(results: list[dict], ground_truth: dict) -> dict:
    truth = {t["ledger_id"]: t for t in ground_truth["ledger_truth"]}
    results_by_id = {r["ledger_id"]: r for r in results}

    # Group ledger rows by the real payment they trace back to (covers duplicate pairs).
    groups: dict[str, list[str]] = {}
    for ledger_id, t in truth.items():
        if t["true_payment_id"] is not None:
            groups.setdefault(t["true_payment_id"], []).append(ledger_id)

    correct_matches = 0
    correctly_flagged_duplicate = 0
    incorrectly_unresolved = 0
    wrong_matches = 0
    mistakes = []

    for payment_id, ledger_ids in groups.items():
        matched_ids = [lid for lid in ledger_ids if results_by_id[lid]["payment_id"] == payment_id]

        if len(matched_ids) == 1:
            correct_matches += 1
            correctly_flagged_duplicate += len(ledger_ids) - 1
        elif len(matched_ids) == 0:
            incorrectly_unresolved += len(ledger_ids)
            for lid in ledger_ids:
                mistakes.append({
                    **results_by_id[lid], "true_payment_id": payment_id, "error_type": "missed_match",
                })
        else:
            # More than one ledger row claims the same true payment as matched —
            # a conflict-resolution bug, since the engine is supposed to enforce 1:1.
            wrong_matches += len(matched_ids)
            for lid in matched_ids:
                mistakes.append({
                    **results_by_id[lid], "true_payment_id": payment_id,
                    "error_type": "duplicate_conflict_not_resolved",
                })

    correctly_left_unresolved = 0
    false_positive_matches = 0
    for ledger_id, t in truth.items():
        if t["true_payment_id"] is not None:
            continue  # already scored above
        r = results_by_id[ledger_id]
        if r["payment_id"] is None:
            correctly_left_unresolved += 1
        else:
            false_positive_matches += 1
            mistakes.append({**r, "true_payment_id": None, "error_type": "false_positive"})

    total = len(results)
    total_correct = correct_matches + correctly_flagged_duplicate + correctly_left_unresolved
    accuracy = round(total_correct / total, 4) if total else 0.0

    return {
        "total_ledger_rows": total,
        "correct_matches": correct_matches,
        "correctly_flagged_duplicate": correctly_flagged_duplicate,
        "correctly_left_unresolved": correctly_left_unresolved,
        "incorrectly_unresolved": incorrectly_unresolved,
        "wrong_matches": wrong_matches,
        "false_positive_matches": false_positive_matches,
        "overall_accuracy": accuracy,
        "mistakes": mistakes,
    }
