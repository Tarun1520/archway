"""
GitHub limits: how much of GitHub's allowance is left, for the studio's limit bar.

What this file does
    GET /api/github/limits asks GitHub itself (GET /rate_limit, which is free)
    and returns the two allowances that matter to research:
      core    repository details, READMEs and licenses  (60 per hour without a
              token, 5,000 with one)
      search  repository searches                       (10 per minute without
              a token, 30 with one)
    Each comes with the seconds until it resets, so the screen can show a
    real countdown instead of a guess.

Why the backend asks, not the browser
    The token must never reach the browser (LEARNING_GUIDE.md topic 38), and
    the limits belong to the machine's IP address and token, which the backend
    uses for every research request.

How it plugs in
    Registered in app/main.py. The answer is cached for a few seconds, so a
    screen that polls does not turn into a stream of requests.
"""

import time

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/github", tags=["github"])

CACHE_SECONDS = 4.0


class LimitMeter(BaseModel):
    limit: int
    remaining: int
    seconds_until_reset: int


class GithubLimits(BaseModel):
    available: bool  # False in fixture mode, or when GitHub could not be asked
    authenticated: bool  # True when a token is in use (a much larger allowance)
    reason: str | None = None  # why it is unavailable
    core: LimitMeter | None = None
    search: LimitMeter | None = None


@router.get("/limits")
async def github_limits(request: Request) -> GithubLimits:
    cached = getattr(request.app.state, "github_limits_cache", None)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]

    github = request.app.state.integrations.github
    if github.mode != "live":
        answer = GithubLimits(available=False, authenticated=False,
                              reason="GitHub is in fixture mode, so no real limits apply.")
    else:
        meters = await github.rate_limits()
        if meters is None:
            answer = GithubLimits(available=False, authenticated=github.authenticated,
                                  reason="GitHub's limits could not be read just now.")
        else:
            answer = GithubLimits(
                available=True, authenticated=github.authenticated,
                core=LimitMeter(**meters["core"]) if "core" in meters else None,
                search=LimitMeter(**meters["search"]) if "search" in meters else None,
            )
    request.app.state.github_limits_cache = (time.monotonic(), answer)
    return answer
