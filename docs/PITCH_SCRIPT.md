# 5-Minute Pitch Script (Final — Delivery Edition)

**You don't need to be a good speaker for this to land well. You need to sound like someone who
knows their project cold and isn't rushing.** That's it. Judges aren't scoring stage presence —
they're scoring whether you understand what you built. Slow and slightly awkward beats fast and
smooth-sounding-but-shaky, every time.

## How to use this

- Read it out loud 3-4 times. By the third time you'll naturally start saying it in your own
  words — that's correct, let it happen. Reciting from memory sounds worse than explaining
  something you understand.
- The **/** marks are pause points. Actually pause there — half a second, just a breath. It feels
  like forever to you and sounds completely normal to a listener. Nervous speakers rush through
  pauses; that's the single biggest thing to fight.
- Sentences here are short on purpose. Short sentences are hard to trip over. If you stumble on a
  word, stop, take a breath, say the sentence again slower. Don't apologize, don't say "sorry" —
  just restart the sentence. Judges have seen this a hundred times; it reads as calm, not weak.
- Bracketed text in *italics* is a stage direction for you — never say it out loud.
- **If you fumble badly and want to stop, hit Pause, not Stop.** Loom's floating recording
  toolbar (the one that appears while you're actually capturing, separate from playback controls)
  has a pause/resume button. Pause, breathe for a few seconds, resume, and just re-say the last
  sentence. It's still one continuous recording — you don't lose the take and don't have to start
  over from the beginning.

---

## 0:00 – 0:10 — Self-intro (10s)

*(Face to camera. Sit up, both hands visible, small smile. This is the easiest part — it's just
your name.)*

> "Hi, I'm Shanmukh Ketineni. / I'm a final-year ECE student, / and this is ReconIQ — my submission
> for the AI Finance Controller track."

## 0:10 – 0:35 — The problem (25s)

> "Here's the problem. / Every company that takes payments has to check that their bank records
> match their internal books. / In practice, they never match perfectly. / Typos. Late entries.
> Duplicate rows. Small fee deductions. / Someone has to sit down and reconcile all of it by hand.
>
> ReconIQ automates that. / And it does one more thing — / it's honest about what it *couldn't*
> figure out, / instead of pretending everything matched."

## 0:35 – 1:15 — What you built (40s)

> "It reconciles two data sources. / Synthetic payment records, built to match Razorpay's real API
> schema exactly. / And a noisy internal ledger, derived from those payments.
>
> Matching runs in three stages. / Cheapest and most certain first. / Stage one: exact matching. /
> Stage two: fuzzy matching, with wider tolerance. / Only what's left after that — the genuinely
> unclear cases — goes to Claude. / It has to return a decision *with* reasoning, and that
> reasoning gets logged in full.
>
> Anything still unresolved gets a real reason attached. / Not 'unresolved.' / Something specific —
> amount mismatch, missing counterpart, duplicate, fee delta."

*(Only say this next line if you're running ahead of time — it's safe to cut: "I used synthetic
data because a live Razorpay account needs PAN KYC I don't have — the brief explicitly allows
this.")*

## 1:15 – 2:30 — Live demo (75s)

*(This is the section that goes long if you're not ready for it — it's where a first take usually
breaks. Two things to do before you ever hit record:*

*1. Open the dashboard in its own tab and leave it open. Don't open it live — every second of
loading is a second you're silently panicking on camera.*

*2. Do one full silent dry run right before recording — click Generate, click Run, type the
passcode, run stage 3, all of it, off camera. This wakes up the app (free hosting can be slow on a
cold start) so it's fast when you're actually rolling, and it makes the clicks muscle memory so
you're not hunting for buttons while also trying to talk.)*

> "Let me show you." *(Switch to screen share.)*
>
> "I'll generate a fresh batch right now — 80 payments, 80 ledger rows." *(Click Generate, click
> Run.)* *(If it takes a moment, you don't need to fill the silence — a second of quiet while
> something visibly loads on screen is completely normal. If it drags, one line is enough: "Running
> the full pipeline now.")*
>
> "Here's the match rate. / And here's the part that matters — measured accuracy. / Not a number
> I'm claiming — / I kept a hidden answer key out of the matching engine, / and this score is
> checked against that."
>
> *(Point at the exception list — you don't have to narrate every word, just point.)* "Every
> unresolved row gets a real reason, not just 'unresolved.'"
>
> "One more thing." *(Type the passcode — this is the one you rehearsed, so it's fast.)* "Stage
> three is gated behind a passcode on this public link, / since it triggers real billed API calls
> with no rate limit otherwise." *(Check the box, click Run again.)* "And now those exceptions get
> resolved, with the reasoning logged right there."

## 2:30 – 3:10 — The honest number (40s)

> "This next part is the one I'm actually proudest of. / My first version of this scored a hundred
> percent accuracy. / Every single test run. / That felt like a win. / It wasn't.
>
> It meant my matching tolerances happened to line up exactly / with noise I'd generated myself. /
> A real judge should distrust a perfect score. / So I went back in / and deliberately added noise
> the rules genuinely can't resolve on their own.
>
> Now it's ninety-three to ninety-nine percent, / and it's different every run. / That's the number
> I actually stand behind."

## 3:10 – 3:45 — Where AI fits, and where it doesn't (35s)

> "One thing I want to be direct about — / how I used AI here isn't just stage three. / It's the
> whole design.
>
> Stages one and two never call an LLM at all. / They're plain rules. / An exact reference match is
> a certainty — / there's no reason to spend a model call proving something you already know. /
> Claude only ever sees the handful of rows left over / that genuinely need judgment. / Usually
> single digits, out of eighty.
>
> The right tool, / only where it's actually needed."

## 3:45 – 4:25 — What broke, and what I did (40s)

> "I built this with Claude Code, directing every decision. / A few things actually broke along the
> way.
>
> No PAN card meant no live Razorpay data — / so I built a schema-accurate synthetic generator
> instead, and said so, openly.
>
> Testing stage three live, against the real API, / not just mocks — / that surfaced two bugs mocks
> never would have caught. / An empty response from a token-budget issue. / And one genuine model
> refusal, on a completely harmless question.
>
> And after I deployed it, / I turned around and critiqued my own live app. / Found the LLM stage
> was wide open — / any visitor, no rate limit. / That's exactly why it's passcode-gated now."

## 4:25 – 4:55 — Close (30s)

*(Back to face on camera if you can. Slow down here — this is the last thing they hear.)*

> "This is built end to end. / Matching engine, exception classifier, LLM stage, dashboard. /
> Dockerized. / Tested on every push. / Deployed live right now.
>
> It's all public on GitHub, / with the real numbers sitting in the README — / not just claimed in
> a slide.
>
> I think this is what a finance team actually needs. / Not a demo that works once — / a system
> that's honest about its own limits.
>
> Thanks for watching."

---

## Before you record — read this once

**The nerves don't go away by the time you hit record. They go away by the third take.** Plan for
3 takes, not 1. Nobody nails this cold.

- **Speed is the enemy, not mistakes.** A nervous person's default is to speed up. Force yourself
  to go slower than feels natural — it will sound normal on playback, not slow. If in doubt, slow
  down more.
- **Look at the camera lens, not your own face on screen**, during the intro and close. It's the
  single biggest thing that makes a recording feel like eye contact instead of a read-aloud.
- **If you fumble a sentence, pause (don't stop), breathe, say it again.** A short pause reads as
  thoughtful, not incompetent — and it keeps you in the same take instead of starting over.
- **Smile slightly during the self-intro and close.** Costs nothing, changes your tone of voice
  even if no one's consciously watching for it.
- **Do the live demo section as a separate practice run**, clicks and all, at least 3 times, before
  you ever hit record for real. This is the section most likely to go sideways, and it's the one
  you can fully rehearse.

## Pre-recording checklist

- [ ] Deploy link is live and works (test fresh, in an incognito window)
- [ ] Dashboard demo data generates in a few seconds — don't demo on a slow connection
- [ ] Passcode is ready to type without fumbling (`buildathon2026` unless you've changed the
      Streamlit Cloud secret — verify it still matches before recording)
- [ ] Did one full silent dry run of the demo (generate, run, passcode, stage 3) immediately
      before recording, off camera, to wake up the app and warm up the clicks
- [ ] Practiced the live-demo section separately until the clicks are muscle memory
- [ ] Know where Loom's pause button is on the recording toolbar, not just the playback controls
- [ ] Timed yourself at least twice with a stopwatch — most people run long on the first pass
- [ ] Backup plan ready: if the live demo breaks during recording, fall back to describing the
      dashboard from a screenshot instead of dead air
- [ ] Recording setup: face-cam bubble + screen share (Loom does this automatically) so the
      self-intro and close have you on camera, not just a voiceover
- [ ] Budgeted for 3 takes, not 1
