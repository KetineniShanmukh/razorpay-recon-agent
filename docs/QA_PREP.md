# Q&A Prep

Read each answer, understand the *reasoning* behind it, then close the file and try answering out
loud from memory. If you can't, that's a sign to re-read [EXPLAINER.md](EXPLAINER.md), not to
memorize this verbatim. A judge asking a follow-up will expose memorized-but-not-understood answers
fast — the goal here is that you genuinely know this project, not that you can recite it.

---

## Data & scope

**Q: Why didn't you use the real Razorpay API?**
A real Razorpay dashboard account — even test mode — requires PAN-card KYC verification, which
wasn't available to me. Rather than skip that or fake it silently, I built the payment generator
to exactly match Razorpay's real API schema field-for-field, so a live connection could be dropped
in later with zero changes downstream. The buildathon brief explicitly permits a "50+ record
synthetic batch," so this is within the stated spec, not a workaround — and I say so openly in the
README rather than letting anyone assume it's live data.

**Q: Isn't synthetic data a weaker demo than real data?**
It's actually stronger for proving my system works, for one specific reason: with synthetic data I
control the ground truth. I know exactly which ledger row *should* match which payment, because I
generated both. That's what let me measure real accuracy instead of just eyeballing results — you
can't do that with a random real dataset unless someone's already hand-labeled it.

**Q: How realistic is the noise you injected?**
It's modeled on real reconciliation pain points: typos in descriptions, dates recorded a few days
late, duplicate ledger entries, amount mismatches (including ones that look like a fee deduction),
missing reference IDs, and rows with no counterpart on either side. I didn't just add random
numbers — the fee-delta noise, for example, subtracts the payment's actual fee and tax from the
ledger amount, because that's a real bookkeeping pattern, not arbitrary noise.

**Q: What happens with a batch bigger than 80? Does it still work?**
Yes — the size is a parameter (`-n`), and nothing in the matching logic assumes a specific count.
I tested at 80 because that comfortably clears the brief's "50+" bar with room for the exception
mix to show up meaningfully; I haven't stress-tested at, say, 10,000 rows, and the fuzzy stage's
pairwise candidate search would need optimizing (it's currently not indexed) before that would stay
fast.

---

## Architecture & design decisions

**Q: Why three stages instead of one machine learning model?**
Because each stage is answering a genuinely different kind of question, and mixing them into one
model would throw away information. An exact reference-ID match is a *certainty*, not a
probability — treating it as anything less would be wasteful and would give it artificially lower
confidence than it deserves. A fuzzy amount/date/description match is a *probability judgment* with
tunable tolerances. And a truly ambiguous case — where two candidates are equally plausible — needs
actual reasoning, which is what the LLM stage is for. Cascading from cheap-and-certain to
expensive-and-judgment-based means you only pay the expensive cost on the small number of cases
that actually need it.

**Q: Why does stage 2 sometimes refuse to make a match?**
Because a wrong automated match is worse than an honest "I don't know." If two candidate payments
score within 5 points of each other on description similarity, picking one would just be a coin
flip dressed up as confidence. I'd rather that row surface as an exception a human (or stage 3) can
look at, than silently get matched to the wrong payment and corrupt the books.

**Q: How do you prevent one payment from being matched to two different ledger rows?**
There's an explicit conflict-resolution step after stages 1 and 2 run. If two ledger rows both
claim the same payment — which happens with duplicate entries — only the higher-confidence one
wins; the other is automatically flagged as a `likely_duplicate` exception instead of being
silently counted as a second correct match. Stage 3 preserves this same guarantee: it processes
rows one at a time and removes a payment from the available pool the moment it's claimed, so the
LLM can never double-book a payment either.

**Q: Walk me through what happens to one specific ledger row, end to end.**
Say a row has the right reference ID and amount, but the date is 9 days off. Stage 1 rejects it —
that's outside its 1-day window. Stage 2's reference-tolerance pass also rejects it — 9 days is
past its 5-day window too. It reaches the exception classifier, which recognizes the reference ID
is valid and the amount checks out, so it tags it `date_drift` with an explanation. If stage 3 runs,
Claude sees that row plus the one candidate payment its reference ID points to, and can reason
"exact reference ID, exact amount, date just recorded late — that's the same transaction" and match
it, logging that reasoning. If stage 3 doesn't run, it stays a `date_drift` exception in the final
report, honestly labeled.

**Q: Why Streamlit and not a "real" backend (Flask/FastAPI + a separate frontend)?**
Given the time constraint, Streamlit gets a functional, actually-usable web UI up in one file
instead of building and wiring together a separate API and frontend. For a buildathon submission,
the priority was a working, deployable tool a reviewer can click through in two minutes, not
demonstrating full-stack architecture for its own sake. The matching/classification logic itself is
fully decoupled from the UI (it's plain Python in `src/`, testable and usable from a CLI too) —
swapping the UI layer later wouldn't require touching the actual reconciliation logic.

---

## Accuracy & honesty

**Q: How do you know your accuracy number is real and not made up?**
Because I generate a hidden ground-truth answer key alongside the noisy ledger — which row really
maps to which payment — and I deliberately keep it out of the matching engine's input. It only gets
used afterward, to score what the engine actually produced. That's the difference between a
self-reported match rate ("X% of rows got matched to *something*") and a measured accuracy ("X% of
those matches are actually correct, verified against the real answer").

**Q: You mentioned your first version scored 100% — isn't that a good thing?**
No, and catching that myself is honestly one of the things I'm most proud of in this build. A
perfect score across every test run meant my matching tolerances were suspiciously well-matched to
the noise ranges — unsurprising, since I designed both. A real judge should distrust a perfect
score exactly like the brief warns against ("no cherry-picked demos"). So I added noise wide enough
that the rules genuinely can't resolve it on their own, specifically to force real failures into
the numbers. The accuracy dropped to a 93-99% range that varies by seed — and that volatility is
the point. It's proof the number isn't rigged.

**Q: What's your actual accuracy number, then — pick one?**
Stages 1+2 alone: 93.1% to 98.9% across 9 different random seeds, averaging about 96.1%. Adding
stage 3 (LLM-assisted resolution) closed the remaining gap in every run I tested it on, including
one full run to 100% — because the LLM correctly resolved the genuine near-misses (like the
date-drift case) while correctly leaving true exceptions as exceptions rather than force-matching
them.

**Q: What kinds of mistakes does the system still make?**
In testing, the only category of real miss was `missed_match` — a row that had a genuine correct
answer but neither stage 1 nor 2 found it (typically the wide date-drift noise). I never observed a
false positive (matching something that shouldn't match) or a wrong match (matching to the wrong
payment) across dozens of test runs — the system is conservative by design: it would rather leave a
row unresolved than guess wrong.

---

## The LLM / stage 3

**Q: What exactly is the LLM doing that a rule couldn't?**
Making a judgment call that would require an unboundedly complex rule to capture safely. "This
payment was recorded 9 days later than usual, but the reference ID and amount match exactly" is
easy for a human (or an LLM) to reason about ("that's probably just a late entry"), but hard to
encode as a fixed threshold rule without either being too strict (missing real matches) or too loose
(accepting false ones). The LLM only ever sees the handful of cases stages 1+2 couldn't confidently
resolve — it's not doing bulk classification, it's doing the few genuinely hard calls.

**Q: How do you stop the LLM from hallucinating a match that isn't real?**
A few layers. First, it's only ever shown up to 3 real, already-filtered candidate payments — it
can't invent a payment ID that doesn't exist, because I validate its chosen `payment_id` is actually
one of the candidates I showed it (and still in the pool of unclaimed payments) before accepting
the match. Second, it has to return a reasoning string alongside every decision, which is logged in
full — so even if I disagreed with a call, I could see exactly why it made that choice. Third, if
its response can't be parsed, is empty, or is a refusal, the system treats that as "no match" by
default rather than guessing — it fails safe, not open.

**Q: What actually goes wrong with LLM calls in practice, and how do you handle it?**
I found two real failure modes by testing live against the actual API instead of trusting mocks.
First: the model (Claude Opus 5) runs extended thinking by default, and with too small a token
budget, thinking alone consumed the whole budget and left zero tokens for the actual answer — an
empty response. I fixed that by raising the token limit and lowering the reasoning effort level
(this is a bounded judgment call, not deep multi-step reasoning, so it didn't need maximum effort
anyway). Second: I saw one genuine model refusal on a completely benign reconciliation question —
rare, but real. Both cases already degraded safely (logged as an unresolved exception, no crash, no
forced bad match), but I improved the audit trail to explain the specific cause instead of just
saying "response was empty."

**Q: How much does running stage 3 cost?**
For this dataset size, it's a few cents at most per full run — stage 3 only calls the LLM for the
handful of rows (typically single digits out of 80) that stages 1+2 couldn't resolve, not the whole
batch. It's opt-in in the dashboard specifically because it costs real API calls, and disabled
automatically if no API key is configured.

**Q: Why Claude specifically, and why Opus?**
I used Anthropic's current guidance to default to their most capable model unless there's a reason
to downgrade, and given this task only runs on a handful of rows per batch, the cost difference
between model tiers is negligible — there was no reason to trade quality for savings that don't
meaningfully exist at this volume.

---

## Engineering & deployment

**Q: Walk me through your test coverage.**
31 tests across the whole pipeline: data generation (reproducibility, schema correctness), the
matching engine (each stage's boundary conditions, conflict resolution), the exception classifier
(one hand-crafted test per category, deliberately built to fall outside auto-match tolerance so it
actually reaches the classifier), stage 3 (using a fake Anthropic client — no real API calls, no
cost, no key needed to run the suite), and the CSV upload/report path. None of them need a real API
key, which matters for CI.

**Q: Why does CI matter here — what does it actually verify?**
Two things, on every push: that the full test suite passes, and that the Docker image doesn't just
build without erroring, but that a real container built from it actually starts and answers a
health check on the Streamlit endpoint. That second part is the difference between "the Dockerfile
has no syntax errors" and "this genuinely runs as a deployable service."

**Q: Is Docker running locally on your machine?**
No — Docker Desktop isn't installed locally, and installing it (WSL2, 15-30+ minutes, possibly a
restart) wasn't worth the time cost this close to the deadline. I verified it instead through
GitHub Actions, which has Docker built into its runners — the image genuinely builds and the
container genuinely serves traffic, just proven in CI rather than on my laptop. The live deploy
itself (Streamlit Community Cloud) doesn't use Docker at all — it builds straight from
`requirements.txt`.

**Q: How are your API keys / secrets handled?**
Locally, in a `.env` file that's git-ignored and never committed — `.env.example` in the repo shows
the expected variable names with placeholder values only. On the deployed dashboard, the key lives
in Streamlit Community Cloud's own secrets manager, not in any file in the repo. The dashboard
checks for the key and disables the LLM-stage checkbox entirely if it's missing, rather than
failing partway through a run.

---

## Product / business framing

**Q: Who would actually use this?**
A finance-ops or accounts-reconciliation team at a company processing meaningful payment volume —
anyone currently doing this kind of matching by hand in spreadsheets. The dashboard's upload flow
is built for exactly that: bring your own two files, get a reconciliation report back in seconds.

**Q: What's the actual output someone would walk away with?**
A results table showing every ledger row's resolution status, a classified exception list they can
act on directly (not just "something's wrong," but specifically why), and a downloadable summary
report — CSV or plain text — they could hand to a manager or paste into a ticket.

**Q: What would you build next if you had more time?**
A few things, roughly in priority order: reconciling at the settlement level too (the generator
already produces schema-correct settlement records, just not wired into the matching loop yet);
handling multi-currency reconciliation properly; and batching the stage-3 LLM calls instead of
processing them one at a time, for speed at larger scale.

---

## Personal / growth

**Q: What was the hardest part of building this?**
Being honest about my own system's flaws instead of shipping the flattering number. The 100%
accuracy result felt like success in the moment — catching that it was actually a red flag, and
fixing the underlying data generator instead of just reporting the good-looking number, was the
harder and more valuable call.

**Q: What did you learn building this?**
*(Answer this one genuinely, in your own words — it's the one question no prep doc can answer for
you truthfully. If you want a starting point: think about what surprised you, what you had to debug
live against a real API instead of trusting mocks, and what you understand now about reconciliation
that you didn't going in.)*

**Q: Did you write all the code yourself?**
I worked with Claude (via Claude Code) to build this end to end — I directed the architecture and
design decisions, made the calls on tradeoffs (synthetic vs. real data, which noise types to add,
when to trust vs. distrust a metric), and I'm prepared to explain and defend every part of it, which
is what this whole prep doc is for. I'm not going to overstate hand-writing every line, but I
understand what this system does and why, at a level where I can walk through any part of it or
extend it myself.
