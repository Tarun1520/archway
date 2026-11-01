"""
RoadmapTask: one unit of work in the build plan.

What this file does
    Defines a task with everything a coding agent needs to do it safely:
    what to build, what must already exist, what must not be broken, and
    how to know it is finished.

How it plugs in
    Phase 6's `build_roadmap` node will create these, and every generated
    prompt will point at one or more task ids.
"""

from pydantic import Field

from app.models.common import ArchwayModel


class RoadmapTask(ArchwayModel):
    id: str = Field(min_length=1)  # e.g. "T-03"
    goal: str = Field(min_length=1)
    prerequisites: list[str] = Field(default_factory=list)  # ids of tasks that must be done first
    scope: str = Field(min_length=1)  # what to implement, and nothing more

    likely_files: list[str] = Field(default_factory=list)
    interfaces_to_preserve: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    acceptance_criteria: list[str] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)
    known_risks: list[str] = Field(default_factory=list)
