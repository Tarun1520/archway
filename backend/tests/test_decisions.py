"""Phase 4: typed decisions, receipts, and the gate inside a full run."""

import json

import httpx
from fastapi.testclient import TestClient

from app.decisions.client import DecisionResponse, DecisionUnavailable, GatewayDecisionClient
from app.decisions.questions import questions_for
from app.decisions.receipts import receipts_from
from app.main import create_app
from tests.conftest import make_settings
from tests.test_agents import research

COMPONENT = {"id": "cmp-1", "name": "piper", "fit": 3, "facts": {"kind": "github", "reference": "rhasspy/piper",
             "license": "MIT", "license_status": "detected", "evidence_ids": ["ev-1"]}}
REQS = [{"id": "REQ-1", "text": "Speak replies in a natural voice"}]


async def test_the_gateway_gets_typed_questions_and_answers_map_back():
    seen = {}

    def answer(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"model": "typesafe-ai/jev", "usage": {"inputTokens": 300, "outputTokens": 20}, "answers": {
            "fit__REQ-1": {"type": "boolean", "probability": 0.9},
            "risk": {"type": "choice", "choice": "low", "probabilities": {"low": 0.85, "medium": 0.1, "high": 0.05}},
            "review": {"type": "boolean", "probability": 0.5}}})

    client = GatewayDecisionClient(api_key="k", model="typesafe-ai/jev", transport=httpx.MockTransport(answer))
    questions = questions_for(COMPONENT, REQS)
    response = await client.decide(state={"component": {"name": "piper"}}, questions=questions)
    assert seen["url"] == "https://ai-gateway.vercel.sh/v1/evaluate" and seen["auth"] == "Bearer k"
    assert seen["body"]["model"] == "typesafe-ai/jev"
    assert {q["type"] for q in seen["body"]["questions"].values()} == {"choice", "boolean"}

    receipts = {r.question_type: r for r in receipts_from("cmp-1", response, list(questions), mode="live", evidence_ids=["ev-1"])}
    fit = receipts["requirement_fit"]
    assert fit.final_result == "meets" and fit.reported_confidence == 0.9 and not fit.needs_review
    assert fit.requirement_id == "REQ-1" and fit.jev_mode == "live" and fit.jev_model_id == "typesafe-ai/jev"
    assert receipts["integration_risk"].final_result == "low"
    assert receipts["needs_human_review"].needs_review is True  # 0.5 is inside the unsure band


async def test_an_unavailable_service_is_reported_with_its_reason_and_no_key():
    def answer(request):
        return httpx.Response(403, json={"error": {"message": "AI Gateway requires a valid credit card on file"}})

    client = GatewayDecisionClient(api_key="secret-key-value", model="m", transport=httpx.MockTransport(answer))
    try:
        await client.decide(state={}, questions={})
    except DecisionUnavailable as error:
        assert "credit card" in str(error) and "secret-key-value" not in str(error)
    else:
        raise AssertionError("expected DecisionUnavailable")


def test_unanswered_questions_become_not_evaluated_receipts_never_guesses():
    names = list(questions_for(COMPONENT, REQS))
    receipts = receipts_from("cmp-1", None, names, mode="live", evidence_ids=[], not_evaluated_reason="card missing")
    assert len(receipts) == 3
    assert all(r.final_result is None and r.needs_review and "not evaluated: card missing" in r.aggregation_policy for r in receipts)


def test_a_full_run_ends_with_eligibility_and_fixture_receipts(tmp_path):
    with TestClient(create_app(make_settings(tmp_path / "data", max_llm_calls_per_run=60))) as client:
        run_id, state = research(client)
        data = client.get(f"/api/runs/{run_id}/research").json()
    assert state["finished"] and data["finished"]
    ids = {c["id"] for c in data["components"]}
    assert {e["component_id"] for e in data["eligibility"]} == ids
    assert data["receipts"] and all(r["jev_mode"] == "fixture" for r in data["receipts"])
    assert {r["question_type"] for r in data["receipts"]} == {"requirement_fit", "integration_risk", "needs_human_review"}


def test_when_decisions_are_unavailable_the_run_still_finishes_with_a_visible_note(tmp_path):
    class Down:
        mode = "live"

        async def decide(self, *, state, questions):
            raise DecisionUnavailable("the decision service answered HTTP 403: card required")

    from app.config.settings import Settings  # noqa: F401  (settings come from make_settings)
    app = create_app(make_settings(tmp_path / "data", max_llm_calls_per_run=60))
    with TestClient(app) as client:
        app.state.workflow._decisions = Down()
        run_id, state = research(client)
        data = client.get(f"/api/runs/{run_id}/research").json()
    assert state["finished"]
    assert any("Decisions not evaluated" in n and "card required" in n for n in data["notes"])
    assert data["receipts"] and all(r["final_result"] is None for r in data["receipts"])
    assert all(e["status"] in ("eligible", "review_required", "unresolved", "excluded") for e in data["eligibility"])


async def test_laya_speaks_the_system_one_protocol_and_yes_no_maps_back():
    from app.decisions.client import SystemOneDecisionClient
    seen = {}

    def answer(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"model": "typed-decisions", "usage": {"input_tokens": 90, "output_tokens": 3}, "answers": {
            "fit__REQ-1": {"type": "noul", "noul": 0.58},
            "risk": {"type": "choice", "choice": "low", "probabilities": {"low": 0.7, "medium": 0.2, "high": 0.1}, "confidence": 0.4},
            "review": {"type": "noul", "noul": 0.41}}})

    client = SystemOneDecisionClient(base_url="http://127.0.0.1:8100", model="typed-decisions", transport=httpx.MockTransport(answer))
    questions = questions_for(COMPONENT, REQS)
    response = await client.decide(state={"component": {"name": "piper", "description": "fast local TTS"}}, questions=questions)
    assert seen["url"] == "http://127.0.0.1:8100/v1/systemone"
    assert seen["body"]["questions"]["fit__REQ-1"]["type"] == "noul" and isinstance(seen["body"]["state"], str)
    assert "description: fast local TTS" in seen["body"]["state"]
    assert response.model == "laya/typed-decisions" and response.answers["fit__REQ-1"] == {"type": "boolean", "probability": 0.58}

    receipts = {r.question_type: r for r in receipts_from("cmp-1", response, list(questions), mode="live", evidence_ids=[])}
    assert receipts["requirement_fit"].final_result == "meets" and not receipts["requirement_fit"].needs_review  # 0.58 is above Laya's band
    assert receipts["needs_human_review"].needs_review is True  # 0.41 is inside Laya's unsure band (0.30 to 0.50)
    assert receipts["requirement_fit"].jev_model_id == "laya/typed-decisions"  # named for what answered, never "Jev"


async def test_a_laya_service_that_is_not_running_is_reported_with_how_to_start_it():
    from app.decisions.client import SystemOneDecisionClient

    def down(request):
        raise httpx.ConnectError("refused", request=request)

    client = SystemOneDecisionClient(base_url="http://127.0.0.1:8100", transport=httpx.MockTransport(down))
    try:
        await client.decide(state="s", questions={})
    except DecisionUnavailable as error:
        assert "is it running" in str(error) and "services/laya" in str(error)
    else:
        raise AssertionError("expected DecisionUnavailable")


def test_live_decisions_default_to_local_laya(tmp_path):
    from app.decisions.client import SystemOneDecisionClient
    from app.decisions.factory import build_decision_client
    assert isinstance(build_decision_client(make_settings(tmp_path, jev_mode="live")), SystemOneDecisionClient)


def test_the_laya_band_applies_whatever_the_server_calls_itself():
    names = list(questions_for(COMPONENT, REQS))
    response = DecisionResponse(model="laya-rl-agent", answers={"fit__REQ-1": {"type": "boolean", "probability": 0.55},
                                                               "review": {"type": "boolean", "probability": 0.45}})
    receipts = {r.question_type: r for r in receipts_from("c", response, names, mode="live", evidence_ids=[])}
    assert receipts["requirement_fit"].final_result == "meets" and not receipts["requirement_fit"].needs_review
    assert receipts["needs_human_review"].needs_review
