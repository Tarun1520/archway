"""
PromptPack: the staged set of prompts for building the project with a
coding agent.

What this file does
    Defines the pack, its prompts, and the result of the automatic quality
    check (the rubric) on each prompt.

Rules built in
    - Every prompt names at least one roadmap task.
    - A prompt may only name tasks that exist in the same pack.
    - The pack records the architecture VERSION it was generated from and
      always carries a notice that generated code needs human review.

How it plugs in
    Phase 6's `generate_prompts` creates it and `check_prompts` fills in
    `rubric_results`.
"""

from datetime import datetime

from pydantic import Field, model_validator

from app.models.common import ArchwayModel
from app.models.roadmap import RoadmapTask


class Prompt(ArchwayModel):
    id: str = Field(min_length=1)  # e.g. "01_scaffold"
    title: str = Field(min_length=1)
    task_ids: list[str] = Field(min_length=1)  # at least one roadmap task
    prerequisite_prompt_ids: list[str] = Field(default_factory=list)
    body: str = Field(min_length=1)


class RubricResult(ArchwayModel):
    prompt_id: str = Field(min_length=1)
    criterion: str = Field(min_length=1)  # e.g. "references architecture version"
    passed: bool
    note: str | None = None


class PromptPack(ArchwayModel):
    id: str = Field(min_length=1)
    architecture_version: int = Field(ge=1)

    tasks: list[RoadmapTask] = Field(default_factory=list)
    prompts: list[Prompt] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)
    rubric_results: list[RubricResult] = Field(default_factory=list)

    generated_at: datetime
    review_notice: str = Field(min_length=1)

    @model_validator(mode="after")
    def prompts_point_at_real_tasks(self):
        known_tasks = {task.id for task in self.tasks}
        for prompt in self.prompts:
            unknown = [task_id for task_id in prompt.task_ids if task_id not in known_tasks]
            if unknown:
                raise ValueError(f"prompt '{prompt.id}' refers to unknown task ids: {unknown}")
        return self
