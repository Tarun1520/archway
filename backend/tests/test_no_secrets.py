"""
Tests that secrets stay inside the backend.

Checkpoint 1 item covered here: "No secret keys reach frontend JavaScript".

The first tests use made-up keys. The last ones read the REAL keys from
backend/.env (if that file exists) only to search for them in places they
must never appear. The values are never printed.
"""

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config.settings import BACKEND_DIR, Settings
from app.logging_setup import JsonFormatter
from app.main import create_app
from tests.conftest import make_settings

PROJECT_ROOT = BACKEND_DIR.parent
FAKE_KEYS = {
    "groq_api_key": "FAKE-GROQ-KEY-1234567890",
    "jev_api_key": "FAKE-JEV-KEY-1234567890",
    "github_token": "FAKE-GITHUB-TOKEN-1234567890",
    "deepgram_api_key": "FAKE-DEEPGRAM-KEY-1234567890",
}


def test_no_api_response_contains_a_secret(tmp_path):
    settings = make_settings(tmp_path, llm_provider="groq", llm_model="some-model", **FAKE_KEYS)
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/projects", json={"name": "P"}).json()
        client.post(f"/api/projects/{project['id']}/runs")
        pages = [
            client.get("/api/config").text,
            client.get("/api/health").text,
            client.get("/api/projects").text,
            client.get(f"/api/projects/{project['id']}/runs").text,
            client.get("/api/sample-briefs").text,
            client.get("/openapi.json").text,  # the machine-readable list of endpoints
        ]
    everything = "\n".join(pages)
    for secret in FAKE_KEYS.values():
        assert secret not in everything


def test_public_config_has_exactly_the_expected_fields(client):
    """If someone adds a field to /api/config, this test makes them look twice."""
    body = client.get("/api/config").json()
    assert set(body) == {"modes", "caps", "llm_provider", "llm_model", "voice", "password_reset"}  # reset: a yes/no only
    assert set(body["voice"]) == {"available", "languages"}  # whether voice is on, never the key
    assert set(body["modes"]) == {"jev", "llm", "github", "badge", "fixture_services", "label"}
    assert set(body["caps"]) == {"max_llm_calls_per_run", "max_jev_calls_per_run", "max_github_calls_per_run"}


def test_a_secret_that_reaches_a_log_line_is_redacted():
    formatter = JsonFormatter(secrets=list(FAKE_KEYS.values()))
    record = logging.LogRecord(
        "archway.test", logging.INFO, __file__, 1,
        "calling provider with key %s", (FAKE_KEYS["groq_api_key"],), None,
    )
    record.fields = {"header": f"Bearer {FAKE_KEYS['jev_api_key']}"}
    line = formatter.format(record)
    assert FAKE_KEYS["groq_api_key"] not in line
    assert FAKE_KEYS["jev_api_key"] not in line
    assert "[redacted]" in line
    json.loads(line)  # still valid JSON after redaction


def test_env_file_is_ignored_by_git_and_the_example_has_no_values():
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore.split()

    for line in (BACKEND_DIR / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if "KEY" in name or "TOKEN" in name:
            assert value.strip() == "", f"{name} must be empty in .env.example"


# --- Checks against the real keys on this machine -----------------------------------
def real_secret_values() -> list[str]:
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return []
    # Caps are given here only so loading cannot fail if .env lacks them.
    real = Settings(_env_file=env_file, max_llm_calls_per_run=1, max_jev_calls_per_run=1)
    secrets = [real.groq_api_key, real.jev_api_key, real.github_token]
    return [secret.get_secret_value() for secret in secrets if secret is not None]


def files_under(folder: Path, suffixes: set[str]) -> list[Path]:
    if not folder.exists():
        return []
    return [
        file for file in folder.rglob("*")
        if file.is_file() and file.suffix in suffixes and "node_modules" not in file.parts
    ]


def test_real_keys_are_not_in_the_frontend_source_or_build():
    secrets = real_secret_values()
    if not secrets:
        pytest.skip("no backend/.env with keys on this machine")

    frontend = PROJECT_ROOT / "frontend"
    files = files_under(frontend / "src", {".ts", ".tsx", ".css", ".json", ".html"})
    files += files_under(frontend / "dist", {".js", ".css", ".html", ".json", ".map"})
    files += [frontend / "index.html", frontend / "vite.config.ts"]
    assert files, "expected to find frontend files to scan"

    for file in files:
        if not file.exists():
            continue
        text = file.read_text(encoding="utf-8", errors="ignore")
        for secret in secrets:
            # The message names the file, never the secret.
            assert secret not in text, f"a real secret was found in {file.relative_to(PROJECT_ROOT)}"


def test_real_keys_are_not_in_backend_code_docs_or_fixtures():
    secrets = real_secret_values()
    if not secrets:
        pytest.skip("no backend/.env with keys on this machine")

    files = files_under(BACKEND_DIR / "app", {".py", ".sql"})
    files += files_under(BACKEND_DIR / "tests", {".py"})
    files += files_under(BACKEND_DIR / "learning", {".py"})
    files += files_under(BACKEND_DIR / "fixtures", {".json"})
    files += [BACKEND_DIR / ".env.example", *PROJECT_ROOT.glob("*.md")]

    for file in files:
        text = file.read_text(encoding="utf-8", errors="ignore")
        for secret in secrets:
            assert secret not in text, f"a real secret was found in {file.relative_to(PROJECT_ROOT)}"
