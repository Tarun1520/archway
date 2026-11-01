"""
Keeping the model's guesses out of the brief's requirements, and asking about undefined terms and missing material.

Both came from a review of a real run (docs/reviews/2026-10-19-argon-review-assessment.md): tools the person never
named were written into stack_preferences and must_have, and the central term and the "two links" the person
mentioned were never asked about, because no question topic could ask them.
"""

from app.briefing.builder import build_brief
from app.models.brief_draft import BriefDraft
from app.policy.clarification import questions_for
from app.policy.grounding import ground_stack, is_named, requirements_naming, restates_assumption

SAID = ["I want to track what my team reads and share notes on it. It should store things in postgres."]


def draft(**changes) -> BriefDraft:
    values = dict(
        describes_project=True, problem="We are building a reading tracker.", users=None,
        must_have=["Track what each person reads"], nice_to_have=[], stack_preferences=[],
        budget=None, privacy=None, deployment=None, multi_user=None, handles_sensitive_data=None,
        mandatory_integrations=None, assumptions=[], unknowns=[], conflicts=[], clarifying_questions=[],
    )
    values.update(changes)
    return BriefDraft.model_validate(values)


def test_a_tool_counts_as_named_only_when_the_person_wrote_it_or_an_alias():
    assert is_named("PostgreSQL database for storage", SAID)  # alias: postgres
    assert not is_named("Redis as a cache", SAID)
    assert is_named("Kaggle or Colab for training", ["run it on colab"])  # one alternative is enough
    assert not is_named("Google Drive for files", ["put it in my drive"])  # every distinctive word must appear
    assert is_named("scikit-learn", ["maybe sklearn"])


def test_only_the_name_part_of_an_entry_is_checked():
    # "notes" appears in what was said, but it is in the explanation, not in the tool's name
    assert not is_named("Elasticsearch for searching notes", SAID)


def test_ground_stack_splits_named_from_assumed():
    kept, assumed = ground_stack(["PostgreSQL for storage", "Redis as a cache", "Python as the language"], SAID)
    assert kept == ["PostgreSQL for storage"]
    assert assumed == ["Redis as a cache", "Python as the language"]


def test_a_requirement_that_names_an_assumed_tool_is_found():
    found = requirements_naming(["Cache results in Redis", "Track what each person reads"], ["Redis as a cache"], SAID)
    assert found == ["Cache results in Redis"]


def test_the_builder_moves_unnamed_tools_and_the_requirements_that_name_them_into_assumptions():
    brief = build_brief(
        run_id="r", previous=None, user_texts=SAID, assumed_topics=[],
        draft=draft(stack_preferences=["PostgreSQL for storage", "Redis as a cache"],
                    must_have=["Track what each person reads", "Cache reading lists in Redis"]),
    )
    assert brief.stack_preferences == ["PostgreSQL for storage"]
    assert [r.text for r in brief.must_have] == ["Track what each person reads"]
    texts = [a.text for a in brief.assumptions]
    assert "Assumed tool: Redis as a cache" in texts
    assert "Assumed requirement: Cache reading lists in Redis" in texts
    assert all(a.reason for a in brief.assumptions if a.id.startswith(("ASM-tool", "ASM-req")))


def test_an_answer_to_a_question_counts_as_something_the_person_said():
    brief = build_brief(run_id="r", previous=None, user_texts=[*SAID, "Answer about integrations: it must use Redis"],
                        assumed_topics=[], draft=draft(stack_preferences=["Redis as a cache"]))
    assert brief.stack_preferences == ["Redis as a cache"]


def test_meaning_and_material_questions_come_first_and_need_the_models_own_wording():
    questions = questions_for(draft(clarifying_questions=[
        {"topic": "deployment", "question": "Local or hosted?", "why_it_matters": "x"},
        {"topic": "material", "question": "Could you share the two links you mentioned?", "why_it_matters": "They may decide what to build."},
        {"topic": "meaning", "question": "What do you mean by 'X-level'?", "why_it_matters": "Two readings, two designs."},
    ]), already_asked=[])
    assert [q.topic for q in questions] == ["meaning", "material", "deployment"]
    assert questions[0].question == "What do you mean by 'X-level'?"


def test_an_open_question_without_wording_is_not_asked():
    questions = questions_for(draft(clarifying_questions=[{"topic": "meaning", "question": "  ", "why_it_matters": ""}]), already_asked=[])
    assert questions == []


def test_an_open_topic_is_asked_once_only():
    questions = questions_for(draft(clarifying_questions=[{"topic": "meaning", "question": "What is X?", "why_it_matters": "x"}]), already_asked=["meaning"])
    assert questions == []


# --- Requirements that only repeat the model's own assumptions (second ARGON run, 2026-10-22) -------------------------

RUN_SAID = [
    "We are building and training a decision model on our own domain data for free so we can reach almost Jev-level "
    "performance. We need clear guidance on how to prepare our data and train the model from scratch.",
    "A decision model responds with numbers like Jev.",
]
RUN_ASSUMED = [
    "The decision model is some form of predictive numeric model (e.g., mapping inputs to numeric outputs).",
    "Domain data is already available or can be collected by the team.",
]


def test_a_requirement_that_repeats_an_assumption_is_recognised():
    invented = "The decision model will be implemented as a supervised regression model mapping input features to continuous numeric outputs."
    assert restates_assumption(invented, RUN_ASSUMED, RUN_SAID)


def test_requirements_backed_by_the_persons_words_stay():
    for text in ["We must train a decision model on our own domain data.", "We must receive clear guidance on how to prepare our data."]:
        assert not restates_assumption(text, RUN_ASSUMED, RUN_SAID)


def test_a_requirement_unlike_every_assumption_stays_even_if_worded_freshly():
    assert not restates_assumption("The guidance must explain how to split data into training and test sets.", RUN_ASSUMED, RUN_SAID)


def test_the_builder_moves_a_restated_assumption_out_of_the_requirements():
    invented = "The decision model will be implemented as a supervised regression model mapping input features to continuous numeric outputs."
    brief = build_brief(
        run_id="r", previous=None, user_texts=RUN_SAID, assumed_topics=[],
        draft=draft(
            must_have=["We must train a decision model on our own domain data.", invented],
            assumptions=[{"text": text, "reason": "guess"} for text in RUN_ASSUMED],
        ),
    )
    assert [r.text for r in brief.must_have] == ["We must train a decision model on our own domain data."]
    assert f"Assumed requirement: {invented}" in [a.text for a in brief.assumptions]
