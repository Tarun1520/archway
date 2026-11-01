"""
Phase 6: roadmap, prompt pack, rubric, export.

Plain-code parts (ordering, the roadmap builder and its checks, prompt writing, the rubric, the links) are tested
directly on a small hand-made state. The whole stage is driven through the API in fixture mode, and with a scripted
model for the cases the fixture does not cover (a failing plan, a retry, a partial export).
"""

import io
import json
import zipfile

from app.models.plan import Roadmap
from app.promptgen.links import build_links
from app.promptgen.render import render_pack
from app.promptgen.rubric import check_pack
from app.roadmap.checks import roadmap_issues
from app.roadmap.draft import build_roadmap, order_tasks, parse_draft
from tests.test_options import app_client, options, researched, scripted
from tests.test_workflow import events_of

# --- A small run, as the plan stage sees it -----------------------------------------------------------------------

OPTION = {
    "id": "OPT-1", "version": 2, "brief_version": 3, "name": "Reuse-first", "summary": "Reuses good-lib for parsing.",
    "trade_off": "less code, more integration", "approved": True,
    "components": [
        {"name": "Parser", "responsibility": "parses", "kind": "reuse", "repo": "acme/good-lib", "candidate_id": "CMP-1"},
        {"name": "App", "responsibility": "the product's own logic", "kind": "build", "repo": None, "candidate_id": None},
    ],
    "reused_repos": [{"repo": "acme/good-lib", "role": "parsing"}],
    "requirement_coverage": {"REQ-1": "covered", "REQ-2": "partial"},
    "validation_tasks": ["Confirm good-lib reads the input format"],
    "review": {"passed": True, "issues": [], "llm_checked": True},
}
OTHER = {**OPTION, "id": "OPT-2", "version": 1, "name": "Build-it-all", "trade_off": "no dependencies, more code", "approved": False}
STATE = {
    "brief": {"version": 3, "problem": "Turn files into notes.", "must_have": [{"id": "REQ-1", "text": "Read the files"}, {"id": "REQ-2", "text": "Show the notes"}],
              "nice_to_have": [], "stack_preferences": [], "constraints": {"stated": ["No paid services."]}, "assumptions": [], "unknowns": []},
    "components": [
        {"id": "CMP-1", "capability_id": "CAP-1", "name": "good-lib", "kind": "building_block", "fit": 3, "provides": "parses",
         "facts": {"reference": "acme/good-lib", "url": "https://github.com/acme/good-lib", "license": "MIT", "evidence_ids": ["ev-1"]}},
        {"id": "CMP-2", "capability_id": "CAP-1", "name": "gpl-parser", "kind": "building_block", "fit": 3, "provides": "parses",
         "facts": {"reference": "acme/gpl-parser", "license": "GPL-3.0", "evidence_ids": ["ev-2"]}},
    ],
    "eligibility": [
        {"component_id": "CMP-1", "status": "eligible", "reasons": [], "decided_by": "rules"},
        {"component_id": "CMP-2", "status": "excluded", "reasons": ["strong copyleft"], "decided_by": "rules"},
    ],
    "receipts": [{"id": "rcpt-1", "candidate_id": "CMP-1", "question_type": "integration_risk", "jev_mode": "fixture", "jev_model_id": "fixture"}],
    "evidence": [{"id": "ev-1", "url": "https://github.com/acme/good-lib#readme"}],
    "options": [OPTION, OTHER],
    "approved_option": {"id": "OPT-1", "version": 2},
}


def task(key, stage, **changes):
    value = {
        "key": key, "title": f"Do {key}", "goal": f"{key} is done", "stage": stage, "kind": "build", "prerequisites": [],
        "scope": f"Implement {key}", "out_of_scope": ["anything else"], "likely_files": [], "interfaces_to_preserve": [],
        "requirement_ids": [], "components": [], "acceptance_criteria": [f"{key} works"], "validation_steps": [f"pytest -k {key}"],
        "risks": [], "validates": [],
    }
    value.update(changes)
    return value


def good_draft():
    return parse_draft({"tasks": [
        task("ui", "frontend", prerequisites=["core"], requirement_ids=["REQ-2"], components=["App"]),
        task("core", "backend_features", prerequisites=["setup", "parse"], requirement_ids=["REQ-1"], components=["App"]),
        task("parse", "integrations", prerequisites=["setup"], components=["Parser"]),
        task("spike", "integrations", kind="spike", prerequisites=["setup"], components=["Parser"], validates=["V-1"]),
        task("setup", "scaffold"),
    ], "decisions": []})


# --- Ordering and the roadmap builder -----------------------------------------------------------------------------


def test_tasks_are_put_in_dependency_order_and_a_loop_is_reported_not_hidden():
    order, looped = order_tasks(["b", "a"], {"a": "scaffold", "b": "frontend"}, set(), {"b": {"a"}, "a": set()})
    assert order == ["a", "b"] and looped == []
    order, looped = order_tasks(["a", "b"], {"a": "scaffold", "b": "scaffold"}, set(), {"a": {"b"}, "b": {"a"}})
    assert sorted(looped) == ["a", "b"]


def test_the_builder_numbers_tasks_in_build_order_and_puts_the_spike_before_the_integration():
    roadmap, issues, notes = build_roadmap(good_draft(), STATE)
    titles = [t.title for t in roadmap.tasks]
    assert titles[0] == "Do setup" and titles.index("Do spike") < titles.index("Do parse") < titles.index("Do core") < titles.index("Do ui")
    by_title = {t.title: t for t in roadmap.tasks}
    assert by_title["Do spike"].id in by_title["Do parse"].prerequisites  # validation before the uncertain work
    assert by_title["Do parse"].evidence_ids == ["ev-1"]  # evidence comes from the component, never from the model
    assert issues == [] and notes == []
    assert roadmap.architecture.id == "OPT-1" and roadmap.architecture.version == 2


def test_links_the_model_invents_are_dropped_and_said():
    draft = parse_draft({"tasks": [task("a", "scaffold", prerequisites=["ghost"], requirement_ids=["REQ-99"], components=["Nonexistent"])]})
    roadmap, _, notes = build_roadmap(draft, STATE)
    only = roadmap.tasks[0]
    assert only.prerequisites == [] and only.requirement_ids == [] and only.components == []
    assert len(notes) == 3


def test_the_first_decision_record_names_the_options_that_were_not_chosen():
    roadmap, _, _ = build_roadmap(good_draft(), STATE)
    adr = roadmap.decisions[0]
    assert adr.id == "ADR-1" and adr.source == "options"
    assert [r.option for r in adr.rejected] == ["OPT-2 v1 Build-it-all"] and "no dependencies" in adr.rejected[0].why


def test_the_roadmap_checks_find_an_uncovered_must_have_an_unsettled_validation_task_and_an_unverifiable_task():
    draft = parse_draft({"tasks": [task("a", "scaffold", requirement_ids=["REQ-1"], validation_steps=[])]})
    roadmap, _, _ = build_roadmap(draft, STATE)
    issues = roadmap_issues(roadmap, STATE)
    assert any("REQ-2" in i for i in issues) and any("V-1" in i for i in issues) and any("no validation steps" in i for i in issues)


# --- Prompts, rubric, links ---------------------------------------------------------------------------------------


def test_every_task_is_in_exactly_one_prompt_and_every_prompt_passes_the_rubric():
    roadmap, _, _ = build_roadmap(good_draft(), STATE)
    files, failures = check_pack(render_pack(roadmap, STATE), roadmap, STATE)
    prompts = [f for f in files if f.kind == "prompt"]
    assert failures == []
    assert sorted(t for p in prompts for t in p.task_ids) == sorted(t.id for t in roadmap.tasks)
    assert all(len(p.rubric) == 8 and all(c.passed for c in p.rubric) for p in prompts)
    integration = next(p for p in prompts if "integrations" in p.path)
    assert "OPT-1 version 2" in integration.content and "license MIT" in integration.content
    assert "requires human review" in integration.content
    assert {"README.md", "ARCHITECTURE.md", "DECISIONS.md", "CONSTRAINTS.md", "verification/acceptance-checklist.md"} <= {f.path for f in files}


def test_the_rubric_fails_a_prompt_that_installs_something_not_allowed_or_names_an_excluded_component():
    draft = good_draft()
    draft.tasks[2].validation_steps = ["pip install requests && pytest"]  # "parse": an install outside the allowed list
    draft.tasks[1].scope = "Use acme/gpl-parser for the hard cases"  # "core": research excluded it
    roadmap, _, _ = build_roadmap(draft, STATE)
    _, failures = check_pack(render_pack(roadmap, STATE), roadmap, STATE)
    assert any("No invented APIs" in f and "requests" in f for f in failures)
    assert any("acme/gpl-parser (not reusable)" in f for f in failures)


def test_links_trace_a_requirement_to_tasks_components_verdicts_receipts_and_evidence():
    roadmap, _, _ = build_roadmap(good_draft(), STATE)
    draft = good_draft()
    draft.tasks[2].requirement_ids = ["REQ-1"]  # the integration task delivers REQ-1 too
    roadmap, _, _ = build_roadmap(draft, STATE)
    link = next(link for link in build_links(roadmap, STATE) if link.requirement_id == "REQ-1")
    parser = next(c for c in link.components if c["name"] == "Parser")
    assert link.coverage == "covered" and parser["eligibility"] == "eligible" and parser["decided_by"] == "rules"
    assert parser["receipt_ids"] == ["rcpt-1"] and parser["evidence"] == [{"id": "ev-1", "url": "https://github.com/acme/good-lib#readme"}]


# --- The stage through the API (fixture mode) ---------------------------------------------------------------------


def approved(client, run_id):
    client.post(f"/api/runs/{run_id}/options/start")
    chosen = options(client, run_id)["presented"][0]["id"]
    client.post(f"/api/runs/{run_id}/options/select", json={"action": "select", "option_id": chosen})
    client.post(f"/api/runs/{run_id}/options/approve", json={"action": "approve"})
    return chosen


def plan(client, run_id):
    return client.get(f"/api/runs/{run_id}/plan").json()


def test_the_plan_is_only_made_when_asked_and_only_for_an_approved_version(tmp_path):
    with app_client(tmp_path) as client:
        run_id = researched(client)
        assert client.post(f"/api/runs/{run_id}/plan/start").status_code == 409  # nothing approved
        assert plan(client, run_id)["requested"] is False
        approved(client, run_id)
        assert plan(client, run_id)["requested"] is False  # approving does not spend anything on a plan


def test_the_whole_stage_plan_prompts_checks_export(tmp_path):
    with app_client(tmp_path) as client:
        run_id = researched(client)
        chosen = approved(client, run_id)
        state = client.post(f"/api/runs/{run_id}/plan/start").json()
        assert state["run"]["status"] == "completed" and state["run"]["outcome"] == "full"
        data = plan(client, run_id)
        assert data["built_for"] == {"id": chosen, "version": 1} and not data["stale"]
        assert data["outcome"] == "full" and data["passed"] is True
        prompts = [f for f in data["files"] if f["kind"] == "prompt"]
        assert prompts and all(all(c["passed"] for c in p["rubric"]) for p in prompts)
        assert data["links"] and all(link["task_ids"] for link in data["links"] if link["requirement_id"].startswith("REQ"))

        archive = zipfile.ZipFile(io.BytesIO(client.get(f"/api/runs/{run_id}/plan/export.zip").content))
        names = archive.namelist()
        assert "build-pack/plan.json" in names and "build-pack/PLAN.md" in names and "build-pack/prompts/01_scaffold.md" in names
        exported = json.loads(archive.read("build-pack/plan.json"))
        assert exported["architecture"] == {"id": chosen, "version": 1} and exported["links"] and exported["decision_receipts"]
        markdown = client.get(f"/api/runs/{run_id}/plan/export.md").text
        assert "Source-to-decision links" in markdown
        # Fixture runs say so, naming the services, in the export and in the pack itself.
        assert exported["fixture_services"] == ["decisions", "github", "language model"] and "FIXTURE MODE" in markdown
        assert "FIXTURE MODE" in archive.read("build-pack/README.md").decode()

        first = prompts[0]["path"]
        assert client.post(f"/api/runs/{run_id}/plan/prompts/complete", json={"path": first, "done": True}).json()["completed"] == [first]
        assert client.post(f"/api/runs/{run_id}/plan/prompts/complete", json={"path": "nope.md", "done": True}).status_code == 404
        assert client.post(f"/api/runs/{run_id}/plan/start").status_code == 409  # already made for this version
        names = [e["event"] for e in events_of(client, run_id)]
        assert "plan_started" in names and "plan_updated" in names


def test_a_change_after_the_plan_makes_it_stale_and_a_new_plan_is_for_the_new_version(tmp_path):
    with app_client(tmp_path) as client:
        run_id = researched(client)
        chosen = approved(client, run_id)
        client.post(f"/api/runs/{run_id}/plan/start")
        client.post(f"/api/runs/{run_id}/options/change", json={"option_id": chosen, "request": "use fewer dependencies"})
        client.post(f"/api/runs/{run_id}/options/select", json={"action": "select", "option_id": chosen})
        client.post(f"/api/runs/{run_id}/options/approve", json={"action": "approve"})
        data = plan(client, run_id)
        assert data["stale"] is True and data["built_for"]["version"] == 1 and data["approved"]["version"] == 2
        client.post(f"/api/runs/{run_id}/plan/start")
        data = plan(client, run_id)
        assert data["stale"] is False and data["built_for"] == {"id": chosen, "version": 2} and data["outcome"] == "full"


def test_a_plan_that_fails_its_checks_gets_one_retry_then_is_exported_as_partial(tmp_path):
    attempts = []

    def unverifiable(user):
        attempts.append("<problems>" in user)
        return {"tasks": [task("only", "scaffold", requirement_ids=[], validation_steps=[])], "decisions": []}

    with app_client(tmp_path, llm=scripted(build_roadmap=unverifiable)) as client:
        run_id = researched(client)
        approved(client, run_id)
        state = client.post(f"/api/runs/{run_id}/plan/start").json()
        data = plan(client, run_id)
        assert attempts == [False, True]  # the retry was told what failed
        assert data["outcome"] == "partial" and data["passed"] is False
        assert any("not covered by any task" in n for n in data["notes"]) and any("Verifiable failed" in n for n in data["notes"])
        assert state["run"]["status"] == "completed" and state["run"]["outcome"] == "partial"
        assert "PARTIAL" in client.get(f"/api/runs/{run_id}/plan/export.md").text
