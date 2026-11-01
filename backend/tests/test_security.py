"""
The defences around the whole app: where requests come from, the headers on every answer, the session cookie,
secrets kept out of messages, and privacy between accounts (including from the admin).
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import auth as auth_api
from app.llm.base import LLMError
from app.llm.fixture import FixtureLLM, keyword_brief_draft
from app.main import create_app
from app.security.guard import origin_allowed
from app.security.scrub import register_secrets, scrub
from tests.conftest import make_settings
from tests.test_workflow import events_of

PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def fresh_counters():
    auth_api._failures.clear()
    auth_api._signups.clear()
    yield
    auth_api._failures.clear()
    auth_api._signups.clear()
    register_secrets([])


def app_for(tmp_path, **settings):
    return create_app(make_settings(tmp_path / "data", **settings))


# --- Where requests come from ---------------------------------------------------------------------------------------


def test_only_archway_s_own_sites_may_send_changes():
    assert origin_allowed("http://localhost:5173", [], local=True)
    assert origin_allowed("http://127.0.0.1:5181", [], local=True)
    assert not origin_allowed("https://evil.example", [], local=True)
    assert not origin_allowed("http://localhost:5173", [], local=False)  # the deployed site allows only its own
    assert origin_allowed("https://archway.vercel.app", ["https://archway.vercel.app"], local=False)
    assert not origin_allowed("https://archway.vercel.app.evil.example", ["https://archway.vercel.app"], local=False)


def test_a_change_sent_from_another_site_is_refused(tmp_path):
    with TestClient(app_for(tmp_path)) as client:
        evil = client.post("/api/projects", json={"name": "x"}, headers={"Origin": "https://evil.example"})
        assert evil.status_code == 403
        assert client.post("/api/projects", json={"name": "x"}, headers={"Origin": "http://localhost:5173"}).status_code == 201
        assert client.get("/api/projects", headers={"Origin": "https://evil.example"}).status_code == 200  # reading is harmless


def test_the_voice_websocket_refuses_another_site(tmp_path):
    with TestClient(app_for(tmp_path)) as client:
        with pytest.raises(WebSocketDisconnect) as closed:
            with client.websocket_connect("/api/voice/listen", headers={"Origin": "https://evil.example"}) as socket:
                socket.receive_text()
        assert closed.value.code == 1008


# --- Headers ------------------------------------------------------------------------------------------------------------


def test_every_answer_carries_the_security_headers(tmp_path):
    with TestClient(app_for(tmp_path)) as client:
        headers = client.get("/api/projects").headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert headers["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in headers["content-security-policy"]
        assert headers["cache-control"] == "no-store"
        assert "strict-transport-security" not in headers  # local http: no HSTS


def test_the_https_site_sends_hsts_and_hides_the_api_docs(tmp_path):
    with TestClient(app_for(tmp_path, cookie_secure=True), base_url="https://testserver") as client:
        assert "max-age" in client.get("/api/health").headers["strict-transport-security"]
        assert client.get("/docs").status_code == 404 and client.get("/openapi.json").status_code == 404
    with TestClient(app_for(tmp_path)) as local:
        assert local.get("/openapi.json").status_code == 200  # on your own machine the docs stay


# --- The session cookie ----------------------------------------------------------------------------------------------


def test_the_session_cookie_is_httponly_lax_and_on_https_secure_with_the_host_prefix(tmp_path):
    with TestClient(app_for(tmp_path, auth_enabled=True, cookie_secure=True), base_url="https://testserver") as client:
        answer = client.post("/api/auth/signup", json={"email": "a@example.com", "password": PASSWORD})
        cookie = answer.headers["set-cookie"]
        assert cookie.startswith("__Host-archway_session=")
        assert "HttpOnly" in cookie and "Secure" in cookie and "samesite=lax" in cookie.lower() and "Path=/" in cookie
        assert "Domain" not in cookie


def test_signing_out_ends_the_session_on_the_server(tmp_path):
    with TestClient(app_for(tmp_path, auth_enabled=True)) as client:
        client.post("/api/auth/signup", json={"email": "a@example.com", "password": PASSWORD})
        stolen = client.cookies.get("archway_session")
        client.post("/api/auth/logout")
        client.cookies.set("archway_session", stolen)  # someone kept a copy of the cookie
        assert client.get("/api/projects").status_code == 401


def test_weak_passwords_and_mass_sign_ups_are_refused(tmp_path):
    with TestClient(app_for(tmp_path, auth_enabled=True)) as client:
        assert client.post("/api/auth/signup", json={"email": "anna.lee@example.com", "password": "anna.lee@example.com"}).status_code == 422
        assert client.post("/api/auth/signup", json={"email": "b@example.com", "password": "password123"}).status_code == 422
        assert client.post("/api/auth/signup", json={"email": "c@example.com", "password": "aaaaaaaaaaaa"}).status_code == 422
        for n in range(5):
            assert client.post("/api/auth/signup", json={"email": f"u{n}@example.com", "password": PASSWORD}).status_code == 200
        assert client.post("/api/auth/signup", json={"email": "u9@example.com", "password": PASSWORD}).status_code == 429


# --- Privacy between accounts, the admin included ------------------------------------------------------------------


def test_an_admin_sees_usage_but_not_other_people_s_projects(tmp_path):
    with TestClient(app_for(tmp_path, auth_enabled=True, admin_email="boss@example.com")) as admin, \
         TestClient(app_for(tmp_path, auth_enabled=True, admin_email="boss@example.com")) as user:
        admin.post("/api/auth/signup", json={"email": "boss@example.com", "password": PASSWORD})
        user.post("/api/auth/signup", json={"email": "ann@example.com", "password": PASSWORD})
        project = user.post("/api/projects", json={"name": "Private idea", "idea": "my secret plan"}).json()
        assert admin.get(f"/api/projects/{project['id']}").status_code == 404
        assert admin.get(f"/api/projects/{project['id']}/messages").status_code == 404
        assert all(p["name"] != "Private idea" for p in admin.get("/api/projects").json())
        assert any(row["projects"] == 1 for row in admin.get("/api/admin/users").json())  # the count, not the content


# --- Secrets never reach the browser ---------------------------------------------------------------------------------


def test_key_shaped_text_and_known_secrets_are_scrubbed():
    register_secrets(["my-very-secret-value-123"])
    assert "my-very-secret" not in scrub("oops: my-very-secret-value-123 leaked")
    for leaked in ["Incorrect API key provided: sk-proj-abcdefghijklmnop", "gsk_abcdefghijklmnopqrstuvwx",
                   "Authorization: Bearer abc.def.ghijklmnop", "api_key=abcdef123456", "ghp_abcdefghijklmnopqrstuvwxyz0123"]:
        cleaned = scrub(leaked)
        assert "[redacted]" in cleaned and "abcdefghij" not in cleaned and "abcdef123456" not in cleaned
    assert scrub("the model did not answer within 60 seconds") == "the model did not answer within 60 seconds"


def test_a_model_error_that_echoes_a_key_is_scrubbed_before_the_browser_sees_it(tmp_path):
    def leaky(step, user):
        if step == "intake":
            raise LLMError("the model service answered HTTP 401: Incorrect API key provided: gsk_live_1234567890abcdefXYZ")
        return keyword_brief_draft(step, user)

    with TestClient(create_app(make_settings(tmp_path / "data"), llm=FixtureLLM(responder=leaky))) as client:
        project = client.post("/api/projects", json={"name": "P"}).json()
        client.post(f"/api/projects/{project['id']}/messages", json={"content": "A notes app for my team"})
        run = client.post(f"/api/projects/{project['id']}/runs").json()["id"]
        client.post(f"/api/runs/{run}/start")
        everything = str(events_of(client, run)) + client.get(f"/api/runs/{run}/state").text
        assert "gsk_live_1234567890" not in everything
        assert "[redacted]" in str(events_of(client, run))
