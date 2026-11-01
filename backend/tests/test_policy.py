"""
Tests for the plain-Python policy rules (app/policy/) and the brief builder
(app/briefing/builder.py).

Checkpoint 2 items covered here:
    - "Stated constraints are never silently dropped"
    - "Conflicting requirements are flagged"
    - assumptions are kept apart from what the user said

None of these tests uses a model. That is why they can be exact.
"""

import pytest

from app.briefing.builder import add_assumptions, apply_edit, build_brief, mark_confirmed
from app.models.brief import Constraints, Requirement
from app.models.brief_draft import BriefDraft
from app.models.workflow import BriefEdit, EditedItem
from app.policy.clarification import MAX_QUESTIONS, QUESTION_TEXT, TOPIC_ORDER, WHY_TEXT, has_project, questions_for
from app.policy.idea_readiness import idea_readiness
from app.policy.small_talk import is_small_talk, only_small_talk
from app.policy.conflicts import find_conflicts
from app.policy.stated_constraints import find_stated_constraints


def draft(**overrides) -> BriefDraft:
    """A minimal model draft; tests override only the fields they care about."""
    values = dict(
        describes_project=True,
        problem="A wiki for a team", users=None, must_have=[], nice_to_have=[], stack_preferences=[],
        budget=None, privacy=None, deployment=None, multi_user=None, handles_sensitive_data=None,
        mandatory_integrations=None, assumptions=[], unknowns=[], conflicts=[],
        # By default the "model" suggests the standard question for every topic.
        clarifying_questions=[
            {"topic": topic, "question": QUESTION_TEXT[topic], "why_it_matters": WHY_TEXT[topic]} for topic in TOPIC_ORDER
        ],
    )
    values.update(overrides)
    return BriefDraft(**values)


# --- Stated constraints -----------------------------------------------------------
@pytest.mark.parametrize("sentence", [
    "We don't want to pay for any hosting.",
    "No paid services.",
    "It must work offline.",
    "My notes must never leave my laptop.",
    "It should be self-hosted.",
    "It runs only on my own machine.",
    "It has to be GDPR compliant.",
])
def test_common_constraint_wordings_are_found(sentence):
    assert find_stated_constraints([f"A notes app. {sentence} It has tags."]) == [sentence]


def test_ordinary_sentences_are_not_constraints():
    assert find_stated_constraints(["A notes app with tags and search. It shows backlinks."]) == []


def test_constraints_are_kept_word_for_word_in_order_without_repeats():
    texts = ["A wiki. No paid hosting!", "Answer about budget: No paid hosting!", "It must work offline"]
    assert find_stated_constraints(texts) == ["No paid hosting!", "Answer about budget: No paid hosting!", "It must work offline"]


def test_a_stated_constraint_survives_even_when_the_model_ignores_it():
    """The model returned nothing about cost. The user's sentence is in the brief anyway."""
    brief = build_brief(
        run_id="r", draft=draft(budget=None), previous=None,
        user_texts=["A team wiki. We don't want to pay for any hosting."], assumed_topics=[],
    )
    assert brief.constraints.budget is None  # unknown stays unknown: we do not invent a value
    assert brief.constraints.stated == ["We don't want to pay for any hosting."]


def test_a_constraint_from_an_earlier_version_is_not_dropped_by_a_later_draft():
    texts = ["A wiki. It must work offline."]
    first = build_brief(run_id="r", draft=draft(deployment="Local", budget="No paid services"),
                        previous=None, user_texts=texts, assumed_topics=[])
    # The second draft "forgets" both values (null).
    second = build_brief(run_id="r", draft=draft(deployment=None, budget=None),
                         previous=first, user_texts=texts, assumed_topics=[])
    assert second.version == 2
    assert second.constraints.deployment == "Local"
    assert second.constraints.budget == "No paid services"
    assert second.constraints.stated == ["It must work offline."]


# --- Conflicts --------------------------------------------------------------------
def test_no_paid_hosting_conflicts_with_always_on_multi_user_sync():
    constraints = Constraints(stated=["We don't want to pay for any hosting."])
    requirements = [
        Requirement(id="REQ-1", text="Pages are written in markdown"),
        Requirement(id="REQ-2", text="Everyone sees changes instantly, from anywhere"),
    ]
    conflicts = find_conflicts(constraints, requirements)
    assert len(conflicts) == 1
    assert conflicts[0].requirement_ids == ["REQ-2"]  # names the requirement involved


def test_a_team_keeping_files_private_is_not_an_always_on_service():
    # Found in a real run: "only authorized team members" was read as "many people reach a server at any time".
    constraints = Constraints(stated=["We are training it for free."])
    requirements = [Requirement(id="REQ-9", text="Store the data and models so that only authorized team members can use them.")]
    assert find_conflicts(constraints, requirements) == []
    hosted = [Requirement(id="REQ-1", text="The whole team uses the shared app online at the same moment.")]
    assert find_conflicts(constraints, hosted)


def test_offline_conflicts_with_a_cloud_requirement():
    conflicts = find_conflicts(Constraints(deployment="Works offline"),
                               [Requirement(id="REQ-1", text="Sync across devices through the cloud")])
    assert [conflict.requirement_ids for conflict in conflicts] == [["REQ-1"]]


def test_compatible_requirements_raise_no_conflict():
    assert find_conflicts(Constraints(budget="No paid services"),
                          [Requirement(id="REQ-1", text="Save a link with a title and tags")]) == []


def test_a_conflict_the_model_suggested_is_kept_and_linked_to_ids():
    brief = build_brief(
        run_id="r", previous=None, user_texts=["x"], assumed_topics=[],
        draft=draft(must_have=["Export to PDF", "Never create files"],
                    conflicts=[{"description": "Exporting creates a file.", "requirement_texts": ["Export to PDF", "Never create files"]}]),
    )
    assert brief.conflicts[0].description == "Exporting creates a file."
    assert brief.conflicts[0].requirement_ids == ["REQ-1", "REQ-2"]


# --- Building and versioning ------------------------------------------------------
def test_requirement_ids_stay_stable_when_the_idea_is_read_again():
    first = build_brief(run_id="r", draft=draft(must_have=["Tags", "Search"]), previous=None, user_texts=["x"], assumed_topics=[])
    second = build_brief(run_id="r", draft=draft(must_have=["Search", "Backlinks", "Tags"]), previous=first, user_texts=["x"], assumed_topics=[])
    assert {item.text: item.id for item in first.must_have} == {"Tags": "REQ-1", "Search": "REQ-2"}
    assert {item.text: item.id for item in second.must_have} == {"Search": "REQ-2", "Backlinks": "REQ-3", "Tags": "REQ-1"}


def test_skipped_questions_become_assumptions_not_user_statements():
    first = build_brief(run_id="r", draft=draft(must_have=["Tags"]), previous=None, user_texts=["x"], assumed_topics=[])
    second = add_assumptions(first, ["deployment", "budget"])
    assert second.version == first.version + 1
    assert [item.id for item in second.assumptions] == ["ASM-deployment", "ASM-budget"]
    # Nothing was written into the user's own statements or constraints.
    assert second.must_have == first.must_have
    assert second.constraints.deployment is None and second.constraints.budget is None


def test_an_edit_makes_a_new_unconfirmed_version_and_rechecks_conflicts():
    first = mark_confirmed(build_brief(run_id="r", draft=draft(must_have=["Pages are markdown"], budget="No paid hosting"),
                                       previous=None, user_texts=["x"], assumed_topics=[]))
    assert first.confirmed is True and first.conflicts == []

    edit = BriefEdit(
        problem="A team wiki",
        must_have=[EditedItem(id="REQ-1", text="Pages are markdown"), EditedItem(text="Everyone edits at the same time")],
        constraints=first.constraints,
    )
    second = apply_edit(first, edit)
    assert second.version == 2
    assert second.confirmed is False  # approval never carries over to an edited version
    assert [item.id for item in second.must_have] == ["REQ-1", "REQ-2"]
    assert second.conflicts and second.conflicts[0].requirement_ids == ["REQ-2"]
    assert first.version == 1 and first.confirmed is True  # the earlier version is untouched


def test_an_edit_cannot_use_the_same_id_twice():
    first = build_brief(run_id="r", draft=draft(must_have=["A"]), previous=None, user_texts=["x"], assumed_topics=[])
    with pytest.raises(ValueError):
        apply_edit(first, BriefEdit(problem="p", must_have=[EditedItem(id="REQ-1", text="A"), EditedItem(id="REQ-1", text="B")]))


# --- Clarification policy ---------------------------------------------------------
def test_only_unknown_architecture_topics_are_asked_and_never_more_than_the_limit():
    questions = questions_for(draft(), already_asked=[])  # everything unknown
    assert len(questions) == MAX_QUESTIONS
    assert [question.topic for question in questions] == ["deployment", "users", "sensitive_data"]


def test_nothing_is_asked_when_everything_is_known():
    known = draft(deployment="Local", multi_user=False, handles_sensitive_data=False, budget="None", mandatory_integrations=[])
    assert questions_for(known, already_asked=[]) == []


def test_a_topic_is_never_asked_twice():
    questions = questions_for(draft(), already_asked=["deployment", "users", "sensitive_data"])
    assert [question.topic for question in questions] == ["budget", "integrations"]


def test_a_redraft_that_rewords_everything_starts_numbering_from_one_again():
    """Seen in a live run: version 2 began at REQ-6 because every item was reworded."""
    first = build_brief(run_id="r", draft=draft(must_have=["A", "B", "C"]), previous=None, user_texts=["x"], assumed_topics=[])
    second = build_brief(run_id="r", draft=draft(must_have=["B", "D", "E"]), previous=first, user_texts=["x"], assumed_topics=[])
    assert [(item.id, item.text) for item in second.must_have] == [("REQ-2", "B"), ("REQ-1", "D"), ("REQ-3", "E")]


def test_the_same_clash_from_the_rule_and_the_model_is_shown_once():
    """Seen in a live run: the rule and the model both reported no-paid-hosting vs instant editing."""
    brief = build_brief(
        run_id="r", previous=None, assumed_topics=[],
        user_texts=["A notes app. We don't want to pay for any hosting."],
        draft=draft(
            must_have=["Instant collaborative editing for all users", "Markdown notes"],
            conflicts=[{"description": "Instant editing may need a paid server.",
                        "requirement_texts": ["Instant collaborative editing for all users", "Markdown notes"]}],
        ),
    )
    assert len(brief.conflicts) == 1
    assert brief.conflicts[0].requirement_ids == ["REQ-1", "REQ-2"]  # the model's extra id is kept


def test_a_different_clash_from_the_model_is_still_listed():
    brief = build_brief(
        run_id="r", previous=None, assumed_topics=[],
        user_texts=["A notes app. We don't want to pay for any hosting."],
        draft=draft(
            must_have=["Instant collaborative editing", "Export to PDF", "Never create files"],
            conflicts=[{"description": "Exporting creates a file.", "requirement_texts": ["Export to PDF", "Never create files"]}],
        ),
    )
    assert len(brief.conflicts) == 2


# --- Questions must belong to the project (a real bug: "hi" got three questions) ----
def test_nothing_is_asked_when_no_project_was_described():
    greeting = draft(describes_project=False, problem=None)
    assert has_project(greeting) is False
    assert questions_for(greeting, already_asked=[]) == []


def test_a_model_that_says_yes_but_wrote_no_problem_is_treated_as_no_project():
    assert has_project(draft(describes_project=True, problem="   ")) is False
    assert has_project(draft(describes_project=True, problem=None)) is False


def test_the_wording_comes_from_the_model_and_only_suggested_topics_are_asked():
    suggested = draft(clarifying_questions=[
        {"topic": "users", "question": "Will your whole team edit the wiki together?", "why_it_matters": "Shared editing needs accounts; solo use does not."},
        {"topic": "sensitive_data", "question": "Will the wiki hold customer records?", "why_it_matters": ""},
    ])
    questions = questions_for(suggested, already_asked=[])
    assert [(q.topic, q.question) for q in questions] == [
        ("users", "Will your whole team edit the wiki together?"),
        ("sensitive_data", "Will the wiki hold customer records?"),
    ]  # deployment, budget and integrations were not suggested, so they are not asked
    assert questions[0].why == "Shared editing needs accounts; solo use does not."
    assert questions[1].why == WHY_TEXT["sensitive_data"]  # a blank reason falls back to the standard one


def test_a_suggested_topic_that_is_already_known_is_not_asked():
    known_deployment = draft(deployment="Local, on one laptop")
    assert "deployment" not in [q.topic for q in questions_for(known_deployment, already_asked=[])]


def test_unusable_wording_falls_back_to_the_standard_question():
    messy = draft(clarifying_questions=[
        {"topic": "users", "question": "   ", "why_it_matters": "x"},
        {"topic": "budget", "question": "x" * 500, "why_it_matters": "x"},
        {"topic": "deployment", "question": "Should the wiki run on your laptop", "why_it_matters": "x"},
    ])
    by_topic = {q.topic: q.question for q in questions_for(messy, already_asked=[])}
    assert by_topic["users"] == QUESTION_TEXT["users"]
    assert by_topic["budget"] == QUESTION_TEXT["budget"]
    assert by_topic["deployment"] == "Should the wiki run on your laptop?"  # a missing "?" is added


def test_the_model_cannot_ask_a_topic_twice_or_more_than_the_limit():
    repeated = draft(clarifying_questions=[{"topic": "users", "question": "A?", "why_it_matters": "a"}, {"topic": "users", "question": "B?", "why_it_matters": "b"}]
                     + [{"topic": t, "question": f"{t}?", "why_it_matters": "r"} for t in TOPIC_ORDER])
    questions = questions_for(repeated, already_asked=[])
    assert len(questions) <= MAX_QUESTIONS
    assert len({q.topic for q in questions}) == len(questions)


# --- Telling a greeting from an idea ----------------------------------------------
@pytest.mark.parametrize("text", ["hi", "Hi!", "hello", "Hey there", "hiii", "test", "ok", "good morning", "???", "👋", "  ", "thanks"])
def test_greetings_and_filler_are_small_talk(text):
    assert is_small_talk(text) is True


@pytest.mark.parametrize("text", [
    "a todo app", "A notes app with tags.", "hi, I want to build a budget app", "CLI to rename photos", "Hello world website",
])
def test_real_ideas_are_not_small_talk(text):
    assert is_small_talk(text) is False


def test_answers_to_questions_do_not_count_as_an_idea():
    assert only_small_talk(["hi", "Answer about deployment: locally"]) is True
    assert only_small_talk(["hi", "A recipe app with a shopping list"]) is False


# --- Enough to draft a brief? ------------------------------------------------------
@pytest.mark.parametrize("texts", [
    ["a todo app"], ["A notes app with tags."], ["CLI to rename photos"], ["hi", "a chat bot for my shop"],
    ["Hello world website"], ["I want an app", "it should track my reading list"],
])
def test_specific_descriptions_are_ready(texts):
    assert idea_readiness(texts).ready is True


@pytest.mark.parametrize("texts", [
    [], ["hi"], ["hello", "hey there"], ["build an app"], ["I want to make something"], ["a new website please"],
    ["test"], ["Answer about deployment: on my laptop"],
])
def test_greetings_and_vague_wishes_are_not_ready_and_say_why(texts):
    result = idea_readiness(texts)
    assert result.ready is False and result.reason


# --- Ordinary words are not constraints (a related bug found while fixing the above) --
@pytest.mark.parametrize("text", [
    "A budget tracker for my team.",
    "Track my monthly budget and expenses.",
    "An app for sharing private photos with family.",
    "A privacy policy generator for small shops.",
])
def test_everyday_uses_of_budget_and_private_are_not_constraints(text):
    assert find_stated_constraints([text]) == []


@pytest.mark.parametrize("sentence", [
    "We have a tight budget.",
    "It has to stay within a small budget.",
    "Keep it private.",
    "It must be private.",
    "The notes should stay private.",
])
def test_real_budget_and_privacy_limits_are_still_found(sentence):
    assert find_stated_constraints([sentence]) == [sentence]
