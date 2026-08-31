# Multi-Source Reconciliation + Exception Intelligence Engine

Built for the Razorpay AI Buildathon 2026 — Track 04 (AI Finance Controller).

Reconciles two synthetic data sources — payments generated to exactly match Razorpay's real
Payments/Settlements API schema, and a noisy synthetic "internal ledger" — using a multi-stage
matching engine (deterministic rules -> fuzzy matching -> LLM-assisted resolution), and reports
match rate plus a classified exception list, scored against a hidden ground truth.

> Full architecture, metrics, and setup instructions land here as the project is built.
> See [PROGRESS.md](PROGRESS.md) for current build status.

## About the data

Both data sources in this project are synthetic — described honestly as such throughout, not
presented as live data:

- **Payments + Settlements**: generated locally by [`src/ingest/razorpay_style_generator.py`](src/ingest/razorpay_style_generator.py),
  using the exact same field names and structure as Razorpay's real Payments/Settlements API
  (`id`, `amount`, `currency`, `status`, `created_at`, `method`, etc. — see
  [razorpay.com/docs/api/payments](https://razorpay.com/docs/api/payments/)). This project doesn't
  call the live Razorpay API — a real dashboard account requires PAN-based KYC, which isn't
  available here. The buildathon brief explicitly permits a "50+ record batch of synthetic data,"
  so this is within spec.
- **Internal ledger**: a synthetic ledger derived from those payments with realistic injected
  noise (typos, date drift, duplicates, amount mismatches, missing reference IDs, fee/tax deltas) —
  see [`src/ingest/synthetic_ledger.py`](src/ingest/synthetic_ledger.py).

## Status

🚧 In progress — matching engine (deterministic + fuzzy stages) built and scored against ground
truth. Next: LLM-assisted stage 3, exception classifier, Streamlit dashboard.
