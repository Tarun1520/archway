"""
Node: generate_prompts. Phase 6: writes the prompt pack from the roadmap, in plain code (no model call).

The model's judgement is already in the roadmap (what each task is, its scope and its checks). This node fills in
the fixed template of IMPLEMENTATION_GUIDE.md 8.4 for each group of tasks, plus the context files of the pack.
Why code and not a model: see app/promptgen/render.py.
"""

from langgraph.runtime import Runtime

from app.graph import events
from app.graph.context import RunContext
from app.graph.state import WorkflowState
from app.models.plan import Roadmap
from app.promptgen.export import fixture_names, service_modes
from app.promptgen.render import render_pack

NODE = "generate_prompts"


async def generate_prompts(state: WorkflowState, runtime: Runtime[RunContext]) -> dict:
    emit = runtime.stream_writer
    emit(events.node_started(NODE))
    roadmap = Roadmap.model_validate(state["roadmap"])
    files = render_pack(roadmap, dict(state), fixture_services=fixture_names(service_modes(runtime.context)))
    prompts = [f for f in files if f.kind == "prompt"]
    emit(events.activity(f"Plan: {len(prompts)} staged prompts written for {len(roadmap.tasks)} tasks"))
    return {"plan_files": [f.model_dump(mode="json") for f in files]}
