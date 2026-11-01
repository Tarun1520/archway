"""
Shared test helpers.

LEARNING NOTE: what is conftest.py?
    pytest loads this file automatically. Functions marked @pytest.fixture
    become ingredients any test can ask for by naming them as an argument:

        def test_something(client): ...

    pytest sees `client`, runs the fixture below, and passes in the result.

The important idea here: tests never touch your real data or real keys.
Every test gets its own temporary folder and its own made-up settings.
"""

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app


def make_settings(data_dir, **overrides) -> Settings:
    """Settings for tests: fixture mode, small caps, a temporary data folder.

    `_env_file=None` tells pydantic-settings NOT to read backend/.env, so a
    test can never pick up a real API key.
    """
    values = {
        "jev_mode": "fixture",
        "llm_mode": "fixture",
        "github_mode": "fixture",
        "max_llm_calls_per_run": 5,
        "max_jev_calls_per_run": 5,
        "data_dir": data_dir,
        "log_level": "WARNING",
        "background_research": False,  # each request finishes its work, so tests can check it
        "auth_enabled": False,  # most tests are about the workflow; test_auth.py switches accounts on
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture(autouse=True)
def no_real_environment(monkeypatch):
    """Remove real settings from the environment for the length of each test.

    autouse=True means every test gets this without asking.
    """
    for name in (
        "JEV_MODE", "LLM_MODE", "GITHUB_MODE", "MAX_LLM_CALLS_PER_RUN", "MAX_JEV_CALLS_PER_RUN", "AUTH_ENABLED", "ADMIN_EMAIL",
        "LLM_PROVIDER", "LLM_MODEL", "GROQ_API_KEY", "JEV_API_KEY", "GITHUB_TOKEN", "DEEPGRAM_API_KEY",
        "ARCHWAY_DATA_DIR", "LOG_LEVEL",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def settings(tmp_path) -> Settings:
    # tmp_path is a built-in pytest fixture: a fresh empty folder per test.
    return make_settings(tmp_path / "data")


@pytest.fixture
def client(settings):
    """A test client for the API, backed by a temporary database.

    LEARNING NOTE: `with TestClient(app)` runs the app's start-up code (which
    creates the tables) on the way in and its shutdown code on the way out.
    """
    with TestClient(create_app(settings)) as test_client:
        yield test_client
