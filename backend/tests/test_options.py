"""
Phase 5: architecture options, review gate, selection, revision, approval.

Plain-code parts (diagram safety, the builder, the review rules) are tested directly. The whole stage is driven
through the API in fixture mode, and with a scripted model for the cases the fixture does not cover.
"""

import copy

from fastapi.testclient import TestClient

from app.llm.fixture import FixtureLLM, keyword_brief_draft
from app.llm.fixture_options import fixture_draft
from app.main import create_app
from app.options.checks import ModelIssue, apply_review, rule_issues
from app.options.draft import OptionsDraft, build_options
from app.options.mermaid_safe import safe_mermaid
from app.options.versions import presented
from tests.conftest import make_settings
from tests.test_agents import research
from tests.test_workflow import events_of

# --- Plain code ------------------------------------------------------------------------------------------------

STATE = {
    "brief": {"version": 2, "must_have": [{"id": "REQ-1", "text": "Do the main thing"}, {"id": "REQ-2", "text": "Do the second thing"}], "nice_to_have": []},
    "components": [
        {"id": "CMP-1", "capability_id": "CAP-1", "name": "good-lib", "kind": "building_block", "fit": 3, "provides": "does a",
         "facts": {"reference": "acme/good-lib", "evidence_ids": ["ev-1"]}},
        {"id": "CMP-2", "capability_id": "CAP-1", "name": "gpl-lib", "kind": "building_block", "fit": 3, "provides": "does b",
         "facts": {"reference": "acme/gpl-lib", "evidence_ids": ["ev-2"]}},
    ],
    "eligibility": [
        {"component_id": "CMP-1", "status": "eligible", "reasons": []},
        {"component_id": "CMP-2", "status": "excluded", "reasons": ["strong copyleft"]},
    ],
    "evidence": [{"id": "ev-1", "url": "https://example.test/1", "excerpt": "good-lib parses things"}],
    "options": [],
}


def draft_option(**changes):
    option = {
        "key": "A", "name": "Reuse", "trade_off": "less code, more integration", "summary": "reuses good-lib",
        "coverage": [{"requirement_id": "REQ-1", "coverage": "covered", "note": "good-lib does it"}, {"requirement_id": "REQ-9", "coverage": "covered", "note": "not in the brief"}],
        "components": [{"name": "Parser", "responsibility": "parses", "kind": "reuse", "candidate_id": "CMP-1"}],
        "integration_boundaries": "x", "data_flow": "x", "storage_model": "x", "deployment": "x", "security_privacy": "x", "testing_approach": "x",
        "risks": ["r"], "validation_tasks": [], "mermaid": "flowchart LR\n A-->B", "evidence_ids": ["ev-1", "ev-invented"],
        "pros": ["p"], "cons": ["c"], "choose_if": "a", "avoid_if": "b",
        "comparison": [{"dimension": "simplicity", "rating": "good", "note": "few parts"}], "change_summary": None,
    }
    option.update(changes)
    return option


def build(*options, mode="new", keys=(), state=STATE):
    return build_options(OptionsDraft.model_validate({"options": list(options), "no_recommendation_reason": None}), state, mode=mode, keys=list(keys))


def test_a_diagram_is_drawn_only_if_it_is_a_plain_flowchart():
    assert safe_mermaid("```mermaid\nflowchart LR\n  A[App] --> B[(DB)]\n```") == "flowchart LR\n  A[App] --> B[(DB)]"
    for unsafe in (
        "flowchart LR\n A[<img src=x onerror=alert(1)>]-->B", "flowchart LR\n click A call alert()", "sequenceDiagram\n A->>B: hi",
        "graph TD\n A-->B[https://evil.example]", "flowchart LR\n %%{init: {}}%%\n A-->B", "", None, "flowchart LR\n" + " A-->B\n" * 80,
    ):
        assert safe_mermaid(unsafe) is None


def test_the_builder_copies_facts_from_research_and_never_trusts_the_model_for_them():
    built, problems, notes = build(draft_option())
    option = built[0]
    assert option["id"] == "OPT-1" and option["version"] == 1 and option["brief_version"] == 2
    part = option["components"][0]
    assert part["repo"] == "acme/good-lib" and part["candidate_id"] == "CMP-1"  # the name comes from the researched facts
    assert option["reused_repos"] == [{"repo": "acme/good-lib", "role": "parses"}]
    assert option["evidence_ids"] == ["ev-1"]  # the invented evidence id was dropped
    assert "REQ-9" not in option["requirement_coverage"]  # a requirement that is not in the brief
    assert option["requirement_coverage"]["REQ-2"] == "unknown"  # left out by the model: unknown, never "covered"
    assert {d["dimension"] for d in option["comparison"]} == {"simplicity", "effort", "oss_reuse", "integration_risk", "maintainability", "privacy", "cost_exposure", "evidence_coverage"}
    assert next(d for d in option["comparison"] if d["dimension"] == "effort")["rating"] == "unknown"
    assert problems == {} and notes == []


def test_reusing_something_that_is_not_reusable_is_dropped_and_reported():
    for candidate in ("CMP-2", "CMP-404", None):  # excluded, invented, missing
        built, problems, _ = build(draft_option(components=[
            {"name": "Parser", "responsibility": "parses", "kind": "reuse", "candidate_id": candidate},
            {"name": "Own code", "responsibility": "glue", "kind": "build", "candidate_id": None},
        ]))
        assert [c["kind"] for c in built[0]["components"]] == ["build"]
        assert "OPT-1@1" in problems and "only components listed as reusable" in problems["OPT-1@1"][0]


def test_an_unsafe_diagram_is_left_out_with_a_note_and_the_option_survives():
    built, _, notes = build(draft_option(mermaid="flowchart LR\n A[<script>alert(1)</script>]-->B"))
    assert built[0]["mermaid"] is None and any("diagram was left out" in n for n in notes)


def test_at_most_three_options_and_ids_continue_across_drafts():
    built, _, notes = build(*[draft_option(key=k) for k in "ABCD"])
    assert [o["id"] for o in built] == ["OPT-1", "OPT-2", "OPT-3"] and any("only the first 3" in n for n in notes)
    again, _, _ = build(draft_option(), state={**STATE, "options": built})
    assert again[0]["id"] == "OPT-4"


def test_a_revision_is_the_next_version_of_the_same_option_and_never_an_edit():
    first, _, _ = build(draft_option())
    state = {**STATE, "options": first}
    revised, _, _ = build(draft_option(key="OPT-1", change_summary="dropped one dependency"), mode="revise", keys=["OPT-1"], state=state)
    assert (revised[0]["id"], revised[0]["version"], revised[0]["change_summary"]) == ("OPT-1", 2, "dropped one dependency")
    assert first[0]["version"] == 1  # the old version is untouched
    ignored, _, notes = build(draft_option(key="OPT-7"), mode="revise", keys=["OPT-1"], state=state)
    assert ignored == [] and any("was not asked for" in n for n in notes)


def test_the_review_gate_refuses_to_reuse_anything_not_eligible_whatever_the_builder_did():
    """The invariant (Python, not a model's opinion): even a hand-made option that reuses an excluded repo is blocked."""
    built, _, _ = build(draft_option())
    sneaky = copy.deepcopy(built[0])
    sneaky["components"].append({"name": "Sneaky", "responsibility": "x", "kind": "reuse", "repo": "acme/gpl-lib", "candidate_id": "CMP-2"})
    issues = rule_issues(sneaky, STATE, [])
    assert any(i["kind"] == "reuse_not_eligible" and i["severity"] == "blocking" and "excluded" in i["text"] for i in issues)
    assert apply_review(sneaky, issues, [])["review"]["passed"] is False
    assert apply_review(built[0], rule_issues(built[0], STATE, []), [])["review"]["passed"] is True


def test_every_option_needs_pros_and_cons_and_components():
    built, _, _ = build(draft_option(pros=[], cons=[], components=[]))
    kinds = {i["kind"] for i in rule_issues(built[0], STATE, []) if i["severity"] == "blocking"}
    assert kinds == {"missing_pros", "missing_cons", "no_components"}


def test_unsupported_claims_become_validation_tasks_and_do_not_reject_the_option():
    built, _, _ = build(draft_option())
    claims = [ModelIssue(option_id="OPT-1", severity="blocking", kind="unsupported_claim", text="good-lib exports to format X"),
              ModelIssue(option_id="OPT-1", severity="warning", kind="overengineering", text="more than the brief needs")]
    reviewed = apply_review(built[0], rule_issues(built[0], STATE, []), claims)
    assert reviewed["review"]["passed"] is True and reviewed["review"]["llm_checked"] is True
    assert "Validate: good-lib exports to format X" in reviewed["validation_tasks"]
    assert [i["kind"] for i in reviewed["review"]["issues"] if i["source"] == "model"] == ["overengineering"]


def test_a_broken_constraint_found_by_the_model_blocks_the_option_and_no_model_check_is_labelled():
    built, _, _ = build(draft_option())
    blocked = apply_review(built[0], [], [ModelIssue(option_id="OPT-1", severity="blocking", kind="constraint", text="needs a paid service")])
    assert blocked["review"]["passed"] is False
    unchecked = apply_review(built[0], [], None)
    assert unchecked["review"]["passed"] is True and unchecked["review"]["llm_checked"] is False


def test_a_failed_revision_never_hides_the_version_that_was_fine():
    ok = {"id": "OPT-1", "version": 1, "review": {"passed": True}}
    bad = {"id": "OPT-1", "version": 2, "review": {"passed": False}}
    assert presented([ok, bad]) == [ok]


# --- The stage through the API (fixture mode) --------------------------------------------------------------------


def app_client(tmp_path, llm=None, **settings):
    return TestClient(create_app(make_settings(tmp_path / "data", max_llm_calls_per_run=settings.pop("cap", 80), **settings), llm=llm))


def researched(client):
    run_id, _ = research(client)
    return run_id


def options(client, run_id):
    return client.get(f"/api/runs/{run_id}/options").json()


def scripted(**overrides):
    """A fixture model whose option steps can be replaced; every other step behaves as in fixture mode."""
    def responder(step, user):
        if step in overrides:
            reply = overrides[step]
            return reply(user) if callable(reply) else reply
        return keyword_brief_draft(step, user)
    return FixtureLLM(responder=responder)


def test_options_are_only_drafted_when_asked_and_not_before_the_research_ends(tmp_path):
    with app_client(tmp_path) as client:
        run_id = researched(client)
        assert options(client, run_id) == {"requested": False, "options": [], "presented": [], "selected": None, "approved": None, "notes": [], "no_recommendation": False}
        assert client.get(f"/api/runs/{run_id}/state").json()["finished"] is True  # the run rests at the shortlist
        fresh = client.post("/api/projects", json={"name": "other"}).json()["id"]
        assert client.post(f"/api/projects/{fresh}/messages", json={"content": "x"}).status_code == 201
        other = client.post(f"/api/projects/{fresh}/runs", json={}).json()["id"]
        assert client.post(f"/api/runs/{other}/options/start").status_code == 409  # nothing researched yet


def test_the_whole_stage_draft_select_approve(tmp_path):
    with app_client(tmp_path) as client:
        run_id = researched(client)
        state = client.post(f"/api/runs/{run_id}/options/start").json()
        assert state["waiting_for"]["node"] == "select_or_revise" and state["run"]["status"] == "awaiting_selection"
        data = options(client, run_id)
        assert data["requested"] and data["presented"] and not data["no_recommendation"]
        option = next(o for o in data["options"] if o["review"]["passed"])
        assert option["pros"] and option["cons"] and option["mermaid"] and option["trade_off"]
        research_data = client.get(f"/api/runs/{run_id}/research").json()
        eligible = {e["component_id"] for e in research_data["eligibility"] if e["status"] == "eligible"}
        assert {c["candidate_id"] for c in option["components"] if c["kind"] == "reuse"} <= eligible  # only eligible repos are reused

        chosen = data["presented"][0]["id"]
        assert client.post(f"/api/runs/{run_id}/options/select", json={"action": "select", "option_id": "OPT-99"}).status_code == 409
        state = client.post(f"/api/runs/{run_id}/options/select", json={"action": "select", "option_id": chosen}).json()
        assert state["waiting_for"]["node"] == "approve_version" and options(client, run_id)["selected"]["id"] == chosen
        state = client.post(f"/api/runs/{run_id}/options/approve", json={"action": "approve"}).json()
        assert state["finished"] is True
        approved = options(client, run_id)["approved"]
        assert approved == {"id": chosen, "version": 1}
        names = [e["event"] for e in events_of(client, run_id)]
        assert "options_updated" in names and "option_approved" in names
        assert client.post(f"/api/runs/{run_id}/options/start").status_code == 409  # already drafted


def test_a_revision_makes_a_new_version_and_the_old_approval_does_not_carry_over(tmp_path):
    with app_client(tmp_path) as client:
        run_id = researched(client)
        client.post(f"/api/runs/{run_id}/options/start")
        chosen = options(client, run_id)["presented"][0]["id"]
        client.post(f"/api/runs/{run_id}/options/select", json={"action": "select", "option_id": chosen})
        client.post(f"/api/runs/{run_id}/options/approve", json={"action": "approve"})
        assert options(client, run_id)["approved"] == {"id": chosen, "version": 1}

        assert client.post(f"/api/runs/{run_id}/options/change", json={"option_id": "OPT-9", "request": "use fewer dependencies"}).status_code == 409
        state = client.post(f"/api/runs/{run_id}/options/change", json={"option_id": chosen, "request": "use fewer dependencies"}).json()
        assert state["waiting_for"]["node"] == "select_or_revise"
        data = options(client, run_id)
        versions = sorted(o["version"] for o in data["options"] if o["id"] == chosen)
        assert versions == [1, 2]
        assert data["approved"] is None  # approval was for version 1 only
        assert data["presented"] == [{"id": chosen, "version": 2}]
        v2 = next(o for o in data["options"] if o["id"] == chosen and o["version"] == 2)
        assert v2["change_summary"] and v2["approved"] is False and v2["review"]["passed"]
        v1 = next(o for o in data["options"] if o["id"] == chosen and o["version"] == 1)
        assert v1["approved"] is True  # the record of what WAS approved is kept

        client.post(f"/api/runs/{run_id}/options/select", json={"action": "select", "option_id": chosen})
        client.post(f"/api/runs/{run_id}/options/approve", json={"action": "approve"})
        assert options(client, run_id)["approved"] == {"id": chosen, "version": 2}


def test_a_change_can_also_be_asked_for_at_the_approval_step_or_the_selection_step(tmp_path):
    with app_client(tmp_path) as client:
        run_id = researched(client)
        client.post(f"/api/runs/{run_id}/options/start")
        chosen = options(client, run_id)["presented"][0]["id"]
        # at the selection step: needs a request; with one option on offer it needs no option id
        assert client.post(f"/api/runs/{run_id}/options/select", json={"action": "revise"}).status_code == 422
        state = client.post(f"/api/runs/{run_id}/options/select", json={"action": "revise", "request": "fewer parts"}).json()
        assert state["waiting_for"]["node"] == "select_or_revise"
        assert sorted(o["version"] for o in options(client, run_id)["options"] if o["id"] == chosen) == [1, 2]
        # at the approval step
        client.post(f"/api/runs/{run_id}/options/select", json={"action": "select", "option_id": chosen})
        assert client.post(f"/api/runs/{run_id}/options/approve", json={"action": "change"}).status_code == 422
        state = client.post(f"/api/runs/{run_id}/options/approve", json={"action": "change", "request": "even fewer"}).json()
        assert state["waiting_for"]["node"] == "select_or_revise"
        assert options(client, run_id)["approved"] is None and options(client, run_id)["selected"] is None


def test_requests_that_do_not_fit_the_step_are_refused(tmp_path):
    with app_client(tmp_path) as client:
        run_id = researched(client)
        assert client.post(f"/api/runs/{run_id}/options/select", json={"action": "select", "option_id": "OPT-1"}).status_code == 409
        assert client.post(f"/api/runs/{run_id}/options/approve", json={"action": "approve"}).status_code == 409
        client.post(f"/api/runs/{run_id}/options/start")
        assert client.post(f"/api/runs/{run_id}/options/approve", json={"action": "approve"}).status_code == 409  # still at selection
        assert client.post(f"/api/runs/{run_id}/options/start").status_code == 409  # waiting for the person
        assert client.get("/api/runs/nope/options").status_code == 404


def test_a_run_waiting_to_choose_survives_a_server_restart(tmp_path):
    settings = make_settings(tmp_path / "data", max_llm_calls_per_run=80)
    with TestClient(create_app(settings)) as first:
        run_id = researched(first)
        before = first.post(f"/api/runs/{run_id}/options/start").json()
        shown = options(first, run_id)
    with TestClient(create_app(settings)) as second:
        after = second.get(f"/api/runs/{run_id}/state").json()
        assert after["waiting_for"] == before["waiting_for"] and options(second, run_id) == shown
        chosen = shown["presented"][0]["id"]
        assert second.post(f"/api/runs/{run_id}/options/select", json={"action": "select", "option_id": chosen}).json()["waiting_for"]["node"] == "approve_version"


def test_no_recommendation_is_a_valid_outcome_and_a_request_can_guide_a_new_draft(tmp_path):
    def draft(user):
        if "extra_guidance_from_the_person" in user:
            return fixture_draft(user)
        return {"options": [], "no_recommendation_reason": "nothing found covers the second requirement"}

    with app_client(tmp_path, llm=scripted(draft_options=draft)) as client:
        run_id = researched(client)
        state = client.post(f"/api/runs/{run_id}/options/start").json()
        data = options(client, run_id)
        assert state["waiting_for"]["payload"]["no_recommendation"] is True
        assert data["no_recommendation"] and data["presented"] == [] and any("nothing found covers the second requirement" in n for n in data["notes"])
        client.post(f"/api/runs/{run_id}/options/select", json={"action": "revise", "request": "relax the second requirement"})
        data = options(client, run_id)
        assert data["presented"] and not data["no_recommendation"]


def test_one_option_is_fine_when_there_is_no_real_trade_off(tmp_path):
    def draft(user):
        full = fixture_draft(user)
        return {**full, "options": full["options"][:1]}

    with app_client(tmp_path, llm=scripted(draft_options=draft)) as client:
        run_id = researched(client)
        client.post(f"/api/runs/{run_id}/options/start")
        assert len(options(client, run_id)["presented"]) == 1


def test_an_option_that_fails_review_is_redrafted_twice_then_withheld_with_the_reasons(tmp_path):
    reviews = []

    def review(user):
        reviews.append(user)
        return {"issues": [{"option_id": "OPT-1", "severity": "blocking", "kind": "constraint", "text": "needs a paid service"}]}

    llm = scripted(review_options=review)
    with app_client(tmp_path, llm=llm) as client:
        run_id = researched(client)
        client.post(f"/api/runs/{run_id}/options/start")
        data = options(client, run_id)
    drafts = llm.calls.count("draft_options")
    assert drafts == 3 and len(reviews) == 3  # the first draft and exactly two redrafts
    failed_ids = {o["id"] for o in data["options"] if not o["review"]["passed"]}
    assert "OPT-1" in failed_ids
    assert all(o["id"] != "OPT-1" for o in data["options"] if o["id"] in [p["id"] for p in data["presented"]])  # never presented
    assert any("OPT-1" in n and "did not pass review" in n and "needs a paid service" in n for n in data["notes"])


def test_the_model_check_failing_is_said_and_the_options_are_judged_by_rules_alone(tmp_path):
    def broken(user):
        raise ValueError("the reviewing model failed")

    with app_client(tmp_path, llm=scripted(review_options=broken)) as client:
        run_id = researched(client)
        client.post(f"/api/runs/{run_id}/options/start")
        data = options(client, run_id)
    assert data["presented"] and all(o["review"]["llm_checked"] is False for o in data["options"])
    assert any("model check could not run" in n for n in data["notes"])


def test_the_model_call_cap_stops_drafting_and_the_run_can_carry_on_after_it_is_raised(tmp_path):
    llm = scripted()
    with app_client(tmp_path, llm=llm, cap=100) as client:
        run_id = researched(client)
        used = client.get(f"/api/runs/{run_id}/state").json()["usage"][0]["calls"]
    settings = make_settings(tmp_path / "data", max_llm_calls_per_run=used)  # exactly what research used: nothing left
    with TestClient(create_app(settings, llm=scripted())) as client:
        assert client.post(f"/api/runs/{run_id}/options/start").status_code == 200
        assert any(e["event"] == "run_error" and "cap" in e["data"]["message"] for e in events_of(client, run_id))
        assert options(client, run_id)["options"] == []
    raised = make_settings(tmp_path / "data", max_llm_calls_per_run=used + 20)
    with TestClient(create_app(raised, llm=scripted())) as client:
        state = client.post(f"/api/runs/{run_id}/start").json()  # the usual "try again": it resumes where it stopped
        assert state["waiting_for"]["node"] == "select_or_revise" and options(client, run_id)["presented"]


def test_what_the_model_is_shown_names_the_engine_that_made_each_decision_and_hides_nothing_reusable(tmp_path):
    seen = []

    def draft(user):
        seen.append(user)
        return fixture_draft(user)

    with app_client(tmp_path, llm=scripted(draft_options=draft)) as client:
        run_id = researched(client)
        client.post(f"/api/runs/{run_id}/options/start")
    first = seen[0]
    assert "<material>" in first and "reusable_components" in first and "not_reusable_components" in first
    assert "decision_model_answers" in first and '"engine"' in first


def test_eligibility_says_whether_the_rules_or_the_decision_model_decided():
    from app.policy.eligibility import EligibilityPolicy, check_component

    component = {"id": "CMP-1", "fit": 3, "kind": "building_block", "facts": {"license": "MIT", "license_status": "detected"}}
    no = [{"question_type": "requirement_fit", "final_result": "does_not_meet"}]
    verdict = check_component(component, no, EligibilityPolicy())
    assert (verdict.status, verdict.decided_by) == ("unresolved", "decision_model")
    gpl = {**component, "facts": {"license": "GPL-3.0", "license_status": "detected"}}
    assert check_component(gpl, no, EligibilityPolicy()).decided_by == "rules"  # a license rule fires first: not the model's call
    assert check_component(component, [], EligibilityPolicy()).decided_by == "rules"


def test_a_null_field_the_model_left_out_means_null_and_nothing_else_may_be_left_out():
    from pydantic import ValidationError

    from app.options.draft import parse_draft

    option = draft_option()
    del option["change_summary"], option["mermaid"]
    option["components"][0].pop("candidate_id")
    parsed = parse_draft({"options": [option]})  # no "no_recommendation_reason" either
    assert parsed.options[0].change_summary is None and parsed.options[0].mermaid is None and parsed.no_recommendation_reason is None
    broken = draft_option()
    del broken["pros"]
    try:
        parse_draft({"options": [broken]})
    except ValidationError:
        pass
    else:
        raise AssertionError("a missing required field must still be refused")


def test_choosing_an_option_is_announced_so_the_page_reloads_the_selection(tmp_path):
    with app_client(tmp_path) as client:
        run_id = researched(client)
        client.post(f"/api/runs/{run_id}/options/start")
        chosen = options(client, run_id)["presented"][0]["id"]
        before = len([e for e in events_of(client, run_id) if e["event"] == "options_updated"])
        client.post(f"/api/runs/{run_id}/options/select", json={"action": "select", "option_id": chosen})
        updates = [e for e in events_of(client, run_id) if e["event"] == "options_updated"]
        assert len(updates) == before + 1 and updates[-1]["data"] == {"selected": chosen}


def test_a_label_with_a_risky_looking_word_is_fine_but_a_risky_statement_is_not():
    assert safe_mermaid("flowchart LR\nApp[API call to the initial style guide] --> B[(DB)]")
    assert safe_mermaid("flowchart LR\nA-->B\nstyle A fill:#f00") is None
    assert safe_mermaid("flowchart LR\nA-->B\nclick A callback") is None
