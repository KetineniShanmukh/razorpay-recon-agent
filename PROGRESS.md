# Progress Log

Read this file first at the start of every session — it's the single source of truth for where the project stands.

**Project:** Multi-Source Reconciliation + Exception Intelligence Engine
**Buildathon:** Razorpay AI Buildathon 2026, Track 04 (AI Finance Controller)
**Deadline:** Applications close September 5, 2026
**Goal:** Agent that closes a finance-ops reconciliation loop across a 50+ record batch, reports match rate + honest exception list.

## Status: Matching engine (stages 1+2) built, tested, and scored against ground truth with real measured accuracy. Next: Razorpay API connector, stage 3 (LLM), exception classifier, or dashboard.

## Done
- Confirmed git, Python 3.14, GitHub CLI (gh 2.98.0) installed on the machine.
- Folder structure created: `src/ingest`, `src/matching`, `src/reporting`, `src/exceptions`, `dashboard`, `tests`, `docs`, `.github/workflows`.
- `.gitignore`, `.env.example`, `requirements.txt`, `README.md` skeleton created.
- git repo initialized locally (not yet pushed to GitHub — no remote yet).
- `.venv` created (use `py -3`, NOT `python` — see Decisions below) and all deps installed.
- **Synthetic data generator built and verified working:**
  - `src/ingest/synthetic_transactions.py` — generates N synthetic "gateway" transactions shaped like real Razorpay Payment objects (payment_id, order_id, amount in paise, currency, status, method, description, contact, created_at, fee, tax). This is a stand-in for the real API and will be swapped later without changing downstream code.
  - `src/ingest/synthetic_ledger.py` — derives a noisy "internal ledger" from those transactions: typos, date drift, duplicate rows, amount mismatches, missing reference IDs, rows with no counterpart on either side. Also returns a **ground-truth answer key** (ledger row -> true payment_id + noise type applied, kept separate from the matching engine's input) so match-rate accuracy can be *measured*, not eyeballed.
  - `src/ingest/generate_data.py` — CLI (`python -m src.ingest.generate_data -n 80`) that runs both and writes CSVs to `data/generated/` (gitignored) + prints a noise-type breakdown.
  - `tests/test_synthetic_data.py` — 4 tests, all passing (shape/count checks, seed reproducibility, ground-truth consistency, missing-counterpart correctness).
  - Verified end-to-end: 80 transactions -> 85 ledger rows (dupes add rows) -> 3 payments with zero ledger row -> noise breakdown looked realistic on manual inspection (e.g. "Payment fo rWarner-Nelson" typo, date drift, amount mismatch all present).

- GitHub repo created and pushed: https://github.com/KetineniShanmukh/razorpay-recon-agent (public, `main` branch, first commit in).
- Git identity: `Shanmukh Ketineni <annu.ketineni@gmail.com>` (matches GitHub account KetineniShanmukh), scoped to this repo only.
- `gh` authenticated as KetineniShanmukh.

- **Matching engine (stages 1 + 2) built, tested, and scored honestly:**
  - `src/matching/deterministic.py` — Stage 1: exact match on reference ID + amount (tight tolerance) + date within a 1-day window. Confidence always 1.0.
  - `src/matching/fuzzy.py` — Stage 2: two passes. Pass A retries rows with a reference ID stage 1 rejected, using widened tolerance (6% amount, 5-day window). Pass B handles rows with no usable reference ID at all, searching candidates by amount/date proximity and disambiguating via `rapidfuzz` description similarity (threshold 75/100, refuses to guess if top-2 candidates score within 5 points of each other).
  - `src/matching/engine.py` — orchestrator. Runs stage 1 then stage 2 on what's left, enforces one-payment-can-only-be-claimed-once (conflict resolution — the loser in a tie becomes a `likely_duplicate` exception), returns per-ledger-row verdicts + list of payments nobody claimed. Stage 3 (LLM) is a documented stub, not wired in yet.
  - `src/matching/evaluate.py` — scores engine output against the hidden ground truth. **Duplicate pairs are scored at group level, not row level**: ground truth says both copies of a duplicated row trace to the same real payment, but the *correct* behavior is to match one and flag the other — so we check "was exactly one of the pair matched and the rest correctly flagged," not "did the engine pick the specific row we arbitrarily generated first."
  - `src/matching/run_eval.py` — CLI that runs the full pipeline on fresh synthetic data and prints an honest report (match rate, measured accuracy, per-stage breakdown, and every individual mistake).
  - `tests/test_matching.py` — 5 tests, all passing.
  - **Important finding, acted on immediately:** first version scored 100% accuracy across 8 different random seeds. That's a red flag, not a win — it meant matching tolerances were suspiciously well-matched to the noise ranges (both designed by the same code). Added two new noise types to `synthetic_ledger.py` that stages 1+2 genuinely cannot resolve on their own: `large_date_drift` (6-10 days, beyond both stages' date windows — real misses, motivates stage 3) and `currency_fee_delta` (ledger records net-of-fee amount instead of gross — matches the buildathon's named "currency/fee delta" exception category). Re-tested across 8 seeds: **measured accuracy now varies 93-99%, with real, non-cherry-picked mistakes every run** — this is the honest signal the buildathon scoring bar wants.
  - Fixed a cosmetic bug: em dashes in printed output showed as `�` in Windows terminals (console codepage) — replaced with `-` in user-facing print/reason strings.

## Next
1. Build Razorpay test-mode API connector (`src/ingest/razorpay_connector.py`) once user's test keys are in `.env` — matches the shape of `synthetic_transactions.py` output so it's a drop-in replacement.
2. Stage 3: LLM-assisted resolution for anything stage 1+2 leave unresolved, with reasoning logged as an audit trail — needs an Anthropic/OpenAI key in `.env`.
3. Exception classifier in `src/exceptions/` — tag every unresolved record with why (amount mismatch, missing counterpart, likely duplicate, currency/fee delta). Much of the raw signal already exists in `engine.py`'s output (e.g. `exception_type: "likely_duplicate"` is already set for conflict losers) — this module mainly needs to classify the plain `"unresolved"` rows.
4. Streamlit dashboard in `dashboard/`.
5. Dockerfile + GitHub Actions CI (`.github/workflows/`).
6. README with architecture diagram + metrics, deploy live link.

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
- Repo will be public on GitHub (required for buildathon submission visibility).
- Matching engine is 3 stages: exact rules -> fuzzy tolerance -> LLM-assisted for anything still ambiguous, with reasoning logged as audit trail.
- Working in small scoped sessions (user has limited hours/day) — always leave this file updated at end of session.
- On this machine, plain `python` on PATH resolves to a broken Windows Store alias stub. Always use `py -3` (the launcher) or the venv's own `.venv/Scripts/python.exe` directly — never bare `python`.
- Synthetic gateway transactions carry amount in paise (int), matching real Razorpay's smallest-unit convention; the derived internal ledger stores amount in rupees (float) — this mismatch is intentional, it's the kind of unit friction a real internal ledger has and the matching engine must normalize it.
- Ground truth (which ledger row maps to which real payment, and what noise was injected) is generated but deliberately kept out of the matching engine's input — it's only used afterwards to score real accuracy. Buildathon scoring explicitly wants "measured accuracy," not a self-reported one.
- Deadline context: applications for the Razorpay AI Buildathon close September 5, 2026 (~13 days out as of 2026-08-23).

## Open questions / blockers
- Git commit author name not yet set (only email is) — asked user, awaiting answer.
- `gh auth login` requires an interactive browser flow the user must run themselves; Claude will create the GitHub repo + push once authenticated.
- Razorpay test-mode keys: user has them, will add to local `.env` (never in chat, never committed).
