"""
Accounts: sign-up and sign-in, private projects, the admin's controls, and the monthly token quota.
"""

import pytest
from fastapi.testclient import TestClient

from app.api import auth as auth_api
from app.auth.passwords import hash_password, verify_password
from app.auth.quota_llm import QUOTA_MESSAGE, QuotaLLM
from app.llm.base import LLMError, LLMResult
from app.main import create_app
from tests.conftest import make_settings
from tests.test_workflow import events_of

ADMIN = "boss@example.com"
PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def fresh_attempt_counts():
    auth_api._failures.clear()
    auth_api._signups.clear()
    yield
    auth_api._failures.clear()
    auth_api._signups.clear()


def client_for(tmp_path, **settings):
    values = {"auth_enabled": True, "admin_email": ADMIN, **settings}
    return TestClient(create_app(make_settings(tmp_path / "data", **values)))


def sign_up(client, email, password=PASSWORD):
    return client.post("/api/auth/signup", json={"email": email, "password": password})


# --- Passwords --------------------------------------------------------------------------------------------------------


def test_a_password_is_stored_only_as_a_salted_hash():
    stored = hash_password(PASSWORD)
    assert PASSWORD not in stored and stored.startswith("scrypt$")
    assert stored != hash_password(PASSWORD)  # a new salt every time
    assert verify_password(PASSWORD, stored) and not verify_password("wrong password!", stored)
    assert not verify_password(PASSWORD, "garbage")


# --- Signing in ---------------------------------------------------------------------------------------------------------


def test_everything_but_health_and_sign_in_needs_an_account(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/projects").status_code == 401
        assert client.get("/api/auth/me").status_code == 401


def test_sign_up_sign_out_and_sign_in_again(tmp_path):
    with client_for(tmp_path) as client:
        me = sign_up(client, "Ann@Example.com").json()
        assert me["user"]["email"] == "ann@example.com" and me["user"]["role"] == "user"
        assert me["user"]["monthly_token_quota"] == 2_000_000 and me["tokens_left"] == 2_000_000
        cookie = client.cookies.get("archway_session")
        assert cookie and len(cookie) > 30
        assert client.get("/api/auth/me").status_code == 200
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401
        assert client.post("/api/auth/login", json={"email": "ann@example.com", "password": PASSWORD}).status_code == 200
        assert client.get("/api/auth/me").json()["user"]["email"] == "ann@example.com"


def test_sign_up_refuses_a_short_password_a_bad_email_and_a_taken_email(tmp_path):
    with client_for(tmp_path) as client:
        assert sign_up(client, "a@example.com", "short").status_code == 422
        assert sign_up(client, "not-an-email").status_code == 422
        assert sign_up(client, "a@example.com").status_code == 200
        assert sign_up(client, "A@example.com").status_code == 409


def test_a_wrong_password_and_an_unknown_email_get_the_same_answer_and_guessing_is_limited(tmp_path):
    with client_for(tmp_path) as client:
        sign_up(client, "a@example.com")
        client.post("/api/auth/logout")
        wrong = client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope nope nope"})
        unknown = client.post("/api/auth/login", json={"email": "who@example.com", "password": "nope nope nope"})
        assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()
        for _ in range(4):
            client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope nope nope"})
        assert client.post("/api/auth/login", json={"email": "a@example.com", "password": PASSWORD}).status_code == 429


# --- Private projects -----------------------------------------------------------------------------------------------


def test_each_account_sees_only_its_own_projects_and_runs(tmp_path):
    with client_for(tmp_path) as ann, client_for(tmp_path) as bob:
        sign_up(ann, "ann@example.com")
        sign_up(bob, "bob@example.com")
        project = ann.post("/api/projects", json={"name": "Ann's", "idea": "a notes app"}).json()
        ann.post(f"/api/projects/{project['id']}/messages", json={"content": "a notes app with search"})
        run = ann.post(f"/api/projects/{project['id']}/runs").json()
        assert [p["name"] for p in ann.get("/api/projects").json()] == ["Ann's"]
        assert bob.get("/api/projects").json() == []
        # Someone else's project or run looks exactly like one that does not exist.
        assert bob.get(f"/api/projects/{project['id']}").status_code == 404
        assert bob.get(f"/api/projects/{project['id']}/messages").status_code == 404
        assert bob.get(f"/api/runs/{run['id']}/state").status_code == 404
        assert bob.delete(f"/api/projects/{project['id']}").status_code == 404
        assert ann.get(f"/api/projects/{project['id']}").status_code == 200


def test_the_admin_email_becomes_admin_and_takes_over_projects_from_before_accounts(tmp_path):
    # A project made while accounts were off has no owner.
    with TestClient(create_app(make_settings(tmp_path / "data"))) as old:
        old.post("/api/projects", json={"name": "From before"})
    with client_for(tmp_path) as client:
        me = sign_up(client, ADMIN).json()
        assert me["user"]["role"] == "admin" and me["user"]["monthly_token_quota"] is None
        assert [p["name"] for p in client.get("/api/projects").json()] == ["From before"]


# --- The admin ----------------------------------------------------------------------------------------------------------


def test_only_an_admin_reaches_the_admin_dashboard(tmp_path):
    with client_for(tmp_path) as admin, client_for(tmp_path) as user:
        sign_up(admin, ADMIN)
        sign_up(user, "user@example.com")
        assert user.get("/api/admin/users").status_code == 403
        rows = admin.get("/api/admin/users").json()
        assert {r["user"]["email"] for r in rows} == {ADMIN, "user@example.com"}
        assert all(r["tokens"] == 0 and r["working"] is False for r in rows)


def test_the_admin_sets_a_quota_blocks_and_unblocks(tmp_path):
    with client_for(tmp_path) as admin, client_for(tmp_path) as user:
        sign_up(admin, ADMIN)
        target = sign_up(user, "user@example.com").json()["user"]["id"]
        row = admin.patch(f"/api/admin/users/{target}", json={"monthly_token_quota": 50_000}).json()
        assert row["user"]["monthly_token_quota"] == 50_000 and row["quota_left"] == 50_000
        assert admin.patch(f"/api/admin/users/{target}", json={"monthly_token_quota": 0}).json()["user"]["monthly_token_quota"] is None
        admin.patch(f"/api/admin/users/{target}", json={"status": "blocked"})
        assert user.get("/api/projects").status_code == 401  # signed out everywhere at once
        assert user.post("/api/auth/login", json={"email": "user@example.com", "password": PASSWORD}).status_code == 403
        admin.patch(f"/api/admin/users/{target}", json={"status": "active"})
        assert user.post("/api/auth/login", json={"email": "user@example.com", "password": PASSWORD}).status_code == 200


def test_the_admin_cannot_lock_everyone_out(tmp_path):
    with client_for(tmp_path) as admin:
        me = sign_up(admin, ADMIN).json()["user"]["id"]
        assert admin.patch(f"/api/admin/users/{me}", json={"status": "blocked"}).status_code == 409
        assert admin.patch(f"/api/admin/users/{me}", json={"role": "user"}).status_code == 409


def test_the_dashboard_shows_live_usage_per_account(tmp_path):
    with client_for(tmp_path, max_llm_calls_per_run=40) as admin, client_for(tmp_path, max_llm_calls_per_run=40) as user:
        sign_up(admin, ADMIN)
        target = sign_up(user, "user@example.com").json()["user"]["id"]
        project = user.post("/api/projects", json={"name": "P"}).json()
        user.post(f"/api/projects/{project['id']}/messages", json={"content": "A notes app that searches my markdown files offline."})
        run = user.post(f"/api/projects/{project['id']}/runs").json()["id"]
        user.post(f"/api/runs/{run}/start")
        row = next(r for r in admin.get("/api/admin/users").json() if r["user"]["id"] == target)
        assert row["llm_calls"] >= 1 and row["runs"] == 1 and row["projects"] == 1


# --- The quota ---------------------------------------------------------------------------------------------------------


async def test_the_quota_client_refuses_once_the_tokens_are_used_up():
    class Model:
        mode = "fixture"

        async def complete_json(self, **_):
            return LLMResult(data={}, model="m", input_tokens=60, output_tokens=50)

    limited = QuotaLLM(Model(), tokens_left=100)
    assert limited.mode == "fixture"
    await limited.complete_json(step="x")  # allowed: 100 left before it
    with pytest.raises(LLMError, match="quota"):
        await limited.complete_json(step="x")


def test_a_run_whose_owner_has_no_tokens_left_stops_and_says_why(tmp_path):
    with client_for(tmp_path) as admin, client_for(tmp_path) as user:
        sign_up(admin, ADMIN)
        target = sign_up(user, "user@example.com").json()["user"]["id"]
        project = user.post("/api/projects", json={"name": "P"}).json()
        user.post(f"/api/projects/{project['id']}/messages", json={"content": "A notes app that searches my markdown files offline."})
        run = user.post(f"/api/projects/{project['id']}/runs").json()["id"]
        # The owner has already used more than this quota this month.
        import asyncio

        from app.db.connection import open_connection
        from app.db.usage_repo import add_usage
        from app.models.common import utc_now
        from app.models.usage import UsageEvent

        async def spend():
            async with open_connection(tmp_path / "data" / "archway.db") as db:
                await add_usage(db, UsageEvent(run_id=run, service="llm", mode="fixture", count=1, tokens_if_known=500, timestamp=utc_now()))
        asyncio.run(spend())
        admin.patch(f"/api/admin/users/{target}", json={"monthly_token_quota": 100})
        assert user.get("/api/auth/me").json()["tokens_left"] == 0
        user.post(f"/api/runs/{run}/start")
        errors = [e["data"]["message"] for e in events_of(user, run) if e["event"] == "run_error"]
        assert errors == [QUOTA_MESSAGE]


def test_with_accounts_switched_off_everything_belongs_to_the_local_admin(tmp_path):
    with TestClient(create_app(make_settings(tmp_path / "data"))) as client:
        me = client.get("/api/auth/me").json()
        assert me["user"]["role"] == "admin" and me["auth_enabled"] is False
        assert client.post("/api/auth/signup", json={"email": "a@example.com", "password": PASSWORD}).status_code == 400


# --- The voice pass (the WebSocket on the server's own address, without the cookie) -------------------------------------


def test_a_voice_pass_opens_the_listening_socket_once_and_only_for_its_account(tmp_path):
    from starlette.websockets import WebSocketDisconnect

    from app.auth import voice_pass

    settings = make_settings(tmp_path / "data", auth_enabled=True, admin_email=ADMIN, voice_socket_url="wss://server.example/")
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/voice/pass").status_code == 401  # no pass without signing in
        sign_up(client, "ann@example.com")
        given = client.post("/api/voice/pass").json()
        assert given["socket_url"] == "wss://server.example" and len(given["voice_pass"]) > 30
        client.cookies.clear()  # like the browser on the server's address: no cookie there

        with client.websocket_connect(f"/api/voice/listen?pass={given['voice_pass']}") as socket:
            assert socket.receive_json()["type"] == "error"  # signed in; voice itself is not set up in this test
        for used_or_made_up in (given["voice_pass"], "not-a-real-pass"):
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(f"/api/voice/listen?pass={used_or_made_up}") as socket:
                    socket.receive_json()
        # A pass is not a cookie: it does nothing for ordinary requests.
        fresh = voice_pass.issue("someone")
        assert client.get(f"/api/projects?pass={fresh}").status_code == 401


# --- Forgot password: a reset link by email ----------------------------------------------------------------------------


class FakeMailer:
    def __init__(self):
        self.sent: list[dict] = []

    async def send(self, *, to, subject, text, html):
        self.sent.append({"to": to, "subject": subject, "text": text, "html": html})


def reset_client(tmp_path, mailer):
    settings = make_settings(tmp_path / "data", auth_enabled=True, admin_email=ADMIN,
                             public_site_url="https://archway.example/")
    return TestClient(create_app(settings, mailer=mailer))


def link_token(mail: dict) -> str:
    return mail["text"].split("#/login/reset/")[1].split()[0]


@pytest.fixture(autouse=True)
def fresh_reset_counts():
    auth_api._resets.clear()
    yield
    auth_api._resets.clear()


def test_without_an_email_sender_reset_is_off_and_says_so(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/api/config").json()["password_reset"] is False
        response = client.post("/api/auth/forgot", json={"email": "ann@example.com"})
    assert response.status_code == 503 and "admin" in response.json()["detail"]


def test_a_reset_link_sets_a_new_password_once_and_signs_out_everywhere(tmp_path):
    mailer = FakeMailer()
    with reset_client(tmp_path, mailer) as client:
        assert client.get("/api/config").json()["password_reset"] is True
        sign_up(client, "ann@example.com")
        assert client.post("/api/auth/forgot", json={"email": "Ann@Example.com"}).status_code == 204
        (mail,) = mailer.sent
        assert mail["to"] == "ann@example.com" and "https://archway.example/#/login/reset/" in mail["text"]
        token = link_token(mail)

        # A weak password is refused WITHOUT using up the link.
        weak = client.post("/api/auth/reset", json={"token": token, "password": "password123"})
        assert weak.status_code == 422
        new_password = "a brand new passphrase"
        assert client.post("/api/auth/reset", json={"token": token, "password": new_password}).status_code == 204
        assert client.get("/api/auth/me").status_code == 401  # the old session ended
        again = client.post("/api/auth/reset", json={"token": token, "password": "yet another passphrase"})
        assert again.status_code == 400  # a link works once

        assert client.post("/api/auth/login", json={"email": "ann@example.com", "password": PASSWORD}).status_code == 401
        assert client.post("/api/auth/login", json={"email": "ann@example.com", "password": new_password}).status_code == 200


def test_forgot_password_does_not_reveal_who_has_an_account(tmp_path):
    mailer = FakeMailer()
    with reset_client(tmp_path, mailer) as client:
        sign_up(client, "ann@example.com")
        known = client.post("/api/auth/forgot", json={"email": "ann@example.com"})
        unknown = client.post("/api/auth/forgot", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 204 and known.content == unknown.content == b""
    assert [mail["to"] for mail in mailer.sent] == ["ann@example.com"]


def test_reset_links_are_limited_per_email_and_a_new_one_replaces_the_old(tmp_path):
    mailer = FakeMailer()
    with reset_client(tmp_path, mailer) as client:
        sign_up(client, "ann@example.com")
        for _ in range(5):
            assert client.post("/api/auth/forgot", json={"email": "ann@example.com"}).status_code == 204
        assert len(mailer.sent) == 3  # at most 3 links an hour for one email, silently
        first, last = link_token(mailer.sent[0]), link_token(mailer.sent[-1])
        assert client.post("/api/auth/reset", json={"token": first, "password": "a brand new passphrase"}).status_code == 400
        assert client.post("/api/auth/reset", json={"token": last, "password": "a brand new passphrase"}).status_code == 204


def test_a_made_up_reset_token_does_nothing(tmp_path):
    with reset_client(tmp_path, FakeMailer()) as client:
        response = client.post("/api/auth/reset", json={"token": "x" * 43, "password": "a brand new passphrase"})
    assert response.status_code == 400
