# Progress Log

Read this file first at the start of every session — it's the single source of truth for where the project stands.

**Project:** Multi-Source Reconciliation + Exception Intelligence Engine
**Buildathon:** Razorpay AI Buildathon 2026, Track 04 (AI Finance Controller)
**Deadline:** Applications close September 5, 2026
**Goal:** Agent that closes a finance-ops reconciliation loop across a 50+ record batch, reports match rate + honest exception list.

## Status: Synthetic data generator working. Blocked on git identity + GitHub auth to get first commit pushed.

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

## Next
1. **Blocked on user:** need a name for git commit authorship (only email is set).
2. **Blocked on user:** run `gh auth login` interactively (browser flow — Claude can't do this), then Claude creates the public GitHub repo + pushes first commit.
3. Build Razorpay test-mode API connector (`src/ingest/razorpay_connector.py`) once user's test keys are in `.env` — matches the shape of `synthetic_transactions.py` output so it's a drop-in replacement.
4. 3-stage matching engine (deterministic -> fuzzy -> LLM-assisted) in `src/matching/`.
5. Exception classifier in `src/exceptions/`.
6. Streamlit dashboard in `dashboard/`.
7. Dockerfile + GitHub Actions CI (`.github/workflows/`).
8. README with architecture diagram + metrics, deploy live link.

## How to regenerate synthetic data
```
.venv/Scripts/python.exe -m src.ingest.generate_data -n 80
```
Output goes to `data/generated/` (gitignored — regenerate anytime, don't rely on committed copies).

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
