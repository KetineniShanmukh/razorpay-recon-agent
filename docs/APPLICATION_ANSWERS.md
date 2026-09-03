# Buildathon Application — Ready-to-Paste Answers

For the Google Form fields that aren't the video or GitHub link. Read each once before pasting —
these are drafts in your voice, not something to submit blind.

## Project Name / Title

```
ReconIQ
```

## Project Objectives — "What does it solve?"

```
ReconIQ closes the finance-ops reconciliation loop that's usually done by hand: matching a
payment gateway's records against a company's internal ledger, which never lines up perfectly in
practice due to typos, late entries, duplicates, and fee deductions. It runs a 3-stage matching
engine — deterministic, then fuzzy, then LLM-assisted only for genuinely ambiguous cases — and
reports a measured accuracy score (scored against a hidden ground-truth key, not self-claimed)
plus a classified, honest list of every exception it couldn't resolve and why. The goal is turning
a full-time manual reconciliation job into a few minutes of reviewing a short, well-explained
exception list.
```

## Build Challenges & Technical Obstacles

```
The biggest early obstacle was data access: I don't have a PAN card, which is a hard KYC
requirement for even a Razorpay test-mode account, so I couldn't pull live API data. Rather than
skip that or fake it, I built a synthetic payments generator matching Razorpay's real Payments API
schema field-for-field, disclosed openly as synthetic throughout the project — the brief
explicitly permits a 50+ record synthetic batch.

The most important obstacle came after the matching engine was working: my first version scored a
suspicious 100% accuracy across every test run. That felt like success, but it wasn't — it meant
my matching tolerances happened to line up exactly with noise I'd generated myself. A judge would
rightly distrust a perfect score, so I deliberately added noise wide enough that the rules
genuinely can't resolve it on their own. Accuracy dropped to a real, varying 93-99% across
different seeds — a number I can actually defend, because nothing about it is cherry-picked.

Wiring in Claude for LLM-assisted resolution of the remaining ambiguous cases surfaced two more
obstacles I only found by testing live against the real API instead of trusting mocked tests: the
model's reasoning sometimes consumed its entire token budget before producing an answer, leaving
an empty response, and a rare genuine model refusal came back on a completely benign question.
Both needed to fail safely - log the reason, never crash, never force a bad match - instead of
breaking silently.

The last obstacle came after deployment: I asked for an honest critique of my own live app and
found the LLM stage was enabled for any public visitor with no rate limit or authentication -
anyone who found the link could trigger real, billed API calls. I added a passcode gate that fails
closed by default, so there's no window where the deployment sits exposed.

I built this using Claude Code as my primary tool, directing the architecture, priorities, and
every judgment call above. The value I added wasn't typing every line - it was catching these
issues, deciding how to fix them, and understanding the system well enough to defend it.
```

*(~320 words. If the form has a character limit, trim the weakest paragraph rather than making
all four vaguer — the specificity is what makes this work. Tell me the limit and I'll cut it for
you.)*

## Before you submit

The form says: *"I confirm this is my official final project submission. I understand that no
further changes or edits can be made after submitting."* Check all of these first — you can't fix
anything after:

- [ ] Live deploy link works (test fresh, incognito window)
- [ ] Stage 3 passcode (`buildathon2026`) still matches what's in Streamlit Cloud secrets
- [ ] GitHub repo is public
- [ ] Video is uploaded and the link is actually shareable (test it in an incognito window too —
      "Unlisted" YouTube and Loom links usually work by default, but double-check)
- [ ] Video is under or close to 5 minutes
