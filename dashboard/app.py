"""Streamlit dashboard: generate or upload data -> run the reconciliation
pipeline -> view results, exceptions, and (optionally) the stage-3 audit
trail -> download a report.

Run from the project root:
    streamlit run dashboard/app.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.exceptions.classifier import classify_exceptions, summarize_exceptions
from src.ingest.razorpay_style_generator import generate_payments
from src.ingest.synthetic_ledger import generate_ledger
from src.matching.engine import run_matching
from src.matching.evaluate import evaluate
from src.matching.llm_resolve import resolve_with_llm
from src.reporting.loaders import load_ledger_csv, load_payments_csv
from src.reporting.report import build_summary_text, results_to_dataframe

load_dotenv()

st.set_page_config(
    page_title="Reconciliation + Exception Intelligence Engine",
    page_icon="🧾",
    layout="wide",
)

st.markdown(
    """
    <style>
    div[data-testid="stMetric"] {
        background-color: #141B2D;
        border: 1px solid #2A3350;
        border-radius: 10px;
        padding: 14px 16px 10px 16px;
    }
    div[data-testid="stMetricValue"] { color: #A5B4FC; }
    .badge-row { margin: 4px 0 18px 0; }
    .badge {
        display: inline-block;
        background-color: #1E2740;
        color: #A5B4FC;
        border: 1px solid #363F63;
        border-radius: 999px;
        padding: 4px 12px;
        margin-right: 8px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_anthropic_key() -> str | None:
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    return os.getenv("ANTHROPIC_API_KEY")


@st.cache_data
def _generate_demo_data(n: int, seed: int):
    payments = generate_payments(n=n, seed=seed)
    ledger, ground_truth = generate_ledger(payments, seed=seed)
    return payments, ledger, ground_truth


for key in ["payments", "ledger", "ground_truth", "results", "audit_log"]:
    if key not in st.session_state:
        st.session_state[key] = None

st.title("🧾 Multi-Source Reconciliation + Exception Intelligence Engine")
st.caption(
    "Reconciles synthetic Razorpay-schema payments against a noisy internal ledger using a "
    "3-stage matching engine (deterministic → fuzzy → LLM-assisted), then reports an honest, "
    "classified exception list. Built for the Razorpay AI Buildathon 2026 · Track 04 "
    "(AI Finance Controller)."
)
st.markdown(
    """
    <div class="badge-row">
        <span class="badge">⚡ 3-Stage Matching</span>
        <span class="badge">🤖 LLM-Assisted Resolution</span>
        <span class="badge">✅ Ground-Truth Scored</span>
        <span class="badge">🔍 Honest Exception List</span>
    </div>
    """,
    unsafe_allow_html=True,
)

how_cols = st.columns(3)
with how_cols[0]:
    st.markdown("**① Ingest**")
    st.caption("Synthetic payments + a noisy internal ledger, styled after Razorpay's real API schema.")
with how_cols[1]:
    st.markdown("**② Match**")
    st.caption("Deterministic → fuzzy → LLM-assisted, cheapest and most confident first.")
with how_cols[2]:
    st.markdown("**③ Explain**")
    st.caption("Every unresolved row gets a real, classified reason — never a bare \"unresolved.\"")

st.divider()
st.header("📥 1. Data")
data_source = st.radio(
    "Choose a data source", ["Generate synthetic demo data", "Upload my own CSV files"], horizontal=True,
)

if data_source == "Generate synthetic demo data":
    col1, col2 = st.columns(2)
    n = col1.number_input("Number of payments", min_value=50, max_value=500, value=80, step=10)
    seed = col2.number_input("Random seed", min_value=0, value=42, step=1)
    if st.button("Generate data"):
        payments, ledger, ground_truth = _generate_demo_data(int(n), int(seed))
        st.session_state.payments = payments
        st.session_state.ledger = ledger
        st.session_state.ground_truth = ground_truth
        st.session_state.results = None
        st.session_state.audit_log = None
        st.success(f"Generated {len(payments)} payments and {len(ledger)} ledger rows.")
else:
    st.caption(
        "Payments CSV must match Razorpay's real payment schema (`id`, `amount`, `currency`, "
        "`status`, `created_at`, ...). Ledger CSV needs: `ledger_id`, `reference_id`, `amount`, "
        "`date`, `description`, `vendor_contact`. Generate a demo dataset first if you want a "
        "reference for the exact format."
    )
    payments_file = st.file_uploader("Payments CSV", type="csv")
    ledger_file = st.file_uploader("Internal ledger CSV", type="csv")
    if payments_file and ledger_file and st.button("Load files"):
        try:
            payments = load_payments_csv(payments_file)
            ledger = load_ledger_csv(ledger_file)
            st.session_state.payments = payments
            st.session_state.ledger = ledger
            st.session_state.ground_truth = None  # honest: no ground truth for real uploads
            st.session_state.results = None
            st.session_state.audit_log = None
            st.success(f"Loaded {len(payments)} payments and {len(ledger)} ledger rows.")
        except Exception as e:
            st.error(f"Couldn't parse the uploaded files: {e}")

if st.session_state.payments is not None:
    with st.expander("Preview loaded data"):
        pcol, lcol = st.columns(2)
        pcol.write("Payments (first 10)")
        pcol.dataframe(pd.DataFrame(st.session_state.payments).head(10))
        lcol.write("Internal ledger (first 10)")
        lcol.dataframe(pd.DataFrame(st.session_state.ledger).head(10))

st.divider()
st.header("⚙️ 2. Run reconciliation")

api_key = get_anthropic_key()
use_llm = st.checkbox(
    "Also run stage 3 (LLM-assisted resolution)",
    value=False,
    disabled=api_key is None,
    help=(
        "Uses Claude to resolve ambiguous/near-miss exceptions with logged reasoning. "
        "Costs a small number of API calls (a few cents at most for a typical batch)."
        if api_key else
        "No ANTHROPIC_API_KEY found - set it in .env (local) or Streamlit secrets (deployed) to enable this."
    ),
)

run_disabled = st.session_state.payments is None
if st.button("Run reconciliation", disabled=run_disabled, type="primary"):
    with st.spinner("Running stages 1 + 2 (deterministic + fuzzy matching)..."):
        output = run_matching(st.session_state.payments, st.session_state.ledger)
        classified = classify_exceptions(output["results"], st.session_state.payments, st.session_state.ledger)

    audit_log = None
    if use_llm and api_key:
        with st.spinner("Running stage 3 (LLM-assisted resolution)..."):
            try:
                classified, audit_log = resolve_with_llm(
                    classified, st.session_state.payments, st.session_state.ledger,
                    output["unmatched_payment_ids"],
                )
            except Exception as e:
                st.warning(f"Stage 3 failed partway through - showing stages 1+2 results only. Error: {e}")

    st.session_state.results = classified
    st.session_state.audit_log = audit_log
    st.success("Reconciliation complete.")

if st.session_state.results is not None:
    results = st.session_state.results
    ledger = st.session_state.ledger

    st.divider()
    st.header("📊 3. Results")

    n_total = len(results)
    n_matched = sum(1 for r in results if r["matched"])
    match_rate = n_matched / n_total if n_total else 0.0

    metric_cols = st.columns(4)
    metric_cols[0].metric("Ledger rows", n_total)
    metric_cols[1].metric("Match rate", f"{match_rate:.1%}")

    scored = None
    if st.session_state.ground_truth is not None:
        scored = evaluate(results, st.session_state.ground_truth)
        metric_cols[2].metric("Measured accuracy (vs ground truth)", f"{scored['overall_accuracy']:.1%}")
    else:
        metric_cols[2].metric("Measured accuracy", "N/A")
        metric_cols[2].caption("No ground truth for uploaded data - only demo data can be scored.")

    metric_cols[3].metric("Unresolved", n_total - n_matched)

    results_df = results_to_dataframe(results, ledger)

    st.subheader("📋 Results table")
    filter_choice = st.selectbox("Show", ["All rows", "Matched only", "Exceptions only"])
    if filter_choice == "Matched only":
        display_df = results_df[results_df["matched"]]
    elif filter_choice == "Exceptions only":
        display_df = results_df[~results_df["matched"]]
    else:
        display_df = results_df
    st.dataframe(display_df, use_container_width=True)

    st.subheader("🔍 Exception list")
    exception_summary = summarize_exceptions(results)
    if exception_summary:
        st.bar_chart(pd.Series(exception_summary, name="count"))
        st.dataframe(
            results_df[~results_df["matched"]][["ledger_id", "exception_type", "explanation"]],
            use_container_width=True,
        )
    else:
        st.info("No exceptions - every ledger row was resolved.")

    if st.session_state.audit_log:
        st.subheader("🤖 Stage 3 audit trail")
        st.caption("Every LLM call's full prompt, raw response, and reasoning - not just the final verdict.")
        for entry in st.session_state.audit_log:
            with st.expander(f"{entry['ledger_id']} - {entry['decision']} (confidence: {entry['confidence']})"):
                st.write(f"**Reasoning:** {entry['reasoning']}")
                st.write(f"**Candidates shown:** {entry['candidates_shown']}")
                st.code(entry["prompt"], language="text")

    st.divider()
    st.header("📦 4. Download report")
    dl_cols = st.columns(3)
    dl_cols[0].download_button(
        "Download full results (CSV)",
        results_df.to_csv(index=False),
        file_name="reconciliation_results.csv",
        mime="text/csv",
    )
    dl_cols[1].download_button(
        "Download exceptions only (CSV)",
        results_df[~results_df["matched"]].to_csv(index=False),
        file_name="reconciliation_exceptions.csv",
        mime="text/csv",
    )
    dl_cols[2].download_button(
        "Download summary report (TXT)",
        build_summary_text(results, ledger, scored),
        file_name="reconciliation_summary.txt",
        mime="text/plain",
    )
