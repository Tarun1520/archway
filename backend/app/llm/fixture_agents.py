"""
Scripted agents for fixture mode: the research team, without a real model.

IMPORTANT: this is not intelligence
    Each "agent" below follows a fixed script, reading the same briefings and
    tool results a real model would, and calling the same tools. It exists so
    the whole team can run in tests, in CI and offline, and so failures are
    repeatable. It still goes through the real tools, so every guardrail
    (budgets, "only propose what you looked at") is exercised for real.

How it plugs in
    FixtureLLM.chat (app/llm/fixture.py) calls `scripted_reply`.
"""

import json
import re
from typing import Any

FIXTURE = "FIXTURE"
_STOP = {"the", "a", "an", "and", "or", "of", "to", "for", "with", "in", "on", "must", "should", "can", "be", "is",
         "app", "users", "user", "it", "that", "this", "their", "from", "by", "as", "are", "will", "able", "allow"}


def _tagged(text: str, tag: str) -> Any:
    match = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


def _keywords(text: str, limit: int = 3) -> list[str]:
    words = []
    for word in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text):
        if word.lower() not in _STOP and word.lower() not in [w.lower() for w in words]:
            words.append(word.lower())
        if len(words) == limit:
            break
    return words


def _tool_results(messages: list[dict]) -> list[tuple[str, dict]]:
    results = []
    for message in messages:
        if message.get("role") == "tool":
            try:
                results.append((message.get("name", ""), json.loads(message["content"])))
            except (ValueError, KeyError):
                results.append((message.get("name", ""), {}))
    return results


def _call(name: str, **arguments) -> dict:
    return {"name": name, "arguments": arguments}


def _lead(briefing: str, results) -> dict:
    if results and "error" in results[-1][1]:
        return _call("finish_research", summary=f"{FIXTURE}: the scripted lead stops after a refused step.")
    board = _tagged(briefing, "board") or {}
    capabilities = board.get("capabilities", [])
    if not capabilities:
        return _call("ask_capability_analyst", instructions="List the capabilities to research.")
    unscouted = [c for c in capabilities if c.get("times_scouted", 0) == 0]
    core = [c["id"] for c in unscouted if c.get("priority", "core") == "core"]
    if core:  # core first
        return _call("ask_component_scouts", capability_ids=core[:5],
                     instructions="Cover every approach.", include_project_scout=board.get("similar_projects_found", 0) == 0)
    review = board.get("latest_review")
    if not review or not review.get("is_current"):
        return _call("ask_reviewer", instructions="Check coverage.")
    supporting = [c["id"] for c in unscouted]
    if supporting:
        return _call("ask_component_scouts", capability_ids=supporting[:5], instructions="The standard options are enough.")
    return _call("finish_research", summary=f"{FIXTURE}: scripted research finished.")


def _analyst(briefing: str, results) -> dict:
    brief = _tagged(briefing, "brief") or {}
    must = brief.get("must_have") or [{"id": "", "text": brief.get("problem", "the product")}]
    capabilities = []
    for item in must[:3]:
        words = _keywords(item.get("text", ""))
        capabilities.append({
            "name": " ".join(words[:3]).title() or "Core capability",
            "need": item.get("text", "")[:200] or "the core of the product",
            "requirement_ids": [item["id"]] if item.get("id") else [],
            "approaches": ["an embeddable library", "a self-hosted service"],
            "search_hints": words,
            "priority": "core" if len(capabilities) < 2 else "supporting",  # the scripted core: the first two
        })
    # Names must differ; a repeated name gets a number.
    seen: dict[str, int] = {}
    for capability in capabilities:
        count = seen.get(capability["name"], 0)
        seen[capability["name"]] = count + 1
        if count:
            capability["name"] = f"{capability['name']} {count + 1}"
    plain = [item["id"] for item in must[3:] if item.get("id")]  # the scripted analyst maps only the first three
    return _call("record_capabilities", capabilities=capabilities, plain_product_logic=plain)


def _scout(briefing: str, results) -> dict:
    capability = _tagged(briefing, "capability") or {}
    searches = [r for name, r in results if name == "search_github"]
    inspections = [r for name, r in results if name == "inspect_repository" and "error" not in r]
    if not searches:
        hints = capability.get("search_hints") or _keywords(capability.get("name", "notes"))
        return _call("search_github", query=" ".join(hints[:3]) or "notes")
    hits = searches[-1].get("results", [])
    inspected = {r.get("reference") for r in inspections}
    for hit in hits[:2]:
        if hit["reference"] not in inspected and len(inspections) < 2:
            return _call("inspect_repository", repo=hit["reference"])
    approaches = capability.get("approaches") or [None]
    components = [{
        "source": "github", "reference": r["reference"], "name": r["reference"].split("/")[-1],
        "approach": approaches[i % len(approaches)], "provides": f"{FIXTURE}: scripted description",
        "fit_notes": f"{FIXTURE}: chosen by a scripted scout, not judged", "concerns": [],
    } for i, r in enumerate(inspections)]
    return _call("submit_components", components=components,
                 summary=f"{FIXTURE}: scripted scout inspected {len(inspections)} repositories.")


def _project_scout(briefing: str, results) -> dict:
    brief = _tagged(briefing, "brief") or {}
    searches = [r for name, r in results if name == "search_github"]
    if not searches:
        return _call("search_github", query=" ".join(_keywords(brief.get("problem", "notes app"))) or "notes")
    hits = searches[-1].get("results", [])[:1]
    return _call("submit_projects", projects=[
        {"reference": h["reference"], "why_similar": f"{FIXTURE}: scripted", "worth_learning": f"{FIXTURE}: scripted"}
        for h in hits
    ], summary=f"{FIXTURE}: scripted project scout.")


def _reviewer(briefing: str, results) -> dict:
    return _call("submit_review", complete=True, gaps=[], notes=f"{FIXTURE}: scripted review, not a real judgement.")


def _judge(briefing: str, results) -> dict:
    candidates = _tagged(briefing, "candidates") or []
    return _call("submit_fit", assessments=[
        {"id": c["id"], "fit": 3, "kind": "building_block", "reason": f"{FIXTURE}: scripted, not judged"} for c in candidates
    ])


SCRIPTS = {
    "agent:research_lead": _lead,
    "agent:capability_analyst": _analyst,
    "agent:component_scout": _scout,
    "agent:project_scout": _project_scout,
    "agent:reviewer": _reviewer,
    "agent:relevance_judge": _judge,
}


def scripted_reply(step: str, messages: list[dict]) -> dict:
    """The tool call a scripted agent makes next: {"name": ..., "arguments": {...}}."""
    script = SCRIPTS.get(step)
    if script is None:
        raise KeyError(f"no scripted agent for step '{step}'")
    briefing = next((m["content"] for m in messages if m.get("role") == "user"), "")
    return script(briefing, _tool_results(messages))
