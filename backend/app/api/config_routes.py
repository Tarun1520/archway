"""
Public configuration: the settings the frontend is ALLOWED to see.

What this file does
    GET /api/config returns the service modes, the LIVE/FIXTURE badge, the
    per-run call caps, and the name of the chosen model.

The security rule this file exists for
    "No secrets in ... frontend bundles." The response is built from an
    explicit model, `PublicConfig`, that lists every field by name. API keys
    are not in that list, so they cannot leak by accident even if new
    settings are added later. A test checks this (tests/test_no_secrets.py).
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.deps import SettingsDep
from app.config.modes import ModeReport, describe_modes
from app.voice.base import LANGUAGES

router = APIRouter(tags=["config"])


class CallCaps(BaseModel):
    max_llm_calls_per_run: int
    max_jev_calls_per_run: int
    # What a run may really use: larger when a GitHub token is set. Never the token itself.
    max_github_calls_per_run: int


class VoiceInfo(BaseModel):
    """Whether Archy can listen and talk, and which languages the user may speak."""

    available: bool
    languages: dict[str, str]


class PublicConfig(BaseModel):
    """Everything about the configuration that may leave the backend."""

    modes: ModeReport
    caps: CallCaps
    # Names only. These say WHICH model is configured, not how to reach it.
    llm_provider: str | None
    llm_model: str | None
    voice: VoiceInfo
    # Whether "Forgot password?" can email a reset link (an email sender is set up).
    password_reset: bool = False


@router.get("/config")
async def public_config(request: Request, settings: SettingsDep) -> PublicConfig:
    return PublicConfig(
        modes=describe_modes(settings),
        caps=CallCaps(
            max_llm_calls_per_run=settings.max_llm_calls_per_run,
            max_jev_calls_per_run=settings.max_jev_calls_per_run,
            max_github_calls_per_run=settings.github_calls_cap,
        ),
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        voice=VoiceInfo(available=request.app.state.voice is not None, languages=LANGUAGES),
        password_reset=settings.auth_enabled and request.app.state.mailer is not None,
    )
