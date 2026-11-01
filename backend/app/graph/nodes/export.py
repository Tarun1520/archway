"""
Node: export. Phase 6, the last step: the source-to-decision links and the whole plan as JSON.

Plain code, no model. The links trace every requirement to its tasks, the components they touch, the eligibility
verdict and receipts behind each reused one, and its evidence (app/promptgen/links.py). The JSON holds the whole
plan (app/promptgen/export.py); the Markdown file and the zip are made from it when they are downloaded.
"""

from langgraph.runtime import Runtime

from app.graph import events
from app.graph.context import RunContext
from app.graph.state import WorkflowState
from app.models.option_flow import VersionRef
from app.models.plan import PlanSnapshot, PromptFile, Roadmap
from app.promptgen.export import plan_json, service_modes
from app.promptgen.links import build_links

NODE = "export"


async def export(state: WorkflowState, runtime: Runtime[RunContext]) -> dict:
    emit = runtime.stream_writer
    emit(events.node_started(NODE))
    roadmap = Roadmap.model_validate(state["roadmap"])
    links = build_links(roadmap, dict(state))
    plan = PlanSnapshot(
        requested=True, built_for=VersionRef.model_validate(roadmap.architecture.model_dump()), roadmap=roadmap,
        files=[PromptFile.model_validate(f) for f in state.get("plan_files", [])], links=links,
        passed=state.get("plan_passed"), outcome=state.get("plan_outcome"),
        notes=list(state.get("plan_notes", [])),
    )
    # Which services answered live and which from recorded fixtures: the export must say so (IMPLEMENTATION_GUIDE 1.2).
    services = service_modes(runtime.context)
    emit(events.activity(f"Plan: exported ({(state.get('plan_outcome') or 'unknown').upper()}), with {len(links)} requirement links"))
    return {"plan_links": [link.model_dump(mode="json") for link in links], "plan_export": plan_json(dict(state), plan, services)}
