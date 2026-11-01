# ARGONS (Archway) Architecture & Pipeline Review: Detailed Root-Cause Analysis, Permanent Resolutions, and Feature Scorecard

This document consolidates the complete architectural review of **ARGONS / Archway**—your local LangGraph + [Laya](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2FNandhaKishorM%2Flaya) agentic architecture-planning system. It is structured as an engineering specification that you can hand directly to a coding agent to integrate permanent fixes across your nodes (`intake`, `briefing/builder.py`, `policy/clarification.py`, `capability_analyst`, `component_scout`, `evaluate_candidates`, `draft_options`, and `review_options`).

## 1. Executive Summary & Test Case Context

To stress-test the pipeline, the system was given the following real-world user goal:
> *"So my goal is to train a decision model for free on my domain. i just have data in some format now. so using the 2 links which one should i follow to get almost jev level performance and how to train the model and prepare the data. assume i have no knowledge"*

* **Actual User Intent**: Fine-tune a **System 1 non-autoregressive decision language model**—specifically [convaiinnovations/laya](https://www.google.com/search?q=https%3A%2F%2Fhuggingface.co%2Fconvaiinnovations%2Flaya) (built on [ModernBERT-large](https://www.google.com/search?q=https%3A%2F%2Fhuggingface.co%2Fanswerdotai%2FModernBERT-large)) via the [Laya Kaggle 2×T4 DDP Fine-Tuning Notebook](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2FNandhaKishorM%2Flaya%2Fblob%2Fmain%2Fnotebooks%2Flaya_finetune_typed_decisions_2xT4_kaggle.ipynb)—to match or beat [TypeSafe's Jev](https://www.google.com/search?q=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FJev_%28AI_model%29) on structured domain decisions (`choice`, `score`, and `noul` probabilities) such as those in the [LocalLLaMA/typed-decisions benchmark](https://www.google.com/search?q=https%3A%2F%2Fhuggingface.co%2Fdatasets%2FLocalLLaMA%2Ftyped-decisions) or the [YouTube Jev Architecture Deep-Dive](https://www.google.com/search?q=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DsF3CNPbWA8o).
* **What ARGONS Produced Instead**: Because `intake` ran without web/GitHub search tools and did not recognize the post-cutoff term `"Jev"` (launched September 2026), it assumed `"decision model"` meant a classical 1990s tabular **Decision Tree / Random Forest** in [scikit-learn](https://www.google.com/search?q=https%3A%2F%2Fpypi.org%2Fproject%2Fscikit-learn%2F) and assumed `"Jev"` was a generic synonym for "high performance." Worse, `intake` leaked that unverified guess into `ProjectBrief.stack_preferences` and `ProjectBrief.must_have`, forcing the entire downstream research team (`component_scout`, `evaluate_candidates`, and `draft_options`) to design tabular CSV pipelines around [scikit-learn](https://www.google.com/search?q=https%3A%2F%2Fpypi.org%2Fproject%2Fscikit-learn%2F), [feature-engine](https://www.google.com/search?q=https%3A%2F%2Fpypi.org%2Fproject%2Ffeature-engine%2F), [xgboost](https://www.google.com/search?q=https%3A%2F%2Fpypi.org%2Fproject%2Fxgboost%2F), and [PyCaret](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fpycaret%2Fpycaret).

## 2. Current Graph Topology & Core Architectural Strengths to Preserve

Before modifying any code, coding agents working on this repository should preserve the existing graph topology in `build.py` and its core anti-hallucination invariants:

```text
START → intake ─(has questions)→ clarify ─→ intake        (max 1 clarify round)
              └─(none)────────→ confirm_brief ─edit→ confirm_brief
                                      └─approve→ research_lead
research_lead ⇄ capability_analyst / component_scout ×N (parallel) / project_scout / reviewer
research_lead → evaluate_candidates ─(options_requested?)→ draft_options → review_options
      → select_or_revise → approve_version → END   (revise/change loops back to draft_options)
                         └─(not requested)→ END
```

### Architectural Pluses (Do Not Regress These)
* **Explicit Separation of User Quotes vs. System Assumptions**: Displaying `"In your words. Kept exactly as you wrote them"` alongside `"Assumptions — Archway assumed these. You did not say them"` makes LLM leaps transparent to the human in the loop at `confirm_brief`.
* **Code-Enforced Honesty Gates in `component_scout.py`**: Requiring `submit_components` to reject any package not actually fetched by a tool in the current run—and copying `license`, `archived` status, and activity strictly via Python code rather than trusting agent prose—eliminates fabricated repositories.
* **Blind Relevance Judge + Calibrated Laya Evaluation (`evaluate_candidates`)**: Having a blind relevance judge score retrieved facts (`0–3`) without seeing the scout's sales pitch, and then using local [Laya](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2FNandhaKishorM%2Flaya) to answer 60 typed questions on fit and integration risk (while leaving 5 unanswerable questions as `"not asked", never guessed`), is an exemplary neuro-symbolic verification pipeline.
* **Post-Draft Claim-to-Evidence Auditing (`review_options`)**: Auditing every prose claim in `OPT-1` and `OPT-2` against specific evidence IDs (`ev-...`) and generating a `"To validate before you rely on it"` checklist gives users a trustworthy engineering spec.

## 3. Detailed Issues, Root Causes, and Permanent Resolutions

### Issue 1: Unstated Assumptions Leak into `stack_preferences` and `must_have`
* **Target Files**: `intake.py`, `prompts.py` (`INTAKE_SYSTEM_PROMPT`), `briefing/builder.py`
* **What Is the Issue**: Even though the user never mentioned a single library or model architecture, `intake` populated `stack_preferences` with `Pandas`, `Scikit-learn as the main library for baseline decision models such as decision trees, random forests, or gradient boosting`, and `Matplotlib or Seaborn`. It also injected tabular-specific requirements into `must_have`, including `REQ-5` (*"feature engineering"*) and `REQ-9` (*"basic model interpretability, such as feature importance or simple explanation plots"*).
* **Why It Happens**:
  1. In `prompts.py`, `INTAKE_SYSTEM_PROMPT` instructs the model to *"Use only what the person wrote, and use null for anything unstated, never a guess"* and *"Assumptions are kept separate from what was said."* However, when generating structured JSON (`BriefDraft`), autoregressive LLMs treat earlier fields or latent assumptions (*"this is probably a beginner tabular ML project"*) as context for filling later required fields (`must_have` and `stack_preferences`) instead of leaving `stack_preferences` empty.
  2. In `briefing/builder.py`, your Python regex detector checks that stated `constraints` match `<user_input>` word for word, but it **does not** verify whether libraries named in `stack_preferences` or paradigm-specific terms in `must_have` actually appear in `<user_input>`. Once `builder.py` promotes `BriefDraft` into `ProjectBrief`, the LLM's hallucinated stack becomes a hard requirement for `research_lead`.
* **Permanent Resolution**:
  1. **Code Fix in `briefing/builder.py` (Lexical Grounding Gate for `stack_preferences`)**: Add a deterministic Python check in `builder.py` that inspects each entry in `BriefDraft.stack_preferences`. Combine `<user_input>` and any user replies from `clarify` into a normalized lowercase source string. Extract candidate package/technology nouns from each `stack_preferences` item (or check against a known vocabulary / capitalized token matcher); if the technology token (e.g., `"pandas"`, `"scikit-learn"`, `"sklearn"`, `"matplotlib"`, `"seaborn"`) is not present in the user's text, **strip that item from `ProjectBrief.stack_preferences`** and automatically append it to `ProjectBrief.assumptions` with the prefix `"Assumed stack preference (not stated by user): ..."`.
  2. **Prompt Fix in `prompts.py` (`INTAKE_SYSTEM_PROMPT`)**: Add an explicit hard rule to `INTAKE_SYSTEM_PROMPT`:
     ```text
     - stack_preferences MUST be an empty list [] unless the user explicitly names a programming language, library, framework, database, or cloud service inside <user_input>. Never infer stack_preferences from the problem domain or from your assumptions.
     - must_have items MUST remain architecture- and paradigm-neutral unless the user explicitly requested that paradigm. If you assume a specific model family (e.g., decision trees vs. neural networks), place that guess ONLY in assumptions, never in must_have or stack_preferences.
     ```

### Issue 2: Pre-Search Entity Blindness & Failure to Trigger `clarify` on Unknown Terms (`"Jev"`)
* **Target Files**: `intake.py`, `prompts.py` (`INTAKE_SYSTEM_PROMPT`), `policy/clarification.py`
* **What Is the Issue**: The user explicitly asked for `"almost jev level performance"` and `"train a decision model"`. In `Assumptions`, the `intake` LLM admitted:
  * *"The user repeatedly mentions training a decision model on their domain data but does not define 'decision model' explicitly."*
  * *"The user mentions 'almost jev level performance' multiple times but does not define 'jev'."*
  Despite recognizing that both core terms were undefined, the system did not ask the user what `"Jev"` or `"decision model"` meant, and instead guessed `DecisionTreeClassifier`.
* **Why It Happens**:
  1. `intake` runs `llm.complete_json(...)` with no search tools, so any model, framework, or benchmark released after the LLM's knowledge cutoff (like [TypeSafe's Jev](https://www.google.com/search?q=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FJev_%28AI_model%29) or [Laya](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2FNandhaKishorM%2Flaya)) is unknown to `intake`.
  2. Although `INTAKE_SYSTEM_PROMPT` says *"Ask a question only when two answers would lead to clearly different designs for this project"*, the LLM resolved its own uncertainty by writing an assumption rather than emitting a question in `BriefDraft.questions`—or `policy/clarification.py` filtered the question out.
* **Permanent Resolution**:
  1. **Code Fix in `policy/clarification.py` (Auto-Escalation from "Undefined Term" Assumptions)**: Add a deterministic rule in `policy/clarification.py` that scans `BriefDraft.assumptions` for uncertainty markers (regex matching phrases like `does not define`, `is not defined`, `refers to`, `assumed to mean`, `unclear whether`, or quoted tokens from `<user_input>`). If `clarify` has not yet run (`clarify_round == 0`) and fewer than 3 questions are queued, automatically synthesize or promote a clarification question asking the user to define the ambiguous term or confirm the assumed paradigm before transitioning to `confirm_brief`.
  2. **Optional Pre-Intake Term Grounding Hook in `intake.py`**: Before calling `llm.complete_json`, run a fast regex/NER pass on `<user_input>` for uncommon capitalized tokens, acronyms, or `"X-level"` / `"like X"` benchmark phrases (e.g., `"jev"`). If found and `search_web` / `search_github` is enabled, run a 1-shot search (capped at 1 tool call, ~500 ms) and pass the top 3 snippets in a `<term_context>` block alongside `<user_input>` so `intake` knows what `"Jev"` is on Turn 1.
  3. **Prompt Fix in `prompts.py` (`INTAKE_SYSTEM_PROMPT`)**: Add the rule:
     ```text
     - Whenever <user_input> contains an unfamiliar proper noun, model name, benchmark name (e.g., "X-level performance"), or domain term that could refer to either classical tabular ML or deep learning / LLM fine-tuning, you MUST emit a clarification question rather than guessing in assumptions.
     ```

### Issue 3: The "1-Line Evidence Trap" Causing False-Positive Warnings in `review_options`
* **Target Files**: `component_scout.py`, tool wrappers (`lookup_pypi`, `lookup_npm`, `search_github`), `draft_options`, `review_options`
* **What Is the Issue**: In the final output, almost every reused component triggered an evidence warning:
  * `ev-18e88ed6ba14` ([feature-engine](https://www.google.com/search?q=https%3A%2F%2Fpypi.org%2Fproject%2Ffeature-engine%2F)): only states *"Feature engineering and selection package with Scikit-learn's fit transform functionality"*; does not support claims about imputation, encoding, and scaling pipelines.
  * `ev-e06d1da2fdeb` ([xgboost](https://www.google.com/search?q=https%3A%2F%2Fpypi.org%2Fproject%2Fxgboost%2F)): only states *"XGBoost Python Package"*; does not support claims about its scikit-learn-compatible API for tabular tasks.
  * `ev-6cf79a18d999` ([joblib](https://www.google.com/search?q=https%3A%2F%2Fpypi.org%2Fproject%2Fjoblib%2F)): only states *"Lightweight pipelining with Python functions"*; does not support claims about serializing and deserializing models (`joblib.dump` / `joblib.load`).
  * `ev-775c870b4032` ([PyCaret](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fpycaret%2Fpycaret)): only states *"low-code machine learning library"*; does not support claims about `setup`, `compare_models`, `create_model`, `tune_model`, or `save_model`.
  * `ev-66474728ca46` ([LthreeC/pyruns](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2FLthreeC%2Fpyruns)): only stores repository metadata (`stars, last push, logo/readme links`).
* **Why It Happens**:
  1. Your system enforces a great rule: *"Agents write claims, and code writes facts."* When `component_scout` calls `lookup_pypi("joblib")` or `lookup_pypi("xgboost")`, the Python code that builds the `ev-...` evidence record only copies the 1-line PyPI `info["summary"]` field (and version/license), ignoring `info["description"]` (the package README). Similarly, when `component_scout` finds a repo via `search_github` and submits it without calling `inspect_repository` (or when `inspect_repository` only records repo header metadata), the `ev-...` record has zero README text.
  2. Downstream in `draft_options`, the LLM uses its parametric knowledge to write helpful, accurate `data_flow` descriptions (mentioning `PyCaret`'s `setup()` and `compare_models()` or `joblib` model persistence).
  3. Then `review_options` compares `draft_options`'s detailed prose against the 1-line `ev-...` summary and dutifully flags every single library as "unverified by evidence."
* **Permanent Resolution**:
  1. **Code Fix in `lookup_pypi` and `lookup_npm` Tool Handlers**: When constructing the code-copied fact for `ev-...`, extract both `info["summary"]` and a cleaned excerpt of `info["description"]` (strip HTML tags, badges, and long changelogs; keep the first 1,200–1,500 characters covering overview and key features/APIs).
  2. **Code Fix in `submit_components` (`component_scout.py`)**: If a scout submits a GitHub component whose evidence record only comes from `search_github` (no `inspect_repository` call in the current run), either have `submit_components` automatically invoke the README fetcher to populate the first 1,200 characters of `README.md` into the `ev-...` fact, or reject the submission with a tool message telling the scout: *"Call `inspect_repository` before `submit_components` so the evidence record contains README content, not just search metadata."*
  3. **Prompt Fix in `draft_options`**: Instruct the option-drafting agent:
     ```text
     - When describing a reused component's capabilities and API calls in components and data_flow, cite only functions, classes, and behaviors explicitly present in that component's retrieved evidence text (ev-...). If a specific function name (e.g., setup(), compare_models()) is not in the retrieved evidence text, describe the step in general terms or move the specific API check to the "To validate before you rely on it" checklist.
     ```

### Issue 4: Lack of Paradigm Diversity Between `OPT-1` and `OPT-2`
* **Target Files**: `capability_analyst`, `research_lead`, `draft_options`
* **What Is the Issue**: `OPT-1` (`scikit-learn` + `feature-engine` + `xgboost`) and `OPT-2` (`PyCaret` wrapping `scikit-learn`) are both classical tabular decision-tree pipelines. They only differ in whether `scikit-learn` is called directly or through `PyCaret`'s wrapper.
* **Why It Happens**: Because Issue 1 polluted `ProjectBrief.stack_preferences` with `scikit-learn`, `capability_analyst` decomposed the problem into tabular ML capabilities, and `draft_options` generated two variations of the exact same paradigm.
* **Permanent Resolution**:
  1. Once Issue 1 is fixed (`stack_preferences` stays empty when unstated), update the `capability_analyst` and `draft_options` prompts so that when `ProjectBrief.assumptions` contains an unconfirmed architectural paradigm assumption, `OPT-1` and `OPT-2` must represent **genuinely distinct technical approaches** (for example, `OPT-1: Fine-tuning a pretrained System 1 transformer decision model like Laya/ModernBERT` vs. `OPT-2: Classical gradient-boosted decision trees with XGBoost/scikit-learn`) rather than two wrappers around the same library.

### Issue 5: Silent Diagram Failure (`"The diagram could not be drawn"`)
* **Target Files**: `draft_options` (and diagram renderer/validator)
* **What Is the Issue**: Both options failed to render a visual architecture diagram and fell back to `"The diagram could not be drawn, so here is the flow as a list."`
* **Why It Happens**: LLMs frequently emit unquoted parentheses, slashes, or special characters inside Mermaid node labels (e.g., `[Upload data (CSV/JSON)]` or `[Save/load with joblib]`), which causes strict Mermaid/diagram parsers to throw a syntax error on the first pass. Because there is no syntax-sanitizer or retry loop inside `draft_options`, a single unescaped parenthesis kills the diagram.
* **Permanent Resolution**:
  1. **Deterministic Sanitizer in Python (`draft_options`)**: Before passing the generated diagram DSL/Mermaid string to the renderer/validator, run a Python regex sanitizer that wraps any node label containing `()`, `/`, `:`, or `.` in double quotes (e.g., transforming `A[Upload data (CSV/JSON)]` into `A["Upload data (CSV/JSON)"]`).
  2. **1-Step Validation Check**: If the diagram parser still reports an error after regex sanitization, append the parser error message and run a single fast repair completion on just the diagram field before falling back to the list view.

### Issue 6: String Concatenation & Empty Bullet Rendering Glitches
* **Target Files**: `briefing/builder.py` and UI / Markdown export templates
* **What Is the Issue**:
  * Two empty bullets (`- `) appear inside `Assumptions (9)`.
  * Badges and adjacent text concatenate without spaces across multiple sections: `AssumedThe decision model...`, `CoveredREQ-2`, `Reuse / build3 reused · 6 built4 reused · 2 builtSimplicityFavourable`, `Implementation effortMixed`, and `Open-source reuseMixed`.
* **Why It Happens**:
  1. In `briefing/builder.py`, empty or whitespace-only strings in the `assumptions` list (or separator items) are not filtered out before numbering and rendering.
  2. In the UI/text export template, badge spans (`<span>Assumed</span>`, `<span>Covered</span>`, `<span>Favourable</span>`) are adjacent to text spans without literal whitespace (`" "` or `"\n"`) between tags, so when copied or rendered to plain text/Markdown, the words fuse together.
* **Permanent Resolution**:
  1. In `briefing/builder.py`, sanitize all list fields on construction:
     ```python
     assumptions = [a.strip() for a in draft.assumptions if a and a.strip()]
     ```
  2. In the UI/Markdown renderer, add explicit literal delimiters (`"Assumed: "`, `"Covered · "`, `"\n"`, and pipe table cells `| Metric | OPT-1 | OPT-2 |`) inside the text nodes so copying or exporting preserves clean spacing.

## 4. Feature-by-Feature Scorecard & Ranking of Your Current System

The table below ranks every individual subsystem of **ARGONS / Archway** from strongest to weakest based on its current implementation, design rigor, and failure modes observed in this run.

| Rank | Feature / Subsystem | Score | Status Tier | What Is Working Well | What Needs Improvement |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Neuro-Symbolic Eligibility & Laya Evaluation (`evaluate_candidates`)** | **9.5 / 10** | **Production-Grade** | Combines deterministic code rules (`license`, `archived`, `finished apps`) with 60 calibrated [Laya](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2FNandhaKishorM%2Flaya) decisions per run, and properly abstains (`5 left as "not asked", never guessed`) instead of hallucinating answers. | Can also be reused earlier in the graph (at `intake`) to score whether user terms or assumptions require pre-search or clarification. |
| **2** | **Anti-Hallucination Tool Gate & Blind Relevance Judge (`component_scout.py`)** | **9.0 / 10** | **Production-Grade** | `submit_components` refuses any package not retrieved by a tool in the current run; code copies license/activity metadata; the blind relevance judge scores `0–3` on raw facts without seeing the scout's sales pitch. | Needs to copy 1,000–1,500 chars of `README.md` / PyPI `description` into `ev-...` (not just the 1-line summary or repo header metadata). |
| **3** | **LangGraph State Architecture & Checkpointing (`build.py`, `state.py`)** | **9.0 / 10** | **Production-Grade** | Clean `Command(goto=...)` edgeless transitions, parallel `Send` fan-out for `component_scout ×N`, plain JSON-serializable dicts/lists for SQLite checkpointing, and human-in-the-loop `interrupt()` gates. | Ready as-is; only needs a lightweight pre-intake term-grounding hook or stricter `intake → clarify` trigger condition. |
| **4** | **Side-by-Side Tradeoff & Requirement Traceability (`draft_options`)** | **8.5 / 10** | **Strong** | Clear `Build` vs. `Reuse` decomposition, explicit mapping to `REQ-1` through `REQ-10`, honest `Pros`/`Cons`, and an actionable `"To validate before you rely on it"` checklist. | Should enforce architectural diversity between `OPT-1` and `OPT-2` and constrain specific API names to those present in `ev-...`. |
| **5** | **Claim-to-Evidence Auditor (`review_options` / `reviewer`)** | **8.0 / 10** | **Strong (Starved of Data)** | Accurately detects whenever `draft_options` makes a claim (`setup()`, `compare_models()`, `joblib` serialization) that is missing from the stored `ev-...` string. | Currently produces noisy false-positive warnings on every library solely because `ev-...` only contains 1-line PyPI summaries (Issue 3). |
| **6** | **Deterministic Brief Builder (`briefing/builder.py`)** | **7.0 / 10** | **Good (Partial Gate)** | Preserves user quotes verbatim (`In your words`), assigns IDs/versions, and regex-verifies `constraints`. | Does not enforce lexical grounding on `stack_preferences` or filter out empty strings in `assumptions` (Issue 1 & Issue 6). |
| **7** | **Clarification Policy (`policy/clarification.py`)** | **6.0 / 10** | **Needs Tuning** | Caps clarification at 1 round and ≤3 high-impact questions so the user isn't interrogated endlessly. | Failed to fire when `intake` explicitly noted in `assumptions` that `"jev"` and `"decision model"` were undefined (Issue 2). |
| **8** | **Brief Generator Prompt & Schema (`intake.py`, `prompts.py`)** | **5.5 / 10** | **Primary Bottleneck** | Separates `Assumptions` into a dedicated list so the user can see what the model guessed. | Violated its own prompt rule (*"use null for anything unstated, never a guess"*) by leaking its `scikit-learn` decision-tree assumption into `stack_preferences` and `must_have`. |
| **9** | **Diagram Generation & Text Export Formatting** | **5.0 / 10** | **Needs Polish** | Gracefully falls back to a numbered text flow instead of crashing the run when a diagram fails. | Fails to render diagrams on both options due to unescaped syntax and fuses badge text (`AssumedThe`, `CoveredREQ-2`) in plain-text/Markdown output (Issue 5 & Issue 6). |

### Overall System Maturity: **8.1 / 10**
Your core multi-agent research engine, code-level honesty enforcement, and [Laya](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2FNandhaKishorM%2Flaya) integration (`research_lead` → `component_scout` → `evaluate_candidates` → `review_options`) are already at a **9/10 production standard**. Fixing the **intake assumption leak** (`briefing/builder.py` + `prompts.py`) and **expanding the evidence snippet length** (`lookup_pypi` / `inspect_repository` in `component_scout.py`) will immediately bring the end-to-end reliability of the entire system up to match its core engine.

## 5. Implementation Checklist (Priority Order)

1. **`briefing/builder.py`**: Strip any item in `BriefDraft.stack_preferences` whose technology name does not appear in `<user_input>` (or `clarify` answers) and move it into `ProjectBrief.assumptions`; strip empty strings from `assumptions`.
2. **`prompts.py` (`INTAKE_SYSTEM_PROMPT`)**: Forbid deriving `stack_preferences` or `must_have` items from `assumptions`; require `stack_preferences = []` when unstated and keep `must_have` paradigm-neutral.
3. **`policy/clarification.py`**: Automatically trigger a `clarify` question (`clarify_round == 0`) whenever `BriefDraft.assumptions` contains an "undefined term" marker (`does not define`, `is not defined`, `unclear`) or guesses between two incompatible modeling paradigms.
4. **`component_scout.py` (Tool Handlers)**: Include the first 1,200–1,500 cleaned characters of PyPI `info["description"]` and GitHub `README.md` inside the code-written `ev-...` fact record so `review_options` has real documentation to verify claims against.
5. **`draft_options` & UI Renderer**: Quote Mermaid node labels via regex before rendering diagrams, constrain prose claims to APIs present in `ev-...`, and insert literal whitespace delimiters (`": "`, `" · "`, `"\n"`) after status badges.
