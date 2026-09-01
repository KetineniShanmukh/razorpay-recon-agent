# Understanding This Project — Plain English

Read this like you're being taught it, not tested on it. Every section builds on the last. By the
end you should be able to explain any part of this project to someone else in your own words —
that's the actual goal, not memorizing this document.

## The 30-second version

Two spreadsheets should agree with each other but don't. One is a bank/payment gateway's record
of transactions; the other is a company's own internal bookkeeping. In real life they never match
perfectly — typos, late entries, duplicate rows, small fee deductions. Someone has to manually go
through both and figure out what matches what, and flag what doesn't. This project builds an
automated agent that does that matching, tells you how confident it is, and — critically — is
honest about what it *couldn't* figure out and why.

## Why this matters (the actual business problem)

Every company that processes payments has to "reconcile" — prove that the money the gateway says
moved actually shows up correctly in their own books. Right now, a lot of that is done by a human
staring at two CSVs. It's slow, error-prone, and doesn't scale. If you can get a machine to
confidently close 90%+ of that loop automatically and hand a human a short, well-explained list of
the genuinely ambiguous cases, you've turned a full-time job into a 10-minute review.

## The data — and why it's synthetic

**What we needed:** two data sources that structurally *look* like a real payment gateway and a
real internal ledger, but that we could control precisely enough to know the "correct answer" in
advance (so we can grade our own system honestly).

**Why not real Razorpay data:** creating a real Razorpay account (even test mode) requires PAN-card
KYC verification, which isn't available here. Rather than skip this or fake it silently, this is
disclosed openly: the project generates payment records using the *exact same field structure* as
Razorpay's real API (same field names, same data types, same conventions like amounts stored in
paise). If you plugged in a real Razorpay API connection tomorrow, nothing downstream would need to
change — the shape is identical, only the source changed. The buildathon's own rules explicitly
allow a "50+ record synthetic batch," so this isn't a workaround, it's within the stated spec.

**The internal ledger** is then *derived* from those payments by deliberately breaking them in
realistic ways: typos in descriptions, dates recorded a few days late, amounts slightly off
(sometimes because of a fee deduction), duplicate entries, and rows referencing a payment ID that's
been left blank or garbled. Some ledger rows also just don't exist for a payment (a payment happened,
nobody logged it), and some logged rows don't correspond to any real payment at all (a bookkeeping
mistake). This is what makes the dataset realistic instead of a toy example where everything trivially
matches.

**The secret ingredient — ground truth.** While generating the noisy ledger, the code *also*
secretly records the correct answer for every single row (which payment it really came from, and
what kind of noise was applied) — but this answer key is never shown to the matching engine. It's
kept completely separate, used only afterward to grade the engine's actual output. This is the
difference between saying "we think we got it right" and "we can prove exactly how often we got it
right, and exactly where we didn't." That second thing is what a judge actually wants to see.

## The matching engine — three stages, cheapest first

Think of it like airport security lanes: an easy, fast, high-confidence check first; a slower,
more careful check for anyone who didn't clear the first; and a human (here, an LLM) making a
judgment call only on the handful of genuinely unclear cases left at the end. You never want the
expensive step doing work the cheap step could've done.

**Stage 1 — Deterministic (the fast lane).** If a ledger row's reference ID exactly matches a real
payment ID, *and* the amount matches almost exactly, *and* the date is within 1 day — it's an
instant, 100%-confidence match. No guessing involved. This alone resolves most of the dataset,
including every row with just a typo in the description, because this stage doesn't even look at
the description — reference ID + amount + date is enough.

**Stage 2 — Fuzzy (the careful lane).** Two things happen here, only for rows stage 1 couldn't
resolve:
- If a row *has* a reference ID but got rejected (amount slightly off, date a few days later),
  retry with a wider tolerance (up to 6% amount difference, 5-day window).
- If a row has *no* reference ID at all, search every unclaimed payment for one with a similar
  amount, similar date, and a similar-sounding description (using fuzzy text matching — the same
  idea as "did you mean...?" spell-check). If two candidates are too close in similarity to
  confidently pick one, this stage refuses to guess — it leaves the row unresolved rather than
  risk a wrong match. **That refusal-to-guess is a deliberate design choice, not a gap** — a wrong
  automated match is worse than an honest "I don't know."

**Conflict resolution.** If two different ledger rows both plausibly point at the same one
payment (this happens with duplicate ledger entries), only one is allowed to "win" the match — the
other is automatically flagged as a likely duplicate exception instead of both being silently
counted as correct.

**Stage 3 — LLM-assisted (the judgment call).** Whatever's still unresolved after stages 1 and 2
gets handed to Claude, one row at a time, along with the 1-3 most plausible candidate payments and
the reason the rule-based system couldn't decide. Claude has to return a decision *and* a written
reason — this is what "reasoning logged as an audit trail" means in the brief: every single
LLM decision is fully inspectable, not a black box. This stage is genuinely useful specifically
*because* it can apply judgment rules aren't good at, like "a payment recorded 9 days later than
usual, with the exact same amount and reference ID, is probably just a late bookkeeping entry, not
a coincidence."

## The exception classifier

For everything that's still not matched even after all three stages, this module answers "why
not?" with a specific, human-readable reason, not just "unresolved." The categories: amount
doesn't match, no payment exists behind this row at all (`missing_counterpart`), it's a duplicate
of another row, the amount gap looks like a fee deduction (`currency_fee_delta`), or — for two
bonus categories added beyond what the brief strictly asked for — only the date is off
(`date_drift`), or multiple candidates are genuinely too close to call (`ambiguous_match`). This is
what turns a bare "8 rows didn't match" into an actual, useful report a human can act on in minutes.

## Why the accuracy numbers can be trusted

Early in building this, the very first version of the matching engine scored a suspicious **100%**
accuracy across eight different random test runs. That's not something to be proud of — it meant
the matching tolerances happened to be tuned to exactly the kind of noise being generated, since
the same person (well, the same AI-assisted session) built both. A real judge would rightly be
suspicious of a perfect score. So two harder noise types were deliberately added — noise wide
enough that the rules genuinely cannot resolve it — specifically to force real, non-cherry-picked
failures into the numbers. After that change: **93.1%–98.9% accuracy across 9 different seeds,
average ~96.1%**, with a real, different mistake list every single run. That volatility is a
feature, not a bug — it's what makes the number honest.

## The dashboard

A Streamlit web app: generate a fresh synthetic dataset (or upload your own two CSVs), click Run,
and see the full results — a filterable table, an exception breakdown chart, and (if you enable
it) the full stage-3 reasoning for every LLM decision, plus one-click downloads. One deliberate
honesty detail: the "measured accuracy" number only appears when there's a ground-truth answer key
to check against — which only exists for generated demo data. If you upload your own real files,
it correctly says "N/A" instead of making up a number it can't actually verify.

## Docker and CI — why they exist at all

Docker packages the code and every dependency it needs into one self-contained unit that runs
identically anywhere, so "it works on my machine" isn't a problem for whoever reviews this.
GitHub Actions (the CI) automatically runs the full test suite *and* actually builds and starts a
real Docker container on every single push to the repo, confirming both the code and the packaging
genuinely work — not just "it built without an error," but "a live container answered a health
check." This is what "fully deployable" means in the brief, proven automatically instead of
claimed.

## Things you built that go beyond the minimum ask

Worth having ready, since these show initiative beyond the checklist:
- Two bonus exception categories beyond the four the brief named.
- The engine deliberately fails sometimes, on purpose, because a perfect score was a red flag, not
  a win — and you caught that yourself before shipping it.
- A full LLM audit trail (prompt, raw response, reasoning) for every stage-3 decision, not just the
  final verdict.
- Real bugs found and fixed by actually testing live against the real API instead of trusting
  mocks (a token-budget truncation issue, and a rare genuine model refusal) — both now degrade
  safely with a clear explanation instead of crashing or silently failing.
- A CI pipeline that verifies the Docker container actually serves traffic, not just that it built.
