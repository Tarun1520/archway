"""
Lesson 20: Settings from the environment, and swappable adapters
================================================================

What you learn here
    1. SETTINGS: read configuration (modes, limits, secrets) from environment
       variables with `pydantic-settings`. Values are validated; a missing
       required value stops the program at start-up, not mid-run.
    2. ADAPTERS: write code against a small INTERFACE (a `Protocol`), then
       provide a fixture version and a live version. A factory picks one
       from the settings. Nothing else in the program changes.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/20_settings_and_adapters.py

Where Archway uses this
    - backend/app/config (Phase 1): `jev_mode`, `llm_mode`, `github_mode` and
      the required per-run call caps.
    - backend/app/jev, backend/app/llm (Phases 2 and 4): "Provider adapter
      behind an SDK-independent interface" and "thin adapter" in the guide.
    - The LIVE/FIXTURE badge: live only when ALL services are live.
"""

import os
from typing import Literal, Protocol

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


# -----------------------------------------------------------------------------
# 1. Settings
# -----------------------------------------------------------------------------
class Settings(BaseSettings):
    """Reads ARCHWAY_JEV_MODE, ARCHWAY_MAX_JEV_CALLS, ... from the environment."""

    # LEARNING NOTE: env_prefix
    #   The prefix keeps our variables from colliding with other programs'.
    model_config = SettingsConfigDict(env_prefix="ARCHWAY_")

    # A default of "fixture" is the SAFE default: nothing paid happens unless
    # someone deliberately switches a service to live.
    jev_mode: Literal["live", "fixture"] = "fixture"
    llm_mode: Literal["live", "fixture"] = "fixture"
    github_mode: Literal["live", "fixture"] = "fixture"

    # No default: the run limits are REQUIRED (guide section 5.3).
    max_llm_calls: int
    max_jev_calls: int


def mode_badge(settings: Settings) -> str:
    """LIVE only when every service is live; otherwise name the fixtures."""
    modes = {"jev": settings.jev_mode, "llm": settings.llm_mode, "github": settings.github_mode}
    fixtures = [name for name, mode in modes.items() if mode == "fixture"]
    return "LIVE" if not fixtures else "FIXTURE MODE: " + ", ".join(fixtures)


# -----------------------------------------------------------------------------
# 2. An interface and two implementations
# -----------------------------------------------------------------------------
class RequirementJudge(Protocol):
    """Anything with this method counts as a RequirementJudge."""

    def requirement_fit(self, repo: str, requirement: str) -> str: ...


class FixtureJudge:
    """Answers from fixed data. Safe for tests, CI and offline demos."""

    mode = "fixture"

    def requirement_fit(self, repo: str, requirement: str) -> str:
        return "cannot_tell" if "unknown" in repo else "satisfies"


class LiveJudge:
    """Placeholder. The real Jev adapter is written in Phase 4, after the spike."""

    mode = "live"

    def requirement_fit(self, repo: str, requirement: str) -> str:
        raise RuntimeError("The live Jev adapter is not built yet (Phase 4).")


def build_judge(settings: Settings) -> RequirementJudge:
    """The ONLY place that decides which implementation is used."""
    return LiveJudge() if settings.jev_mode == "live" else FixtureJudge()


def run_with_judge(judge: RequirementJudge) -> str:
    """Business code. It cannot tell which implementation it was given."""
    return judge.requirement_fit("example/notes-md", "works offline")


if __name__ == "__main__":
    print("1. Missing required settings fail immediately")
    for name in list(os.environ):
        if name.startswith("ARCHWAY_"):
            del os.environ[name]
    try:
        Settings()
    except ValidationError as error:
        missing = [item["loc"][0] for item in error.errors()]
        print("   refused to start; missing:", missing)

    print("\n2. With values set (as if from the environment)")
    os.environ["ARCHWAY_MAX_LLM_CALLS"] = "30"
    os.environ["ARCHWAY_MAX_JEV_CALLS"] = "10"
    settings = Settings()
    print("   max_llm_calls:", settings.max_llm_calls, "| jev_mode:", settings.jev_mode)
    print("   badge        :", mode_badge(settings))

    print("\n3. Same business code, different adapter")
    print("   fixture judge ->", run_with_judge(build_judge(settings)))

    os.environ["ARCHWAY_JEV_MODE"] = "live"
    live_settings = Settings()
    print("   badge now    :", mode_badge(live_settings))
    try:
        run_with_judge(build_judge(live_settings))
    except RuntimeError as error:
        print("   live judge   ->", error)

    print("\n4. A typo in a mode is rejected, not silently accepted")
    os.environ["ARCHWAY_JEV_MODE"] = "lvie"
    try:
        Settings()
    except ValidationError as error:
        print("  ", error.errors()[0]["msg"])
