# 5-Minute Pitch Script (Final)

**How to use this:** don't memorize word-for-word — read it a few times, understand *why* each
line is there, then say it in your own words. A judge can tell the difference between reciting
and explaining. Total runtime target: ~4:55, leaving a little buffer under the 5:00 limit.

This version is structured around Razorpay's own published judging criteria (seen on their
buildathon page): **Problem taste, Build quality, AI judgment, Failure recovery.** Each section
below is labeled with which one it's mainly answering — that label is for you, not something to
say out loud.

Fill in your live deploy link before recording if it's not already muscle memory. Practice with a
timer at least twice — first passes almost always run long.

---

## 0:00 – 0:10 — Self-intro (10s)

*(Face to camera.)*

> "Hi, I'm Shanmukh Ketineni, a final-year ECE student, and this is ReconIQ — my submission for
> the AI Finance Controller track."

## 0:10 – 0:35 — Hook · *Problem taste* (25s)

> "Every company that takes payments has to prove their bank records match their internal books.
> In practice, they never line up perfectly — typos, late entries, duplicate rows, small fee
> deductions — and someone has to manually reconcile them by hand. ReconIQ automates that loop,
> and — this is the important part — it's honest about what it *couldn't* figure out, instead of
> pretending everything matched."

## 0:35 – 1:15 — What you built (40s)

> "It reconciles two data sources: synthetic payment records built to exactly match Razorpay's
> real API schema, and a noisy internal ledger derived from them. Matching runs through three
> stages, cheapest and most certain first — deterministic exact-match, then fuzzy matching with
> wider tolerance, and only the genuinely ambiguous leftovers go to Claude, which has to return a
> decision with reasoning, logged in full. Anything still unresolved gets classified with a
> specific reason — not 'unresolved,' but *why*: amount mismatch, missing counterpart, duplicate,
> fee delta."

*(Skip if short on time: "I used synthetic data matching Razorpay's real schema since a live
account needs PAN KYC I don't have — the brief explicitly allows this.")*

## 1:15 – 2:30 — Live demo · *Build quality* (75s)

*(Have the dashboard already open in a tab before recording.)*

> "Let me show you." *(Screen share.)* "I'll generate a fresh batch of 80 payments and ledger rows
> right now — nothing pre-computed." *(Click Generate, click Run.)* "We get a match rate, and —
> because I kept a hidden ground-truth key completely out of the matching engine — a *measured*
> accuracy score against the real correct answers, not a number I'm just claiming." *(Point at the
> metrics.)* "Filterable results, and an exception list classified by reason — this one's a
> duplicate we caught and flagged instead of double-counting, this one's a payment recorded late."
>
> "One more thing worth showing —" *(type the passcode)* "— stage 3 is gated behind a passcode on
> this public link, since it triggers real billed API calls with no rate limit otherwise. Not
> hiding it, just being responsible with a public URL." *(Check the box, click Run again.)* "And
> now those same exceptions get resolved with logged reasoning instead of staying stuck."

## 2:30 – 3:10 — The honest results (40s)

> "Here's the part I'm proudest of. My first version scored a suspicious 100% accuracy across
> every test run. That should've felt like a win — it wasn't. It meant my tolerances happened to
> match noise I'd generated myself. So I deliberately added noise the rules genuinely can't
> resolve, specifically to force real failures into the numbers. Now: 93 to 99 percent, a real and
> different mistake list every run. That's the number I actually stand behind."

## 3:10 – 3:45 — AI judgment · *the right tool, and where I chose not to use one* (35s)

> "On using AI to build this — the three-stage design is itself a judgment call about when *not*
> to use AI. Stages one and two never touch an LLM at all; they're plain rules, because an exact
> reference match is a certainty, not something worth spending a model call on. Claude only ever
> sees the handful of rows left over that genuinely need judgment — usually single digits out of
> eighty. The right tool, only where it's actually needed."

## 3:45 – 4:25 — Failure recovery (40s)

> "I built this with Claude Code, directing every decision above. The obstacles were real: no PAN
> card meant no live Razorpay data, so I built a schema-accurate synthetic generator instead,
> disclosed openly. Testing stage 3 live against the real API — not just mocks — surfaced two bugs
> mocks never would have caught: an empty response from a token-budget issue, and a genuine model
> refusal on a completely benign question. And after deploying, I critiqued my own live app and
> found the LLM stage was open to any visitor with no rate limit — that's exactly why it's
> passcode-gated now."

## 4:25 – 4:55 — Close (30s)

> "This is fully built end to end — matching engine, exception classifier, LLM stage, dashboard,
> Dockerized, CI-verified on every push, deployed live. It's all public on GitHub with the real
> numbers in the README, not just claimed in a slide. I think this is what a finance team actually
> needs — not a demo that works once, but a system that's honest about its own limits. Thanks for
> watching."

---

## Pre-recording checklist

- [ ] Deploy link is live and works (test fresh, in an incognito window)
- [ ] Dashboard demo data generates in a few seconds — don't demo on a slow connection
- [ ] Passcode is ready to type without fumbling (`buildathon2026` unless you've changed the
      Streamlit Cloud secret — verify it still matches before recording)
- [ ] Practice the live-demo section separately until the clicks are muscle memory
- [ ] Time yourself at least twice with a stopwatch — most people run long on the first pass
- [ ] Have a backup: if the live demo breaks during recording, know you can fall back to
      describing the dashboard from a screenshot instead of dead air
- [ ] Recording setup: face-cam bubble + screen share (Loom does this automatically) so the
      self-intro and close have you on camera, not just a voiceover
