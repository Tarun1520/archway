"""
Tests for the research TEAM: the agent loop, the tools' guardrails, and how
the agents work together through the lead.

The "model" is scripted (app/llm/fixture_agents.py, or a script written in
the test), and GitHub, PyPI, npm and web pages are the recorded fixture
world. Every guardrail runs for real.
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agents.runtime import AgentSpec, run_agent
from app.integrations.factory import build_integrations
from app.llm.base import LLMError
from app.llm.fixture import FixtureLLM, keyword_brief_draft
from app.llm.fixture_agents import scripted_reply
from app.main import create_app
from app.models.brief import ProjectBrief, Requirement
from app.models.research import Capability
from app.tools.base import BoardView, RunBudget, ToolContext
from app.tools.github_tools import INSPECT_REPOSITORY, SEARCH_GITHUB
from app.tools.package_tools import LOOKUP_PYPI
from app.tools.report_tools import SUBMIT_COMPONENTS
from app.tools.team_tools import FINISH_RESEARCH
from app.tools.web_tools import READ_WEB_PAGE
from tests.conftest import make_settings
from tests.test_workflow import events_of, new_run

IDEA = "A markdown notes app with tags and offline full-text search. Notes sync between devices. Export notes to HTML."


# --- Helpers ---------------------------------------------------------------------------
def tool_context(tmp_path, *, llm_cap=20, github_cap=20, capabilities=None, assignment=None):
    settings = make_settings(tmp_path / "data")
    brief = ProjectBrief(id="b", version=1, problem="A notes app", confirmed=True,
                         must_have=[Requirement(id="REQ-1", text="Search notes offline")])
    events: list[dict] = []
    ctx = ToolContext(
        integrations=build_integrations(settings),
        budget=RunBudget(llm_cap=llm_cap, llm_used=0, github_cap=github_cap, github_used=0),
        board=BoardView(brief=brief, capabilities=capabilities or []),
        mode="fixture", emit=events.append, assignment=assignment or {},
    )
    return ctx, events


def scripted(*moves):
    """A model that makes exactly these tool calls, in order, then repeats the last."""
    moves = list(moves)
    index = {"n": 0}

    def responder(step, messages):
        move = moves[min(index["n"], len(moves) - 1)]
        index["n"] += 1
        return move

    return FixtureLLM(agent_responder=responder)


def call(name, **arguments):
    return {"name": name, "arguments": arguments}


SCOUT_SPEC = AgentSpec(name="component_scout", instructions="test",
                       tools=(SEARCH_GITHUB, INSPECT_REPOSITORY, LOOKUP_PYPI, SUBMIT_COMPONENTS), max_turns=6)
CAP = Capability(id="CAP-1", name="Search", need="search notes", approaches=["library"])


# --- The agent loop --------------------------------------------------------------------
async def test_an_agent_works_through_tools_and_stops_at_its_report(tmp_path):
    ctx, _ = tool_context(tmp_path, capabilities=[CAP], assignment={"capability_id": "CAP-1"})
    llm = scripted(
        call("search_github", query="markdown notes search"),
        call("inspect_repository", repo="fixture-owner/notes-md"),
        call("submit_components", summary="one option", components=[{
            "source": "github", "reference": "fixture-owner/notes-md", "name": "notes-md", "approach": "library",
            "provides": "search", "fit_notes": "fits"}]),
    )
    turns = await run_agent(SCOUT_SPEC, "<capability>{}</capability>", llm=llm, tools=ctx, config={})
    assert turns == 3 and llm.calls == ["agent:component_scout"] * 3
    component = ctx.outcome["components"][0]
    assert component["facts"]["license"] == "MIT" and component["facts"]["inspected"] is True


async def test_an_agent_cannot_propose_what_it_never_looked_at(tmp_path):
    ctx, _ = tool_context(tmp_path, capabilities=[CAP], assignment={"capability_id": "CAP-1"})
    unverified = call("submit_components", summary="s", components=[{
        "source": "pypi", "reference": "a-library-from-memory", "name": "x", "approach": "library", "provides": "p", "fit_notes": "f"}])
    llm = scripted(unverified, unverified, unverified)
    await run_agent(SCOUT_SPEC, "go", llm=llm, tools=ctx, config={})
    assert ctx.outcome is None  # refused every time; the agent ran out of turns
    assert any("ran out of turns" in note for note in ctx.notes)


async def test_a_search_result_must_be_inspected_before_it_is_proposed(tmp_path):
    ctx, _ = tool_context(tmp_path, capabilities=[CAP], assignment={"capability_id": "CAP-1"})
    propose = call("submit_components", summary="s", components=[{
        "source": "github", "reference": "fixture-owner/notes-md", "name": "notes-md", "approach": "library", "provides": "p", "fit_notes": "f"}])
    llm = scripted(call("search_github", query="markdown notes"), propose,
                   call("inspect_repository", repo="fixture-owner/notes-md"), propose)
    await run_agent(SCOUT_SPEC, "go", llm=llm, tools=ctx, config={})
    assert ctx.outcome is not None and len(ctx.outcome["components"]) == 1  # accepted only after inspection


async def test_unverified_items_are_dropped_but_verified_ones_are_kept(tmp_path):
    ctx, _ = tool_context(tmp_path, capabilities=[CAP], assignment={"capability_id": "CAP-1"})
    llm = scripted(
        call("inspect_repository", repo="fixture-owner/notes-md"),
        call("submit_components", summary="s", components=[
            {"source": "github", "reference": "fixture-owner/notes-md", "name": "notes-md", "approach": "library", "provides": "p", "fit_notes": "f"},
            {"source": "pypi", "reference": "a-library-from-memory", "name": "x", "approach": "library", "provides": "p", "fit_notes": "f"}]),
    )
    await run_agent(SCOUT_SPEC, "go", llm=llm, tools=ctx, config={})
    assert [c["name"] for c in ctx.outcome["components"]] == ["notes-md"]
    assert any("a-library-from-memory" in note for note in ctx.notes)


async def test_an_agent_near_its_turn_limit_is_only_offered_its_report(tmp_path):
    offered: list[list[str]] = []

    class Recording(FixtureLLM):
        async def chat(self, *, step, messages, tools):
            offered.append([tool["function"]["name"] for tool in tools])
            return await super().chat(step=step, messages=messages, tools=tools)

    ctx, _ = tool_context(tmp_path, capabilities=[CAP], assignment={"capability_id": "CAP-1"})
    search = call("search_github", query="markdown notes")
    moves = iter([search] * 4 + [call("submit_components", summary="nothing suitable", components=[])])
    llm = Recording(agent_responder=lambda step, messages: next(moves))
    await run_agent(SCOUT_SPEC, "go", llm=llm, tools=ctx, config={})  # max_turns=6, so turns 5 and 6 wrap up
    assert all("search_github" in names for names in offered[:4])
    assert offered[4] == ["submit_components"]
    assert ctx.outcome is not None  # it reported instead of running out of turns


async def test_facts_come_from_the_tools_not_from_the_agents_words(tmp_path):
    """An agent claiming a license for an unlicensed repository changes nothing."""
    ctx, _ = tool_context(tmp_path, capabilities=[CAP], assignment={"capability_id": "CAP-1"})
    llm = scripted(
        call("inspect_repository", repo="fixture-owner/md-vault"),
        call("submit_components", summary="s", components=[{
            "source": "github", "reference": "fixture-owner/md-vault", "name": "md-vault", "approach": "library", "provides": "p",
            "fit_notes": "MIT licensed and perfect", "license": "MIT"}]),  # "license" is not a field it can set
    )
    await run_agent(SCOUT_SPEC, "go", llm=llm, tools=ctx, config={})
    facts = ctx.outcome["components"][0]["facts"]
    assert facts["license"] is None and facts["license_status"] == "none_detected"


async def test_unknown_tools_and_bad_arguments_are_refused_and_reported_back(tmp_path):
    ctx, events = tool_context(tmp_path, capabilities=[CAP], assignment={"capability_id": "CAP-1"})
    llm = scripted(call("delete_everything"), call("search_github", wrong_field=1),
                   call("submit_components", summary="nothing found", components=[]))
    await run_agent(SCOUT_SPEC, "go", llm=llm, tools=ctx, config={})
    actions = [(e["tool"], e["ok"]) for e in events if e.get("event") == "agent_action"]
    assert ("search_github", False) in actions and ctx.outcome == {"components": [], "summary": "nothing found"}


async def test_the_model_budget_stops_an_agent(tmp_path):
    ctx, _ = tool_context(tmp_path, llm_cap=2, capabilities=[CAP], assignment={"capability_id": "CAP-1"})
    llm = scripted(call("search_github", query="notes"))
    await run_agent(SCOUT_SPEC, "go", llm=llm, tools=ctx, config={})
    assert len(llm.calls) == 2 and any("budget was used up" in note for note in ctx.notes)


async def test_the_github_budget_is_enforced_by_the_tool(tmp_path):
    ctx, _ = tool_context(tmp_path, github_cap=1, capabilities=[CAP], assignment={"capability_id": "CAP-1"})
    llm = scripted(call("search_github", query="notes"), call("search_github", query="search"),
                   call("submit_components", summary="s", components=[]))
    await run_agent(SCOUT_SPEC, "go", llm=llm, tools=ctx, config={})
    assert ctx.budget.github_used == 1


async def test_unsafe_addresses_are_refused_by_the_page_tool_and_recorded(tmp_path):
    ctx, _ = tool_context(tmp_path)
    from app.tools.web_tools import ReadWebPageArgs, read_web_page

    result = await read_web_page(ReadWebPageArgs(url="https://localhost/admin"), ctx)
    assert not result.ok and "local name" in result.content
    assert ctx.evidence[0].extraction_status == "failed" and ctx.evidence[0].excerpt is None


async def test_a_package_is_verified_by_lookup(tmp_path):
    ctx, _ = tool_context(tmp_path)
    from app.tools.package_tools import LookupArgs, lookup_pypi

    found = json.loads((await lookup_pypi(LookupArgs(name="fixture-doc-parser"), ctx)).content)
    assert found["found"] and found["license"] == "MIT"
    assert ctx.known("pypi", "fixture-doc-parser").inspected
    missing = json.loads((await lookup_pypi(LookupArgs(name="no-such-package-xyz"), ctx)).content)
    assert missing["found"] is False and ctx.known("pypi", "no-such-package-xyz") is None


async def test_the_lead_cannot_finish_before_the_work_is_reviewed(tmp_path):
    ctx, _ = tool_context(tmp_path, capabilities=[CAP])
    from app.tools.team_tools import FinishArgs, finish_research

    refused = await finish_research(FinishArgs(summary="done"), ctx)
    assert not refused.ok and "never scouted" in refused.content
    ctx.board.scout_rounds = {"CAP-1": 1}
    refused = await finish_research(FinishArgs(summary="done"), ctx)
    assert not refused.ok and "reviewer" in refused.content
    ctx.board.review_is_fresh = True
    assert (await finish_research(FinishArgs(summary="done"), ctx)).ok


# --- The whole team, through the API ----------------------------------------------------------
def research(client, idea=IDEA):
    run_id = new_run(client, idea)
    client.post(f"/api/runs/{run_id}/start")
    client.post(f"/api/runs/{run_id}/clarify", json={"continue_with_assumptions": True})
    state = client.post(f"/api/runs/{run_id}/confirm", json={"action": "approve"}).json()
    return run_id, state


def test_the_team_researches_an_approved_brief_and_talks_through_the_lead(tmp_path):
    with TestClient(create_app(make_settings(tmp_path / "data", max_llm_calls_per_run=40))) as client:
        run_id, state = research(client)
        assert state["finished"] and state["run"]["status"] == "researching"
        data = client.get(f"/api/runs/{run_id}/research").json()

        assert data["finished"] and data["capabilities"] and data["components"]
        assert {c["capability_id"] for c in data["components"]} <= {c["id"] for c in data["capabilities"]}
        for component in data["components"]:
            assert component["facts"]["inspected"] and component["facts"]["evidence_ids"]
        assert data["review"]["complete"] is True
        # The conversation: every specialist was given a task by the lead and reported back.
        senders = [m["sender"] for m in data["messages"]]
        for agent in ("capability_analyst", "component_scout", "project_scout", "reviewer"):
            assert agent in senders
        tasks = [m for m in data["messages"] if m["sender"] == "research_lead" and m["kind"] == "task"]
        assert [t["recipient"] for t in tasks][:2] == ["capability_analyst", "component_scout"]


def test_scouts_for_several_capabilities_run_in_the_same_step(tmp_path):
    with TestClient(create_app(make_settings(tmp_path / "data", max_llm_calls_per_run=60))) as client:
        run_id, _ = research(client)
        data = client.get(f"/api/runs/{run_id}/research").json()
        assert len(data["capabilities"]) >= 2
        events = events_of(client, run_id)
        scout_starts = [i for i, e in enumerate(events) if e["event"] == "node_started" and e["data"].get("node") == "component_scout"]
        assert len(scout_starts) == len(data["capabilities"])
        # All scouts started before any of them reported back (they ran together).
        first_report = next(i for i, e in enumerate(events) if e["event"] == "team_message" and e["data"]["sender"] == "component_scout")
        assert max(scout_starts) < first_report


def test_a_low_model_budget_ends_the_research_with_a_visible_note(tmp_path):
    with TestClient(create_app(make_settings(tmp_path / "data", max_llm_calls_per_run=4))) as client:
        run_id, state = research(client)
        data = client.get(f"/api/runs/{run_id}/research").json()
        assert state["finished"] is True and data["finished"] is True
        assert any("budget" in note for note in data["notes"])


def test_a_single_model_failure_costs_one_agent_not_the_run(tmp_path):
    failures = {"left": 1}

    def agent_responder(step, messages):
        if step == "agent:component_scout" and failures["left"]:
            failures["left"] -= 1
            raise KeyError("simulated hiccup")  # FixtureLLM turns this into an LLMError
        return scripted_reply(step, messages)

    llm = FixtureLLM(agent_responder=agent_responder)
    with TestClient(create_app(make_settings(tmp_path / "data", max_llm_calls_per_run=60), llm=llm)) as client:
        run_id, state = research(client)
        assert state["finished"] is True
        notes = client.get(f"/api/runs/{run_id}/research").json()["notes"]
        assert any("stopped early: the model failed" in note for note in notes)


def test_a_model_outage_stops_the_run_and_it_resumes_later(tmp_path):
    outage = {"on": True}

    def agent_responder(step, messages):
        if step == "agent:component_scout" and outage["on"]:
            raise KeyError("simulated outage")  # every scout call fails while the outage lasts
        return scripted_reply(step, messages)

    llm = FixtureLLM(agent_responder=agent_responder)
    with TestClient(create_app(make_settings(tmp_path / "data", max_llm_calls_per_run=60), llm=llm)) as client:
        run_id, state = research(client)
        assert state["finished"] is False and state["running"] is False
        assert any(e["event"] == "run_error" for e in events_of(client, run_id))

        outage["on"] = False
        state = client.post(f"/api/runs/{run_id}/start").json()  # carry on from the last checkpoint
        assert state["finished"] is True
        assert client.get(f"/api/runs/{run_id}/research").json()["finished"] is True


def test_research_survives_a_restart(tmp_path):
    settings = make_settings(tmp_path / "data", max_llm_calls_per_run=40)
    with TestClient(create_app(settings)) as first:
        run_id, _ = research(first)
        before = first.get(f"/api/runs/{run_id}/research").json()
    with TestClient(create_app(settings)) as second:
        assert second.get(f"/api/runs/{run_id}/research").json() == before


def test_approval_returns_at_once_when_research_runs_in_the_background(tmp_path):
    import time

    settings = make_settings(tmp_path / "data", max_llm_calls_per_run=40, background_research=True)
    with TestClient(create_app(settings)) as client:
        run_id, state = research(client)
        assert state["running"] is True or state["finished"] is True  # answered at once; the team works on
        for _ in range(100):  # the team works in the background; wait for it
            state = client.get(f"/api/runs/{run_id}/state").json()
            if state["finished"]:
                break
            time.sleep(0.05)
        assert state["finished"] and not state["running"]
        assert state["brief"]["confirmed"] is True
        assert client.get(f"/api/runs/{run_id}/research").json()["components"]


async def test_an_agent_is_told_why_its_call_was_rejected_and_can_correct_it(tmp_path):
    from app.llm.base import ChatResult, ToolCall

    class RejectThenAccept(FixtureLLM):
        def __init__(self):
            super().__init__()
            self.seen: list[list[dict]] = []

        async def chat(self, *, step, messages, tools):
            self.seen.append(messages)
            if len(self.seen) == 1:
                return ChatResult(content=None, tool_calls=[], model="m", input_tokens=None, output_tokens=None,
                                  problem="Tool call validation failed: missing properties: 'name'")
            arguments = {"components": [], "summary": "nothing suitable found"}
            return ChatResult(content=None, tool_calls=[ToolCall("c", "submit_components", arguments, json.dumps(arguments))],
                              model="m", input_tokens=None, output_tokens=None)

    ctx, _ = tool_context(tmp_path, capabilities=[CAP], assignment={"capability_id": "CAP-1"})
    llm = RejectThenAccept()
    await run_agent(SCOUT_SPEC, "go", llm=llm, tools=ctx, config={})
    assert ctx.outcome == {"components": [], "summary": "nothing suitable found"}
    assert "was rejected" in llm.seen[1][-1]["content"] and "missing properties" in llm.seen[1][-1]["content"]


async def test_an_id_the_model_wrote_into_a_capability_name_is_removed(tmp_path):
    from app.tools.report_tools import RECORD_CAPABILITIES
    ctx, _ = tool_context(tmp_path)
    args = RECORD_CAPABILITIES.args.model_validate({"capabilities": [
        {"name": "CAP-1: Document parsing", "need": "read pdfs", "approaches": ["library"], "priority": "core",
         "requirement_ids": ["REQ-1"]}]})
    result = await RECORD_CAPABILITIES.run(args, ctx)
    assert result.ok and ctx.outcome["capabilities"][0]["name"] == "Document parsing"


# --- Fewer model calls, fewer wasted searches ---------------------------------------------
def _fake_github(answers):
    """A GitHub stand-in that answers each search from `answers` (a list), and records the queries."""
    import types

    from app.integrations.github_client import GitHubRateLimited
    seen: list[str] = []

    async def search_repositories(query, per_page=8):
        seen.append(query)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return types.SimpleNamespace(candidates=answer, provenance=types.SimpleNamespace(requested=True))

    return types.SimpleNamespace(search_repositories=search_repositories, mode="fixture"), seen, GitHubRateLimited


async def _search(tmp_path, answers, query="food image recognition portion estimation language:python"):
    from app.tools.github_tools import SEARCH_GITHUB
    ctx, events_seen = tool_context(tmp_path)
    github, seen, _ = _fake_github(answers)
    ctx.integrations = type("I", (), {"github": github})()
    result = await SEARCH_GITHUB.run(SEARCH_GITHUB.args.model_validate({"query": query}), ctx)
    return result, seen, ctx


def test_a_search_that_finds_nothing_is_retried_with_fewer_words():
    from app.tools.github_tools import relaxed_queries
    assert relaxed_queries("food image recognition portion estimation language:python") == [
        "food image recognition language:python", "food image language:python"]
    assert relaxed_queries("python fastapi language:python") == []  # the language word is not a keyword


async def test_the_search_tool_relaxes_an_empty_query_without_asking_the_model(tmp_path):
    from datetime import datetime, timezone

    from app.models.research import Candidate
    hit = Candidate(repo="o/n", url="https://github.com/o/n", description="d", retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    result, seen, _ = await _search(tmp_path, [[], [hit]])
    assert len(seen) == 2 and len(seen[1].split()) < len(seen[0].split())
    assert "o/n" in result.content and "shorter query" in result.content


async def test_a_short_github_rate_limit_is_waited_out_inside_the_tool(tmp_path, monkeypatch):
    from app.integrations.github_client import GitHubRateLimited
    from app.tools import github_tools
    waits: list[float] = []

    async def fake_wait(seconds):
        waits.append(seconds)

    monkeypatch.setattr(github_tools, "wait", fake_wait)
    result, seen, _ = await _search(tmp_path, [GitHubRateLimited("limit", 12.0), [], [], []])
    assert waits == [13.0] and len(seen) >= 2 and result.ok  # waited once, then searched again


async def test_a_long_github_rate_limit_is_reported_not_waited_out(tmp_path, monkeypatch):
    from app.integrations.github_client import GitHubRateLimited
    from app.tools import github_tools
    waits: list[float] = []

    async def fake_wait(seconds):
        waits.append(seconds)

    monkeypatch.setattr(github_tools, "wait", fake_wait)
    result, _, ctx = await _search(tmp_path, [GitHubRateLimited("limit", 300.0)])
    assert not waits and not result.ok and any("rate limit" in n for n in ctx.notes)


async def test_several_tool_calls_in_one_reply_cost_one_model_call(tmp_path):
    ctx, _ = tool_context(tmp_path, capabilities=[CAP], assignment={"capability_id": "CAP-1"})
    llm = scripted(
        [call("search_github", query="markdown notes"), {"name": "lookup_pypi", "arguments": {"name": "pytest"}}, call("inspect_repository", repo="fixture-owner/notes-md")],
        call("submit_components", summary="s", components=[{
            "source": "github", "reference": "fixture-owner/notes-md", "name": "notes-md", "approach": "library",
            "provides": "p", "fit_notes": "f"}]),
    )
    turns = await run_agent(SCOUT_SPEC, "go", llm=llm, tools=ctx, config={})
    assert turns == 2 and len(llm.calls) == 2  # three tools, one model call
    assert ctx.outcome is not None


def test_a_reworded_approach_is_matched_to_the_listed_one():
    from app.tools.report_tools import resolve_approach
    listed = ["Hybrid heuristic image analysis with OpenCV plus shallow ML models", "Self-hosted deep learning food recognition"]
    assert resolve_approach("A2", listed) == listed[1]
    assert resolve_approach("hybrid heuristic image analysis with opencv plus shallow ml", listed) == listed[0]
    assert resolve_approach("quantum blockchain", listed) is None


def test_repeated_notes_are_reported_once():
    import types

    from app.agents.team_board import produced
    tools = types.SimpleNamespace(evidence=[], repos=[], new_facts=[], notes=["a", "b", "a", "a"])
    assert produced(tools)["research_notes"] == ["a", "b"]


async def test_inspecting_a_repository_seen_in_a_search_does_not_ask_for_its_license_again(tmp_path):
    import types
    from datetime import datetime, timezone

    from app.integrations.github_client import Provenance, ReadmeOutcome
    from app.models.research import Candidate
    from app.tools.github_tools import INSPECT_REPOSITORY, SEARCH_GITHUB

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    calls: list[str] = []

    async def search_repositories(query, per_page=8):
        calls.append("search")
        hit = Candidate(repo="o/n", url="https://github.com/o/n", license="MIT", retrieved_at=now)
        return types.SimpleNamespace(candidates=[hit], provenance=Provenance(now, False, True))

    async def get_readme(repo):
        calls.append("readme")
        return ReadmeOutcome(text="# n\nA tool.", found=True, truncated=False, html_url=None, provenance=Provenance(now, False, True))

    async def get_license(repo):
        calls.append("license")
        raise AssertionError("the license was already known from the search")

    ctx, _ = tool_context(tmp_path)
    github = types.SimpleNamespace(search_repositories=search_repositories, get_readme=get_readme,
                                   get_license=get_license, mode="fixture")
    ctx.integrations = type("I", (), {"github": github})()
    await SEARCH_GITHUB.run(SEARCH_GITHUB.args.model_validate({"query": "tool"}), ctx)
    before = ctx.budget.github_used
    result = await INSPECT_REPOSITORY.run(INSPECT_REPOSITORY.args.model_validate({"repo": "o/n"}), ctx)
    assert result.ok and calls == ["search", "readme"]
    assert ctx.budget.github_used - before == 1  # one request (the README) was the whole cost
    assert ctx.known("github", "o/n").license == "MIT"


def test_a_github_token_raises_the_cap_a_run_may_use(tmp_path):
    from pydantic import SecretStr
    plain = make_settings(tmp_path / "a")
    with_token = make_settings(tmp_path / "b", github_token=SecretStr("t"))
    assert with_token.github_calls_cap == plain.github_calls_cap * 3


# --- The blind relevance judge --------------------------------------------------------------
def _judging(verdict_for):
    """A fixture model whose relevance judge answers `verdict_for(index) -> (fit, kind)`; everyone else is scripted."""
    from app.llm.fixture_agents import _tagged

    def responder(step, messages):
        if step != "agent:relevance_judge":
            return scripted_reply(step, messages)
        candidates = _tagged(next(m["content"] for m in messages if m["role"] == "user"), "candidates")
        return {"name": "submit_fit", "arguments": {"assessments": [
            {"id": c["id"], "fit": verdict_for(i)[0], "kind": verdict_for(i)[1], "reason": f"judged {i}"}
            for i, c in enumerate(candidates)]}}

    return FixtureLLM(agent_responder=responder)


def test_the_judge_never_sees_what_the_scout_claimed():
    from app.agents.relevance_judge import _candidate_view
    import types

    component = {"id": "c1", "name": "n", "approach": "A", "provides": "SECRET CLAIM", "fit_notes": "SECRET PITCH",
                 "facts": {"kind": "github", "reference": "o/n", "description": "what it really is", "evidence_ids": []}}
    view = _candidate_view(component, types.SimpleNamespace(evidence=[], pending={}))
    assert "SECRET" not in json.dumps(view) and view["description"] == "what it really is"


def test_a_component_the_judge_calls_unrelated_is_removed_and_a_reference_is_kept_with_its_verdict(tmp_path):
    verdicts = {0: (0, "building_block")}  # the first candidate of every capability is unrelated
    llm = _judging(lambda i: verdicts.get(i, (1, "reference_app")))
    with TestClient(create_app(make_settings(tmp_path / "data", max_llm_calls_per_run=80), llm=llm)) as client:
        run_id, _ = research(client)
        result = client.get(f"/api/runs/{run_id}/research").json()
    assert any("Removed as unrelated" in note for note in result["notes"])
    kept = result["components"]
    assert kept and all(c["fit"] == 1 and c["kind"] == "reference_app" and c["fit_reason"] for c in kept)


def test_judged_fit_is_stored_on_components(tmp_path):
    llm = _judging(lambda i: (3, "building_block"))
    with TestClient(create_app(make_settings(tmp_path / "data", max_llm_calls_per_run=80), llm=llm)) as client:
        run_id, _ = research(client)
        kept = client.get(f"/api/runs/{run_id}/research").json()["components"]
    assert kept and all(c["fit"] == 3 and c["kind"] == "building_block" for c in kept)


async def test_a_must_have_that_no_capability_serves_is_pushed_back_once(tmp_path):
    from app.tools.report_tools import RECORD_CAPABILITIES
    ctx, _ = tool_context(tmp_path)  # the brief has one must-have: REQ-1
    unserved = RECORD_CAPABILITIES.args.model_validate({"capabilities": [
        {"name": "Search", "need": "find notes", "approaches": ["library"], "priority": "core"}]})
    first = await RECORD_CAPABILITIES.run(unserved, ctx)
    assert not first.ok and "REQ-1" in first.content and "plain_product_logic" in first.content
    second = await RECORD_CAPABILITIES.run(unserved, ctx)  # a stubborn model still gets a result
    assert second.ok and any("REQ-1" in note for note in ctx.notes)


async def test_declaring_a_requirement_plain_product_logic_satisfies_the_check(tmp_path):
    from app.tools.report_tools import RECORD_CAPABILITIES
    ctx, _ = tool_context(tmp_path)
    args = RECORD_CAPABILITIES.args.model_validate({
        "capabilities": [{"name": "Search", "need": "find notes", "approaches": ["library"], "priority": "core"}],
        "plain_product_logic": ["REQ-1"],
    })
    assert (await RECORD_CAPABILITIES.run(args, ctx)).ok and not ctx.notes


async def test_a_finished_app_can_never_be_a_direct_fit(tmp_path):
    from app.tools.report_tools import SUBMIT_FIT
    ctx, _ = tool_context(tmp_path, assignment={"component_ids": ["a", "b"]})
    args = SUBMIT_FIT.args.model_validate({"assessments": [
        {"id": "a", "fit": 3, "kind": "reference_app", "reason": "a demo"},
        {"id": "b", "fit": 3, "kind": "building_block", "reason": "a library"}]})
    assert (await SUBMIT_FIT.run(args, ctx)).ok
    assert ctx.outcome["assessments"]["a"]["fit"] == 1 and ctx.outcome["assessments"]["b"]["fit"] == 3


async def test_a_report_naming_unverified_components_is_sent_back_once(tmp_path):
    from app.tools.report_tools import SUBMIT_COMPONENTS
    ctx, _ = tool_context(tmp_path, capabilities=[CAP], assignment={"capability_id": "CAP-1"})
    await INSPECT_REPOSITORY.run(INSPECT_REPOSITORY.args.model_validate({"repo": "fixture-owner/notes-md"}), ctx)
    report = SUBMIT_COMPONENTS.args.model_validate({"summary": "s", "components": [
        {"source": "github", "reference": "fixture-owner/notes-md", "name": "notes-md", "approach": "library", "provides": "p", "fit_notes": "f"},
        {"source": "github", "reference": "big/never-opened", "name": "big", "approach": "library", "provides": "p", "fit_notes": "f"}]})
    first = await SUBMIT_COMPONENTS.run(report, ctx)
    assert not first.ok and "big/never-opened" in first.content and "Inspect or look up" in first.content
    second = await SUBMIT_COMPONENTS.run(report, ctx)  # still unverified: dropped, the rest accepted
    assert second.ok and [c["name"] for c in ctx.outcome["components"]] == ["notes-md"]


# --- Discussion and web search (leads, never facts) -----------------------------------------
def _forum_transport():
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.host == "hn.algolia.com":
            return httpx.Response(200, json={"hits": [
                {"title": "Show HN: Open-source voice agent framework", "url": "https://example.org/a", "points": 40,
                 "num_comments": 12, "objectID": "1", "created_at_i": 1_760_000_000},
                {"title": "Low points story", "url": "https://example.org/b", "points": 0, "objectID": "2"},
                {"title": "Ask HN: best TTS?", "points": 9, "num_comments": 3, "objectID": "3", "created_at_i": 1_760_000_000}]})
        if request.url.host == "api.stackexchange.com":
            return httpx.Response(200, json={"items": [
                {"title": "How to do TTS &amp; STT in <b>React Native</b>?", "link": "https://stackoverflow.com/q/1",
                 "score": 6, "answer_count": 2, "creation_date": 1_760_000_000}]})
        return httpx.Response(404)
    return httpx.MockTransport(answer)


async def test_discussion_search_merges_sources_filters_noise_and_cleans_text():
    from app.integrations.discussion_client import DiscussionClient
    hits, problems = await DiscussionClient(mode="live", transport=_forum_transport()).search("voice agent")
    titles = [h.title for h in hits]
    assert problems == [] and "Low points story" not in titles
    assert "How to do TTS & STT in React Native?" in titles  # entities and tags cleaned
    ask = next(h for h in hits if h.title.startswith("Ask HN"))
    assert ask.url == "https://news.ycombinator.com/item?id=3"  # a thread without a link points to the thread


async def test_one_failing_forum_is_reported_not_fatal():
    from app.integrations.discussion_client import DiscussionClient

    def answer(request):
        return httpx.Response(500) if request.url.host == "hn.algolia.com" else httpx.Response(200, json={"items": [
            {"title": "t", "link": "https://stackoverflow.com/q/2", "score": 1, "answer_count": 0, "creation_date": 1_760_000_000}]})

    hits, problems = await DiscussionClient(mode="live", transport=httpx.MockTransport(answer)).search("x")
    assert len(hits) == 1 and any("Hacker News" in p for p in problems)


async def test_the_discussion_tool_says_its_results_are_leads(tmp_path):
    from app.tools.discussion_tools import SEARCH_DISCUSSIONS
    ctx, _ = tool_context(tmp_path)  # fixture mode: a fixed pair of threads
    result = await SEARCH_DISCUSSIONS.run(SEARCH_DISCUSSIONS.args.model_validate({"query": "voice agent framework"}), ctx)
    body = json.loads(result.content)
    assert result.ok and body["results"] and "Verify any tool" in body["note"]


async def test_web_search_is_refused_without_a_key_and_parses_results_with_one(tmp_path):
    from app.integrations.web_search_client import WebSearchClient
    from app.tools.discussion_tools import SEARCH_WEB
    ctx, _ = tool_context(tmp_path)
    refused = await SEARCH_WEB.run(SEARCH_WEB.args.model_validate({"query": "tts"}), ctx)
    assert not refused.ok and "not configured" in refused.content

    seen = {}

    def answer(request: httpx.Request) -> httpx.Response:
        seen["token"] = request.headers.get("x-subscription-token")
        return httpx.Response(200, json={"web": {"results": [
            {"title": "<strong>Best</strong> TTS libraries", "url": "https://example.org/tts", "description": "A list &amp; more"}]}})

    ctx.integrations = type("I", (), {"web_search": WebSearchClient(api_key="k", transport=httpx.MockTransport(answer))})()
    found = json.loads((await SEARCH_WEB.run(SEARCH_WEB.args.model_validate({"query": "tts"}), ctx)).content)
    assert seen["token"] == "k" and found["results"][0]["title"] == "Best TTS libraries"
    assert found["results"][0]["description"] == "A list & more"


def test_the_scout_is_offered_web_search_only_when_it_is_configured():
    from app.agents.component_scout import SPEC, spec_for
    import types
    assert "search_web" not in [t.name for t in spec_for(types.SimpleNamespace(web_search=None)).tools]
    with_web = spec_for(types.SimpleNamespace(web_search=object()))
    assert "search_web" in [t.name for t in with_web.tools] and with_web.tools[-1].name == "submit_components"
    assert "search_discussions" in [t.name for t in SPEC.tools]


# --- Curated lists and adoption ---------------------------------------------------------------
def test_entries_are_read_from_a_curated_list_without_repeats_or_other_lists():
    from app.tools.curated_tools import list_entries
    readme = """# Awesome TTS
- [Piper](https://github.com/rhasspy/piper) - Fast, local neural **text to speech**.
- [Piper again](https://github.com/rhasspy/piper/) - duplicate.
- [Other list](https://github.com/someone/awesome-voice) - not a project.
- [Kokoro](https://github.com/hexgrad/kokoro#readme): An open-weight TTS model.
- [Self](https://github.com/me/awesome-tts)
"""
    entries = list_entries(readme, "me/awesome-tts")
    assert [e["repo"] for e in entries] == ["rhasspy/piper", "hexgrad/kokoro"]
    assert entries[0]["description"] == "Fast, local neural text to speech"


async def test_package_downloads_are_read_and_failures_are_unknown_not_zero():
    from app.integrations.adoption_client import NPM_DOWNLOADS_BASE, PYPISTATS_BASE, AdoptionClient
    from app.integrations.http_json import JsonHttp

    def answer(request):
        if request.url.host == "api.npmjs.org":
            return httpx.Response(200, json={"downloads": 12345})
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(answer)
    client = AdoptionClient(npm=JsonHttp(base_url=NPM_DOWNLOADS_BASE, service="npm downloads", transport=transport),
                            pypi=JsonHttp(base_url=PYPISTATS_BASE, service="pypistats", transport=transport))
    assert await client.downloads_last_month("npm", "@scope/pkg") == 12345
    assert await client.downloads_last_month("pypi", "missing") is None
    assert await client.downloads_last_month("github", "o/n") is None


async def test_a_second_round_needs_an_open_gap(tmp_path):
    from app.models.research import ReviewGap, ReviewVerdict
    from app.tools.team_tools import AskScoutsArgs, ask_component_scouts
    other = Capability(id="CAP-2", name="Sync", need="sync notes", approaches=["library"])
    ctx, _ = tool_context(tmp_path, capabilities=[CAP, other])
    ctx.board.scout_rounds = {"CAP-1": 1, "CAP-2": 1}
    ctx.board.review = ReviewVerdict(complete=False, gaps=[ReviewGap(capability_id="CAP-2", missing="x")], scouting_seen=2)
    refused = await ask_component_scouts(AskScoutsArgs(capability_ids=["CAP-1", "CAP-2"], instructions="again"), ctx)
    assert not refused.ok and "CAP-1" in refused.content and "no gap" in refused.content
    assert (await ask_component_scouts(AskScoutsArgs(capability_ids=["CAP-2"], instructions="close it"), ctx)).ok


def test_a_package_and_its_github_repo_are_one_component():
    import types

    from app.models.research import SourceFacts
    from app.tools.report_tools import identity, merge_duplicates
    from app.tools.facts import github_repo_of
    assert github_repo_of("git+https://github.com/expressjs/multer.git") == "expressjs/multer"
    assert github_repo_of("https://github.com/taskforcesh/bullmq/tree/master") == "taskforcesh/bullmq"
    npm = SourceFacts(kind="npm", reference="multer", url="u", downloads_last_month=100, source_repo="expressjs/multer", evidence_ids=["a"])
    gh = SourceFacts(kind="github", reference="expressjs/multer", url="u", stars=12000, evidence_ids=["b", "c"])
    other = SourceFacts(kind="npm", reference="busboy", url="u")
    item = lambda name: types.SimpleNamespace(name=name)  # noqa: E731
    assert identity(npm) == identity(gh)
    kept, skipped = merge_duplicates([(item("Multer (GitHub)"), gh), (item("multer"), npm), (item("busboy"), other)], set())
    assert [i.name for i, _ in kept] == ["multer", "busboy"] and skipped == ["Multer (GitHub)"]
    merged = kept[0][1]
    assert merged.kind == "npm" and merged.stars == 12000 and merged.downloads_last_month == 100 and merged.evidence_ids == ["a", "b", "c"]
    again, skipped_again = merge_duplicates([(item("multer"), npm)], {identity(gh)})
    assert again == [] and skipped_again == ["multer"]  # already proposed for this capability


async def test_http_addresses_are_read_over_https(tmp_path):
    from app.tools.web_tools import READ_WEB_PAGE
    ctx, _ = tool_context(tmp_path)
    asked = {}

    class Fetcher:
        async def fetch(self, url):
            asked["url"] = url
            from app.integrations.safe_fetch import FetchRefused
            raise FetchRefused("unsafe", "stop here")

    ctx.integrations = type("I", (), {"fetcher": Fetcher()})()
    await READ_WEB_PAGE.run(READ_WEB_PAGE.args.model_validate({"url": "http://fdc.example.org/api-key-signup.html"}), ctx)
    assert asked["url"] == "https://fdc.example.org/api-key-signup.html"


def test_the_judge_can_refile_a_component_under_the_approach_it_really_is(tmp_path):
    verdicts = {}

    def responder(step, messages):
        from app.llm.fixture_agents import _tagged
        if step != "agent:relevance_judge":
            return scripted_reply(step, messages)
        candidates = _tagged(next(m["content"] for m in messages if m["role"] == "user"), "candidates")
        return {"name": "submit_fit", "arguments": {"assessments": [
            {"id": c["id"], "fit": 3, "kind": "building_block", "reason": "r", "approach": 2} for c in candidates]}}

    with TestClient(create_app(make_settings(tmp_path / "data", max_llm_calls_per_run=80), llm=FixtureLLM(agent_responder=responder))) as client:
        run_id, _ = research(client)
        data = client.get(f"/api/runs/{run_id}/research").json()
    caps = {c["id"]: c for c in data["capabilities"]}
    assert data["components"]
    assert all(c["approach"] == caps[c["capability_id"]]["approaches"][1] for c in data["components"])


async def test_a_capability_named_after_an_app_layer_is_pushed_back_once(tmp_path):
    from app.tools.report_tools import RECORD_CAPABILITIES
    ctx, _ = tool_context(tmp_path)
    args = RECORD_CAPABILITIES.args.model_validate({"capabilities": [
        {"name": "cross_platform_mobile_frontend", "need": "screens", "approaches": ["library"], "priority": "core", "requirement_ids": ["REQ-1"]}]})
    first = await RECORD_CAPABILITIES.run(args, ctx)
    assert not first.ok and "named after a layer" in first.content and "cross_platform_mobile_frontend" in first.content
    assert (await RECORD_CAPABILITIES.run(args, ctx)).ok  # once only: a stubborn model still finishes
    renamed = RECORD_CAPABILITIES.args.model_validate({"capabilities": [
        {"name": "Camera capture and image picking", "need": "photos", "approaches": ["library"], "priority": "core", "requirement_ids": ["REQ-1"]}]})
    ctx2, _ = tool_context(tmp_path / "b")
    assert (await RECORD_CAPABILITIES.run(renamed, ctx2)).ok


async def test_a_capability_named_after_a_quality_is_pushed_back_once(tmp_path):
    from app.tools.report_tools import RECORD_CAPABILITIES
    ctx, _ = tool_context(tmp_path)
    args = RECORD_CAPABILITIES.args.model_validate({"capabilities": [
        {"name": "Cost-aware ML and API orchestration", "need": "keep costs low", "approaches": ["library"], "priority": "core", "requirement_ids": ["REQ-1"]}]})
    first = await RECORD_CAPABILITIES.run(args, ctx)
    assert not first.ok and "quality, not a function" in first.content


async def test_core_capabilities_are_scouted_before_supporting_ones_and_supporting_ones_once(tmp_path):
    from app.tools.team_tools import AskScoutsArgs, ask_component_scouts
    core = Capability(id="CAP-1", name="Speech to text", need="n", approaches=["engine"], priority="core")
    extra = Capability(id="CAP-2", name="User accounts", need="n", approaches=["library"], priority="supporting")
    ctx, _ = tool_context(tmp_path, capabilities=[core, extra])
    refused = await ask_component_scouts(AskScoutsArgs(capability_ids=["CAP-2"], instructions="go"), ctx)
    assert not refused.ok and "core capabilities first" in refused.content
    assert (await ask_component_scouts(AskScoutsArgs(capability_ids=["CAP-1"], instructions="go"), ctx)).ok
    ctx.board.scout_rounds = {"CAP-1": 1, "CAP-2": 1}
    again = await ask_component_scouts(AskScoutsArgs(capability_ids=["CAP-2"], instructions="again"), ctx)
    assert not again.ok and "supporting ones one" in again.content


async def test_capabilities_are_stored_core_first_and_a_core_is_required(tmp_path):
    from app.tools.report_tools import RECORD_CAPABILITIES
    ctx, _ = tool_context(tmp_path)
    none_core = RECORD_CAPABILITIES.args.model_validate({"capabilities": [
        {"name": "User accounts", "need": "n", "approaches": ["a"], "priority": "supporting", "requirement_ids": ["REQ-1"]}]})
    assert "core" in (await RECORD_CAPABILITIES.run(none_core, ctx)).content
    mixed = RECORD_CAPABILITIES.args.model_validate({"capabilities": [
        {"name": "User accounts", "need": "n", "approaches": ["a"], "priority": "supporting"},
        {"name": "Speech to text", "need": "n", "approaches": ["a"], "priority": "core", "requirement_ids": ["REQ-1"]}]})
    assert (await RECORD_CAPABILITIES.run(mixed, ctx)).ok
    assert [c["priority"] for c in ctx.outcome["capabilities"]] == ["core", "supporting"]


async def test_the_review_cannot_be_complete_while_a_core_stage_has_no_building_block(tmp_path):
    from app.tools.report_tools import SUBMIT_REVIEW
    core = Capability(id="CAP-1", name="Analyse sources", need="n", approaches=["a"], priority="core")
    ctx, _ = tool_context(tmp_path, capabilities=[core])
    result = await SUBMIT_REVIEW.run(SUBMIT_REVIEW.args.model_validate({"complete": True, "gaps": []}), ctx)
    review = ctx.outcome["review"]
    assert result.ok and review["complete"] is False and review["gaps"][0]["capability_id"] == "CAP-1"


def test_a_tool_call_is_described_by_its_subject_and_count_in_plain_words():
    from pydantic import BaseModel

    from app.agents.action_subject import action_subject

    class Search(BaseModel):
        query: str
        language: str | None = None

    class Inspect(BaseModel):
        repo: str

    class Page(BaseModel):
        url: str

    class Report(BaseModel):
        components: list[dict]
        summary: str

    class Ask(BaseModel):
        capability_ids: list[str]
        instructions: str

    assert action_subject(Search(query="  fast   keyword  search ")) == {"about": "fast keyword search", "count": None}
    assert action_subject(Inspect(repo="owner/name"))["about"] == "owner/name"
    assert action_subject(Page(url="https://www.example.org/docs"))["about"] == "example.org/docs"
    assert action_subject(Report(components=[{}, {}, {}], summary="x")) == {"about": None, "count": 3}
    assert action_subject(Ask(capability_ids=["CAP-1", "CAP-2"], instructions="go"))["count"] == 2
    assert len(action_subject(Search(query="word " * 50))["about"]) <= 80


# --- Which sources a run really used (shown in the studio) -----------------------------
def source_events(events):
    return [(e["source"], e["results"]) for e in events if e.get("event") == "source_used"]


async def test_each_tool_announces_the_source_it_looked_in(tmp_path):
    from app.tools.discussion_tools import SEARCH_DISCUSSIONS
    ctx, events = tool_context(tmp_path)
    await SEARCH_GITHUB.run(SEARCH_GITHUB.args.model_validate({"query": "markdown notes"}), ctx)
    await SEARCH_DISCUSSIONS.run(SEARCH_DISCUSSIONS.args.model_validate({"query": "voice agent framework"}), ctx)
    used = dict(source_events(events))
    # Fixture mode gives a fixed pair of threads; each source is named with how many it gave.
    assert "github" in used and used["github"] >= 1
    assert set(used) >= {"github", "hacker_news", "stack_overflow"}


async def test_a_source_that_failed_to_answer_is_not_announced(tmp_path):
    from app.integrations.discussion_client import DiscussionClient
    from app.tools.discussion_tools import SEARCH_DISCUSSIONS

    def only_hacker_news(request: httpx.Request) -> httpx.Response:
        if "algolia" in str(request.url):
            return httpx.Response(200, json={"hits": [{"title": "Show HN: a tool", "objectID": "1", "points": 9, "num_comments": 2,
                                                       "created_at_i": 1700000000, "url": "https://example.org/x"}]})
        return httpx.Response(500)

    ctx, events = tool_context(tmp_path)
    ctx.integrations = type("I", (), {"discussion": DiscussionClient(mode="live", transport=httpx.MockTransport(only_hacker_news))})()
    await SEARCH_DISCUSSIONS.run(SEARCH_DISCUSSIONS.args.model_validate({"query": "anything"}), ctx)
    names = [source for source, _ in source_events(events)]
    assert names == ["hacker_news"]  # Stack Overflow failed, so it was not "used"


async def test_source_usage_is_totalled_per_run_in_a_fixed_order(tmp_path):
    from app.db import run_events_repo
    from app.db.connection import open_connection

    settings = make_settings(tmp_path / "data")
    with TestClient(create_app(settings)) as client:
        run_id = new_run(client, IDEA)
    async with open_connection(settings.database_path) as db:
        for source, results in [("npm", 3), ("github", 5), ("github", 2), ("brave", 0), ("elsewhere", 1)]:
            await run_events_repo.add_event(db, run_id, "source_used", {"source": source, "results": results})
        await run_events_repo.add_event(db, run_id, "activity", {"message": "not a source event"})
        totals = await run_events_repo.source_usage(db, run_id)
    assert totals == [("github", 2, 7), ("npm", 1, 3), ("brave", 1, 0), ("elsewhere", 1, 1)]


def test_a_finished_research_says_where_it_looked(tmp_path):
    with TestClient(create_app(make_settings(tmp_path / "data", max_llm_calls_per_run=40))) as client:
        run_id, _ = research(client)
        data = client.get(f"/api/runs/{run_id}/research").json()
        assert data["sources"], "the research snapshot should list the sources the run used"
        assert data["sources"][0]["source"] == "github"
        assert all(item["lookups"] >= 1 for item in data["sources"])
