# Progress Log

Read this file first at the start of every session — it's the single source of truth for where the project stands.

**Project:** Multi-Source Reconciliation + Exception Intelligence Engine
**Buildathon:** Razorpay AI Buildathon 2026, Track 04 (AI Finance Controller)
**Deadline:** Applications close September 5, 2026
**Goal:** Agent that closes a finance-ops reconciliation loop across a 50+ record batch, reports match rate + honest exception list.

## Status: Matching engine (stages 1+2) working on fully synthetic data. Next: stage 3 (LLM), exception classifier, dashboard.

## Done
- Repo scaffolded: `src/ingest`, `src/matching`, `src/reporting`, `src/exceptions`, `dashboard`, `tests`, `docs`, `.github/workflows`; `.gitignore`, `.env.example`, `requirements.txt`, `README.md`.
- GitHub repo live: https://github.com/KetineniShanmukh/razorpay-recon-agent (public, `main` branch). `gh` authenticated as KetineniShanmukh. Git identity: `Shanmukh Ketineni <annu.ketineni@gmail.com>`.
- `.venv` created (use `py -3`, NOT `python` — see Decisions) and all deps installed.

- **Both data sources are fully synthetic — no real Razorpay API integration.** User doesn't have a PAN card, which is a hard KYC requirement for a real Razorpay dashboard account (even test mode). This isn't a workaround: the buildathon brief explicitly allows a "50+ record batch of synthetic data."
  - `src/ingest/razorpay_style_generator.py` — `generate_payments()` produces synthetic payments with the exact field names/structure of Razorpay's real Payment entity (`id`, `entity`, `amount` in paise, `currency`, `status`, `order_id`, `method`, method-specific fields like `card_id`/`bank`/`wallet`/`vpa`, `created_at` as a Unix timestamp, `fee`, `tax`, etc.). `generate_settlements()` batches captured payments into daily Settlement-entity-shaped records (`id`, `amount`, `fees`, `tax`, `utr`, `created_at`) — generated but **not yet wired into the matching engine** (that reconciles at the payment level); it exists as a second authentic data source matching the "Payments/Settlements" language in the brief.
  - `src/ingest/synthetic_ledger.py` — derives a noisy "internal ledger" from the payments: typos, date drift (including drift wide enough that no matching stage can resolve it), duplicate rows, amount mismatches, fee/tax deltas, missing reference IDs, rows with no counterpart on either side. Also returns a **ground-truth answer key** (kept out of the matching engine's input) so match-rate accuracy can be *measured*, not eyeballed.
  - `src/ingest/generate_data.py` — CLI (`python -m src.ingest.generate_data -n 80`) writes `payments.csv`, `settlements.csv`, `internal_ledger.csv`, `ground_truth.csv` to `data/generated/` (gitignored).
  - (Superseded) `src/ingest/synthetic_transactions.py` — the original generator, used Razorpay-*inspired* field names (`payment_id`, datetime objects) rather than the real API's exact shape. Deleted and replaced by `razorpay_style_generator.py`.

- **Matching engine (stages 1 + 2) built, tested, and scored honestly:**
  - `src/matching/deterministic.py` — Stage 1: exact match on reference ID + amount (tight tolerance) + date within a 1-day window. Confidence always 1.0.
  - `src/matching/fuzzy.py` — Stage 2: two passes. Pass A retries rows with a reference ID stage 1 rejected, using widened tolerance (6% amount, 5-day window). Pass B handles rows with no usable reference ID at all, searching candidates by amount/date proximity and disambiguating via `rapidfuzz` description similarity (threshold 75/100, refuses to guess if top-2 candidates score within 5 points of each other).
  - `src/matching/engine.py` — orchestrator. Runs stage 1 then stage 2 on what's left, enforces one-payment-can-only-be-claimed-once (conflict resolution — the loser in a tie becomes a `likely_duplicate` exception), returns per-ledger-row verdicts + list of payments nobody claimed. Stage 3 (LLM) is a documented stub, not wired in yet.
  - `src/matching/evaluate.py` — scores engine output against the hidden ground truth. **Duplicate pairs are scored at group level, not row level**: ground truth says both copies of a duplicated row trace to the same real payment, but the *correct* behavior is to match one and flag the other — so we check "was exactly one of the pair matched and the rest correctly flagged," not "did the engine pick the specific row we arbitrarily generated first."
  - `src/matching/run_eval.py` — CLI that runs the full pipeline on fresh synthetic data and prints an honest report (match rate, measured accuracy, per-stage breakdown, and every individual mistake).
  - **Important finding, acted on immediately:** first version scored 100% accuracy across 8 different random seeds. That's a red flag, not a win — it meant matching tolerances were suspiciously well-matched to the noise ranges (both designed by the same code). Added two new noise types that stages 1+2 genuinely cannot resolve on their own: `large_date_drift` (6-10 days, beyond both stages' date windows — real misses, motivates stage 3) and `currency_fee_delta` (ledger records net-of-fee amount instead of gross — matches the buildathon's named "currency/fee delta" exception category). Re-tested: **measured accuracy now varies 93-99% across seeds, with real, non-cherry-picked mistakes every run** — this is the honest signal the buildathon scoring bar wants.
  - Fixed a cosmetic bug: em dashes in printed output showed as `�` in Windows terminals (console codepage) — replaced with `-` in user-facing print/reason strings.

- `tests/test_synthetic_data.py` (6 tests) + `tests/test_matching.py` (5 tests) — 11 tests total, all passing.

## Next
1. Stage 3: LLM-assisted resolution for anything stage 1+2 leave unresolved, with reasoning logged as an audit trail — needs an Anthropic/OpenAI key in `.env`.
2. Exception classifier in `src/exceptions/` — tag every unresolved record with why (amount mismatch, missing counterpart, likely duplicate, currency/fee delta). Much of the raw signal already exists in `engine.py`'s output (e.g. `exception_type: "likely_duplicate"` is already set for conflict losers) — this module mainly needs to classify the plain `"unresolved"` rows.
3. Streamlit dashboard in `dashboard/`.
4. Dockerfile + GitHub Actions CI (`.github/workflows/`).
5. README with architecture diagram + metrics, deploy live link.

## How to run things
```bash
# Regenerate synthetic data (writes CSVs to data/generated/, gitignored)
.venv/Scripts/python.exe -m src.ingest.generate_data -n 80

# Run the matching engine end-to-end and print an honest accuracy report
.venv/Scripts/python.exe -m src.matching.run_eval -n 80

# Run the test suite
.venv/Scripts/python.exe -m pytest tests/ -v
```

## Decisions
- Repo is public on GitHub (required for buildathon submission visibility).
- **No real Razorpay API integration — both data sources are synthetic.** User lacks a PAN card, a hard KYC requirement for even a Razorpay test-mode dashboard account. The payments generator matches Razorpay's real API schema field-for-field instead, so the project is honest about being synthetic while still demonstrating the same reconciliation problem a real integration would pose. This is explicitly within the buildathon's stated spec (50+ record synthetic batch).
- Matching engine is 3 stages: exact rules -> fuzzy tolerance -> LLM-assisted for anything still ambiguous, with reasoning logged as audit trail.
- Working in small scoped sessions (user has limited hours/day) — always leave this file updated at end of session.
- On this machine, plain `python` on PATH resolves to a broken Windows Store alias stub. Always use `py -3` (the launcher) or the venv's own `.venv/Scripts/python.exe` directly — never bare `python`.
- Payments carry amount in paise (int) and created_at as a Unix timestamp (int), matching Razorpay's real API conventions exactly; the derived internal ledger stores amount in rupees (float) and date as an ISO string — this mismatch is intentional, it's the kind of unit friction a real internal ledger has and the matching engine must normalize it.
- Ground truth (which ledger row maps to which real payment, and what noise was injected) is generated but deliberately kept out of the matching engine's input — it's only used afterwards to score real accuracy. Buildathon scoring explicitly wants "measured accuracy," not a self-reported one.
- Settlements are generated (schema-authentic) but not yet part of the matching/reconciliation loop — payment-level reconciliation is the core deliverable; settlement-level reconciliation is optional future scope, not required for the "one finance-ops loop" bar.
- Deadline context: applications for the Razorpay AI Buildathon close September 5, 2026 (**4 days out as of 2026-09-01** — tight, prioritize the required deliverables: stage 3, exception classifier, dashboard, deploy link, README — over nice-to-haves like settlement-level matching).

## Open questions / blockers
None currently — data layer and matching engine (stages 1+2) are unblocked and working end to end.
