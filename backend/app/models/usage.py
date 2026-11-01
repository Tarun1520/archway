"""
UsageEvent: one count of calls made to an outside service.

What this file does
    Records how many calls a run made, to which service, and whether they
    were live or fixtures. Adding these up gives the usage counters in the
    UI and is how the per-run caps are enforced.

How it plugs in
    From Phase 2 on, every model, Jev and GitHub call writes one of these.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.common import ArchwayModel, ServiceMode

Service = Literal["llm", "jev", "github"]


class UsageEvent(ArchwayModel):
    run_id: str = Field(min_length=1)
    service: Service
    mode: ServiceMode
    count: int = Field(ge=1)
    # Token counts are only stored when the service reported them.
    tokens_if_known: int | None = Field(default=None, ge=0)
    timestamp: datetime
