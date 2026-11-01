# Assessment of the second ARGON review (2026-10-22)

The review covers ARGON's "Run 1" (assessed in [2026-10-19-argon-review-assessment.md](2026-10-19-argon-review-assessment.md))
and a "Run 2". The review text itself was shared in chat; this file records what was checked against the code and the
saved run, so a future reader knows which parts to trust.

## The most important finding: Run 2 ran on code from before the first fixes

Run 2 is run `4add4a85…` (brief version 3, saved 2026-10-20 16:14 UTC). The stack-grounding gate
(`app/policy/grounding.py`) was written on 2026-10-19. Run on the current code, that gate moves all five unnamed tools
(Python, scikit-learn, pandas, Jupyter, Git) into "Assumed tool:" entries. The saved brief has none, so the backend
that built it was still running the older code (the server's reload on save evidently missed the change). The review's
"still leaked scikit-learn, pandas, Jupyter, Git into the stack" therefore grades old code. **Before trusting a review
of a run, restart the backend and check that the run used the current code.**

## Claim by claim

| # | Review claim | Verdict | What the code / data shows |
|---|---|---|---|
| 1 | Intake has no search, so "Jev" was misread; add a lookup of unknown names first | **True gap; their regex is too narrow** | Intake has no tools. Matching only "X-level" / "like X" misses most cases. A generic lookup of unfamiliar proper nouns, shown to the person as an assumption, is the better form. Not built yet. |
| 2 | Unstated stack still leaks into the brief | **Already fixed** (see above) | The gate works on the current code. |
| 2b | A paradigm guess became a must-have (REQ-10 "supervised regression model") | **True gap** | The gate only caught tool NAMES. Their fix is a hard-coded list of ML words, which breaks the domain-agnostic rule. Built instead: `restates_assumption` (a requirement barely backed by the person's words that repeats one of the model's own assumptions becomes an assumption). On this run it moves REQ-10 and also REQ-9. |
| 3 | False conflict: "team members" read as an always-on server | **True, diagnosis correct** | `conflicts.py` matched the bare word "team". Now only a team reaching a shared or online service counts. Prompt rule added: no requirements about who uses or may access the result unless the person said so. |
| 4 | MLflow evidence: the first 1,500 characters miss the feature used | **True; their fix (slice per query) does not fit** | Evidence ids are per URL, shared by every capability, so a per-query slice would clash. Built instead: `doc_excerpt` keeps a long document's opening plus the start of every section. |
| 5a | 3 blank bullets among 10 assumptions | **Not supported** | All 10 saved assumptions have text; 3 have no reason line. |
| 5b | Copied text fuses labels ("AssumedThe", "CoveredREQ-2") | **True, cosmetic** | Unseen separators (screen-reader-only text, still copied) added to the brief labels and the option coverage rows. Tables already copy with tabs. |
| — | Facts about Laya's base model, the Kaggle notebook, the benchmark, the video | **Unverified** | Nothing in the code depends on them; none goes into prompts. (TypeSafe Jev itself is real and already documented in LEARNING_GUIDE.md.) |
| — | Scores (8.6/10 ...) | **Opinion, not measurement** | No method is given. |

## Verdict
More useful than the first review: three real bugs (false conflict, assumption written as a requirement, long-README
evidence) with correct diagnoses. Its proposed code is domain-specific and should not be copied as written. Its biggest
miss is not noticing that the run predated the fixes it was asked to evaluate.
