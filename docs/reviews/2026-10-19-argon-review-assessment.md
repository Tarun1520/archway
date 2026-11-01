# Assessment of the ARGON review (2026-10-19)

The review is kept as written in [2026-10-19-argon-review.md](2026-10-19-argon-review.md). This file records what was
checked against the code and the saved run (project "demo", run `1b0b99af…`), so a future reader knows which parts to trust.

## How it was checked
Each claim was compared with the code (file and function named below) and with the saved run's brief, questions,
decision receipts and options, read from the running backend. Diagrams were drawn with the real Mermaid library.

## Claim by claim

| # | Review claim | Verdict | What the code / data shows |
|---|---|---|---|
| 1 | Unstated stack leaks into `stack_preferences` and `must_have` | **True, and the most important finding** | `briefing/builder.py` copies `draft.stack_preferences` unchecked. The run's brief lists Python, Pandas, scikit-learn, Google Drive/Kaggle, Matplotlib; the person named none of them. |
| 2 | "Jev" and "decision model" were undefined but no question was asked | **True symptom, wrong root cause** | The question topics are a fixed list of five (`DraftQuestion.topic`: deployment, users, sensitive_data, budget, integrations). There is no topic for "what do you mean by X?", so the system *cannot* ask it. The run asked only a deployment question. Also missed by the review: the message refers to "the 2 links", which were never given. |
| 3 | Evidence is a one-line summary, so the review flags every library | **Mostly true** | PyPI evidence keeps only `info.summary` (`pypi_client.py` never reads `description`); npm keeps the short description; README evidence is the first 400 raw characters (`evidence/extract.py` `EXCERPT_LENGTH`), often badges. **Wrong part:** "a scout can submit a GitHub repo without inspecting it": `submit_components` already refuses that. |
| 4 | OPT-1 and OPT-2 are the same paradigm | **True** | A consequence of 1 and 2, as the review says. |
| 5 | Diagrams fail because of unquoted parentheses and slashes | **Wrong diagnosis for this run** | This run's diagrams were bare quoted strings (`"User Data" --> "Pandas Load"`), with no node ids: a side effect of our own prompt line "quote every label". Label quoting already existed when the run was made. Fixed 2026-10-19 (ids are given to bare quoted nodes, prompt now shows the exact form); all five saved diagrams now draw. |
| 6 | Empty assumption bullets; fused text like "CoveredREQ-2" | **Mostly not reproducible** | The saved brief has 9 assumptions, none empty, and the builder drops empty ones. Fused words come from copying the page as plain text (badges are separate elements); on screen they are apart. No Markdown export exists yet (Phase 6). |
| — | "60 calibrated Laya decisions" | **Count true, "calibrated" false** | 65 receipts, 60 answered. Laya's probabilities are not calibrated (measured; see `backend/services/laya/README.md`), which is why the UI says "raw score". |
| — | Scores (8.1/10, 9.5/10 ...) | **Opinion, not measurement** | No method is given. `evaluate_candidates` at 9.5 ignores that Laya scored 7/14 on four-step questions in our own spike. |
| — | Links and facts about Jev, Laya, benchmarks | **Unverified** | Every link is a Google search URL, not a source. Nothing in the code depends on them. |

## What to take from it
Worth doing (in this order): ground `stack_preferences` / `must_have` in the person's words (code, not only prompt);
let the model ask what a central undefined term means, and ask for material the person mentions but did not include;
keep longer, cleaned evidence text (PyPI description, README without badges) so the review checks against real text.

Not to copy as written: its prompt snippets contain domain examples ("decision trees vs. neural networks"), which our
prompts must not (see the generic-prompts rule); regex-scanning the model's assumptions for "does not define" is
brittle; a search before every intake adds cost to every run.

## Can its reviews be used again?
Yes, as a reader of OUTPUTS: it noticed real symptoms a user would notice. No, as an authority on the CODE or on
facts: about half its root causes were guesses phrased as findings ("or clarification.py filtered it out"), and it
cites search links instead of sources. Rule for next time: give it the code, ask for file and line for every claim,
and check each claim here before changing anything.

## What was changed because of it (2026-10-19)

1. **Brief grounding (code).** `app/policy/grounding.py`: a tool stays in `stack_preferences` only if the person named it
   (or an alias, or in an answer to a question). The rest, and any must-have that names one of them, move to the
   assumptions as "Assumed tool: ..." / "Assumed requirement: ...". The intake prompt also says so. Tests: `tests/test_grounding.py`.
2. **Two open question topics.** `meaning` (an undefined central term) and `material` (something mentioned but not
   included, such as links), asked first and only with the model's own wording (`app/policy/clarification.py`). The
   prompt's definition of a project now includes models, data pipelines and automations, and "how do I build it"
   requests: before this, the reviewed message was classified as not a project at all.
3. **Evidence that can support a claim.** PyPI evidence now includes the start of the package description, and README
   evidence is 1,500 characters with badges, images, HTML and links removed (`clean_doc_text`); the options reviewer
   sees 1,500 characters per cited item. Tests: `tests/test_doc_evidence.py`. Not done: npm READMEs (the registry's
   `latest` document does not reliably include one; a linked GitHub repository is inspected instead).
4. **Diagrams.** Bare quoted nodes get ids; the prompt shows the exact node form.

Checked live (Azure, 2026-10-19) on the reviewed message: no invented stack; questions asked about the undefined term and
the missing links. Holdouts (a messenger idea, a Django recipe site, a greeting) behaved as before: one question each for
the two ideas, named tools kept, the greeting still not a project.
