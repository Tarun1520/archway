"""
The application entry point: builds the FastAPI app.

What this file does
    `create_app()` assembles everything: it loads the settings, prepares
    logging and the database, plugs in every group of endpoints, and says
    how errors become HTTP responses.

How to start the server (from the project root)
    backend/.venv/bin/python backend/run.py
    then open http://localhost:8000/docs for the interactive API page.

LEARNING NOTE: why a function instead of a global `app = FastAPI()`?
    A function can be called with DIFFERENT settings. Tests call
    `create_app(test_settings)` to get an app that uses a temporary
    database, without touching your real data or your real .env file.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app import __version__
from app.api import (
    admin, auth, config_routes, demo_events, github_limits, health, messages, options, plan, projects, readiness, research, run_events, runs, sample_briefs, suggestions,
    voice, workflow,
)
from app.config.modes import describe_modes
from app.config.settings import Settings, get_settings
from app.db.connection import open_connection
from app.db.errors import NotFound
from app.db.migrations import apply_migrations
from app.graph.build import build_workflow
from app.llm.base import LLMClient, LLMError
from app.llm.factory import build_llm
from app.llm.fast_first import FastFirstLLM
from app.llm.groq import GroqLLM
from app.logging_setup import configure_logging
from app.models.lifecycle import InvalidTransition
from app.integrations.factory import Integrations, build_integrations
from app.voice.base import VoiceClient
from app.voice.factory import build_voice
from app.mail.base import Mailer
from app.mail.factory import build_mailer
from app.auth.access import current_user, owns_path
from app.security.guard import SecurityGuard
from app.security.scrub import register_secrets, scrub
from app.workflow.service import WorkflowConflict, WorkflowService
from app.workflow.suggestions_service import SuggestionService

logger = logging.getLogger("archway.app")


def _secret_values(settings: Settings) -> list[str]:
    """The real secret strings, used ONLY to scrub them from log lines and from messages to the browser."""
    secrets = [settings.groq_api_key, settings.jev_api_key, settings.github_token, settings.azure_openai_api_key,
               settings.ai_gateway_api_key, settings.brave_api_key, settings.deepgram_api_key, settings.brevo_api_key]
    return [secret.get_secret_value() for secret in secrets if secret is not None]


def create_app(
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    integrations: Integrations | None = None,
    voice_client: VoiceClient | None = None,
    mailer: Mailer | None = None,
) -> FastAPI:
    """Build the app. Tests may pass their own settings, model client, research integrations, voice and mailer."""
    settings = settings or get_settings()

    # LEARNING NOTE: lifespan
    #   Code before `yield` runs ONCE when the server starts; code after it
    #   runs once when the server stops. Start-up is the right moment to
    #   prepare the database, so every request can assume the tables exist.
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(settings.log_level, secrets=_secret_values(settings))
        async with open_connection(settings.database_path) as connection:
            version = await apply_migrations(connection)

        # LEARNING NOTE: the checkpointer (LEARNING_GUIDE.md topic 10)
        #   AsyncSqliteSaver saves the workflow's state to a file after every
        #   step. `async with` keeps its database connection open for as long
        #   as the server runs and closes it cleanly on shutdown. Because the
        #   state is in a file, a run that is waiting for the user is still
        #   waiting, at the same step, after the server restarts.
        async with AsyncSqliteSaver.from_conn_string(str(settings.checkpoints_path)) as checkpointer:
            model = llm or build_llm(settings)
            # The voice endpoints (what did the person say?) use a quick model when one is set up.
            app.state.llm = model
            app.state.voice_llm = model
            if llm is None and settings.llm_mode == "live" and settings.voice_llm_model and settings.groq_api_key:
                app.state.voice_llm = FastFirstLLM(
                    GroqLLM(api_key=settings.groq_api_key.get_secret_value(), model=settings.voice_llm_model, max_concurrency=2),
                    model,
                )
            app.state.integrations = integrations or build_integrations(settings)
            app.state.workflow = WorkflowService(
                graph=build_workflow(checkpointer), settings=settings, llm=model,
                integrations=app.state.integrations,
            )
            app.state.suggestions = SuggestionService(settings=settings, llm=model)
            logger.info(
                "backend started",
                extra={"fields": {"version": __version__, "database_version": version,
                                  "modes": describe_modes(settings).label}},
            )
            yield
            # Background research must stop while its database is still open.
            await app.state.workflow.shutdown()
        logger.info("backend stopped")

    docs = settings.docs_enabled
    app = FastAPI(title="Archway API", version=__version__, lifespan=lifespan,
                  docs_url="/docs" if docs else None, redoc_url="/redoc" if docs else None,
                  openapi_url="/openapi.json" if docs else None)
    # The front door (app/security/guard.py): requests that change data, and WebSocket handshakes, must come from
    # Archway's own site; every answer carries the security headers.
    app.add_middleware(SecurityGuard, allowed_origins=settings.origin_list, local=not settings.cookie_secure,
                       https=settings.cookie_secure)
    # Known secret values are scrubbed from every message that leaves the backend (app/security/scrub.py).
    register_secrets(_secret_values(settings))

    # Keep the settings on the app so routes can reach them (app/api/deps.py).
    app.state.settings = settings
    # The voice provider (Archy), or None when no key is set: voice is then off.
    app.state.voice = voice_client if voice_client is not None else build_voice(settings)
    # The email sender (password reset links), or None when it is not set up.
    app.state.mailer = mailer if mailer is not None else build_mailer(settings)

    # --- Plug in the endpoints. Every URL starts with /api. ------------------
    # Open to everyone: the health check, the public settings, and signing in.
    for router in (health.router, config_routes.router, auth.router):
        app.include_router(router, prefix="/api")
    # Everything else needs a signed-in account (with auth switched off: the local admin). `owns_path` also checks
    # that a project or run named in the address belongs to the person asking (app/auth/access.py).
    signed_in = [Depends(current_user), Depends(owns_path)]
    for router in (
        github_limits.router,
        projects.router,
        messages.router,
        readiness.router,
        readiness.check_router,
        runs.project_runs_router,
        runs.runs_router,
        workflow.router,
        research.router,
        options.router,
        plan.router,
        suggestions.router,
        run_events.router,
        sample_briefs.router,
        demo_events.router,
        voice.router,
        admin.router,
    ):
        app.include_router(router, prefix="/api", dependencies=signed_in)

    # --- Turn our own errors into clear HTTP responses ------------------------
    # LEARNING NOTE: status codes
    #   404 = "that thing does not exist"
    #   409 = "the request is understood but conflicts with the current state"
    @app.exception_handler(NotFound)
    async def not_found(request: Request, error: NotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(InvalidTransition)
    async def invalid_transition(request: Request, error: InvalidTransition) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(LLMError)
    async def model_failed(request: Request, error: LLMError) -> JSONResponse:
        # 502 = "a service we depend on failed". The message is scrubbed: a service's own error text could echo a key.
        return JSONResponse(status_code=502, content={"detail": scrub(str(error))})

    @app.exception_handler(WorkflowConflict)
    async def workflow_conflict(request: Request, error: WorkflowConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": scrub(str(error))})

    return app
