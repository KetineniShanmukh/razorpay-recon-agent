# 5-Minute Pitch Script

**How to use this:** don't memorize this word-for-word — read it a few times, understand *why*
each line is there, then say it in your own words. A judge can tell the difference between someone
reciting and someone explaining. The timings below assume normal speaking pace with a live demo in
the middle; adjust to your own rhythm, but keep roughly this shape.

Fill in your live deploy link before recording. Practice with a timer at least twice.

---

## 0:00 – 0:25 — Hook (25s)

> "Every company that takes payments has to prove their bank records match their internal books.
> In practice, they never line up perfectly — typos, late entries, duplicate rows, small fee
> deductions — and someone has to manually reconcile them by hand. I built an agent that does that
> automatically, and — this is the important part — it tells you honestly what it *couldn't*
> figure out, instead of pretending everything matched."

## 0:25 – 1:10 — What you built (45s)

> "This is a multi-source reconciliation engine. It takes two data sources — synthetic payment
> gateway records built to exactly match Razorpay's real API schema, and a noisy internal ledger
> derived from them — and runs them through a 3-stage matching pipeline: deterministic exact
> matching first, fuzzy matching second, and Claude making judgment calls on whatever's still
> genuinely ambiguous, with every decision's reasoning logged. Everything that's still unresolved
> gets classified with a specific reason — not just 'unresolved,' but *why*: amount mismatch,
> missing counterpart, duplicate, fee delta."

*(Say why synthetic, briefly, only if you have time or get asked — don't let this eat the clock:
"I used synthetic data matching Razorpay's real schema since a live account needs PAN KYC I don't
have — the brief explicitly allows this.")*

## 1:10 – 2:40 — Live demo (90s)

*(Have the dashboard already open in a tab before you start recording.)*

> "Let me show you." *(Screen share the dashboard.)* "I'll generate a fresh batch of 80 synthetic
> payments and ledger rows right now — nothing pre-computed." *(Click Generate, click Run.)*
> "In a few seconds, we get a match rate, and — because I kept a hidden ground-truth answer key out
> of the matching engine entirely — a *measured* accuracy score against the real correct answers,
> not a number I'm just claiming." *(Point at the metrics.)* "Here's the results table, filterable
> down to just the exceptions." *(Click the exceptions filter.)* "And here's the breakdown by
> reason — this one's a duplicate entry we correctly caught and flagged instead of double-counting,
> this one's a payment recorded 9 days late." *(If time allows, toggle stage 3 on and show one
> audit trail entry expand with its reasoning.)*

## 2:40 – 3:40 — The honest results (60s)

> "Here's the part I'm most proud of, honestly. The first version of this engine scored a perfect
> 100% accuracy across eight different test runs. That should've felt like a win — it wasn't. It
> meant my matching tolerances happened to line up exactly with the noise I'd generated, because I
> built both. A judge would be right to be suspicious of a perfect score. So I deliberately added
> noise the rules genuinely can't resolve — date drift wider than the matching window — specifically
> to force real failures into the numbers. After that: 93 to 99 percent accuracy across different
> seeds, a real and different mistake list every single run. That's the number I'm actually
> standing behind, because I can prove it's not cherry-picked."

## 3:40 – 4:25 — Why the LLM stage actually matters (45s)

> "The three-stage design isn't just for show — each stage only does what the one before it
> couldn't. Rules handle anything with a clear, checkable answer. The LLM only sees the handful of
> genuinely ambiguous cases left — usually single digits out of eighty — and it earns its keep
> there specifically: it can reason that a payment recorded late, with the exact same amount and
> reference ID, is obviously the same transaction, in a way a fixed tolerance rule can't safely
> generalize. And every one of its decisions is logged with its full reasoning, so nothing it
> decides is a black box."

## 4:25 – 5:00 — Close (35s)

> "This is fully built end to end: the matching engine, the exception classifier, the LLM stage,
> a live dashboard, Dockerized and verified through CI on every push, deployed at
> razorpay-recon-agent-bfar8jdwabaejt6qrj9u7u.streamlit.app.
> The whole thing is on GitHub, public, with the real numbers in the README, not just claimed in a
> slide. I think this maps directly to what a finance team actually needs — not a demo that works
> once, but a system that's honest about its own limits. Thanks for watching."

---

## Timing checklist before you record

- [ ] Deploy link is live and works (test it fresh, in an incognito window)
- [ ] Dashboard demo data generates in a few seconds — don't demo on a slow connection
- [ ] Practice the live-demo section separately until the clicks are muscle memory
- [ ] Time yourself at least twice with a stopwatch — most people run long on the first pass
- [ ] Have a backup: if the live demo breaks during recording, know you can fall back to describing
      the dashboard from a screenshot instead of dead air
