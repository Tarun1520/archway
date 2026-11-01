"""
The LIVE / FIXTURE report shown in the UI and written into exports.

What this file does
    Turns the three mode settings into one honest summary.

The rule (IMPLEMENTATION_GUIDE.md section 6.5)
    The badge reads LIVE only when ALL three services are live. If any one
    is a fixture, the badge reads FIXTURE and names which ones.

How it plugs in
    app/api/config_routes.py returns this report; the frontend shows it.
"""

from typing import Literal

from pydantic import BaseModel

from app.config.settings import ServiceMode, Settings


class ModeReport(BaseModel):
    """What the frontend needs to draw the mode badge. Contains NO secrets."""

    jev: ServiceMode
    llm: ServiceMode
    github: ServiceMode
    badge: Literal["LIVE", "FIXTURE"]
    fixture_services: list[str]
    label: str  # the full sentence to show, for example "FIXTURE MODE: jev, llm"


def describe_modes(settings: Settings) -> ModeReport:
    modes = {"jev": settings.jev_mode, "llm": settings.llm_mode, "github": settings.github_mode}
    fixture_services = [name for name, mode in modes.items() if mode == "fixture"]

    if fixture_services:
        badge = "FIXTURE"
        label = "FIXTURE MODE: " + ", ".join(fixture_services)
    else:
        badge = "LIVE"
        label = "LIVE"

    return ModeReport(**modes, badge=badge, fixture_services=fixture_services, label=label)
