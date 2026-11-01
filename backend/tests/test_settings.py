"""
Tests for configuration (app/config/).

Covers "configuration validation" and the LIVE/FIXTURE badge rule.
"""

import pytest
from pydantic import ValidationError

from app.config.modes import describe_modes
from app.config.settings import Settings
from tests.conftest import make_settings


def test_call_caps_are_required_with_no_unlimited_default(tmp_path):
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, data_dir=tmp_path)
    missing = {error["loc"][0] for error in caught.value.errors()}
    assert {"max_llm_calls_per_run", "max_jev_calls_per_run"} <= missing


def test_a_cap_of_zero_or_less_is_rejected(tmp_path):
    with pytest.raises(ValidationError):
        make_settings(tmp_path, max_llm_calls_per_run=0)


def test_fixture_is_the_default_mode(tmp_path):
    settings = Settings(_env_file=None, max_llm_calls_per_run=1, max_jev_calls_per_run=1, data_dir=tmp_path)
    assert (settings.jev_mode, settings.llm_mode, settings.github_mode) == ("fixture",) * 3


def test_a_mistyped_mode_is_rejected(tmp_path):
    with pytest.raises(ValidationError):
        make_settings(tmp_path, jev_mode="lvie")


def test_live_mode_without_its_key_refuses_to_start(tmp_path):
    with pytest.raises(ValidationError, match="AI_GATEWAY_API_KEY"):
        make_settings(tmp_path, jev_mode="live", decision_provider="gateway")
    make_settings(tmp_path, jev_mode="live")  # the default, a local Laya, needs no key
    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        make_settings(tmp_path, llm_mode="live", llm_provider="groq", llm_model="some-model")
    with pytest.raises(ValidationError, match="LLM_PROVIDER"):
        make_settings(tmp_path, llm_mode="live")


def test_live_mode_with_its_key_is_accepted(tmp_path):
    settings = make_settings(
        tmp_path, llm_mode="live", llm_provider="groq", llm_model="some-model", groq_api_key="test-key-not-real"
    )
    assert settings.llm_mode == "live"


def test_an_empty_value_means_not_set(tmp_path):
    settings = make_settings(tmp_path, github_token="", llm_model="   ")
    assert settings.github_token is None
    assert settings.llm_model is None


def test_settings_are_read_from_environment_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "12")
    monkeypatch.setenv("MAX_JEV_CALLS_PER_RUN", "7")
    monkeypatch.setenv("ARCHWAY_DATA_DIR", str(tmp_path / "elsewhere"))
    settings = Settings(_env_file=None)
    assert settings.max_llm_calls_per_run == 12
    assert settings.max_jev_calls_per_run == 7
    assert settings.database_path == tmp_path / "elsewhere" / "archway.db"


def test_secrets_do_not_appear_when_settings_are_printed(tmp_path):
    settings = make_settings(tmp_path, groq_api_key="super-secret-value-123")
    assert "super-secret-value-123" not in repr(settings)
    assert "super-secret-value-123" not in str(settings.model_dump())
    # Reading it requires asking on purpose.
    assert settings.groq_api_key.get_secret_value() == "super-secret-value-123"


# --- The LIVE / FIXTURE badge -------------------------------------------------------
def test_badge_is_fixture_and_names_the_services_when_any_is_a_fixture(tmp_path):
    report = describe_modes(make_settings(tmp_path))
    assert report.badge == "FIXTURE"
    assert report.fixture_services == ["jev", "llm", "github"]
    assert report.label == "FIXTURE MODE: jev, llm, github"


def test_badge_is_live_only_when_all_three_are_live(tmp_path):
    keys = dict(llm_provider="groq", llm_model="m", groq_api_key="test-key-not-real", ai_gateway_api_key="test-key-not-real")

    two_live = describe_modes(make_settings(tmp_path, llm_mode="live", jev_mode="live", **keys))
    assert two_live.badge == "FIXTURE"
    assert two_live.fixture_services == ["github"]

    all_live = describe_modes(make_settings(tmp_path, llm_mode="live", jev_mode="live", github_mode="live", **keys))
    assert all_live.badge == "LIVE"
    assert all_live.fixture_services == []
