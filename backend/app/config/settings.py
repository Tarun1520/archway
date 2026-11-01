"""
Settings: every value that can differ between machines or runs.

What this file does
    Reads settings from environment variables (and from backend/.env), checks
    them, and gives the rest of the app one typed `Settings` object.

How it plugs in
    `create_app()` in app/main.py calls `get_settings()` once at start-up and
    stores the result on the app. API routes receive it through
    app/api/deps.py. Nothing else in the code reads environment variables.

Learn more
    LEARNING_GUIDE.md topic 30 and backend/learning/20_settings_and_adapters.py
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# .../backend  (this file is backend/app/config/settings.py, so go up 3 levels)
BACKEND_DIR = Path(__file__).resolve().parents[2]

# A service is either really called ("live") or answered from recorded data
# ("fixture"). Literal means: only these exact words are accepted.
ServiceMode = Literal["live", "fixture"]


class Settings(BaseSettings):
    """All settings for the backend, validated when the object is created."""

    # LEARNING NOTE: where values come from
    #   pydantic-settings fills each field from an environment variable with
    #   the same name in capitals (jev_mode <- JEV_MODE). `env_file` makes it
    #   also read backend/.env, which is convenient while developing.
    #   `extra="ignore"` means unknown variables in .env are not an error.
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # --- Service modes -------------------------------------------------------
    # "fixture" is the SAFE default: nothing paid happens unless someone
    # deliberately switches a service to "live".
    jev_mode: ServiceMode = "fixture"
    llm_mode: ServiceMode = "fixture"
    github_mode: ServiceMode = "fixture"

    # --- Per-run call caps ---------------------------------------------------
    # No default on purpose. IMPLEMENTATION_GUIDE.md section 5.3 says these are
    # required: "there is no unlimited default". `gt=0` means "greater than 0".
    max_llm_calls_per_run: int = Field(gt=0)
    max_jev_calls_per_run: int = Field(gt=0)
    # GitHub requests per run. 60 is GitHub's whole hourly allowance without a
    # token, so one run cannot exhaust it twice over.
    max_github_calls_per_run: int = Field(default=90, gt=0)

    @property
    def origin_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    @property
    def docs_enabled(self) -> bool:
        return self.api_docs if self.api_docs is not None else not self.cookie_secure

    @property
    def github_calls_cap(self) -> int:
        """The cap a run actually uses: three times larger with a token.

        A token lifts GitHub's allowance from 60 reads an hour to 5,000, so the
        same run can look at many more repositories without risk.
        """
        return self.max_github_calls_per_run * (3 if self.github_token else 1)

    # Run the research team in the background after approval (the request
    # returns at once). Tests switch it off so each request finishes its work.
    background_research: bool = True

    # --- LLM provider --------------------------------------------------------
    llm_provider: str | None = None
    llm_model: str | None = None
    # How many model requests may be in flight at once. None = the provider's
    # default: 1 for Groq (free tier, tight rate limit), 4 for Azure.
    llm_max_concurrency: int | None = Field(default=None, ge=1, le=16)

    # --- Secrets -------------------------------------------------------------
    # LEARNING NOTE: SecretStr
    #   A SecretStr hides its value when printed or logged: it shows as
    #   '**********'. You must call .get_secret_value() on purpose to read it.
    #   That makes it much harder to leak a key by accident.
    groq_api_key: SecretStr | None = None
    azure_openai_api_key: SecretStr | None = None
    # Not secret, but they belong with the key. For Azure, LLM_MODEL is the
    # DEPLOYMENT name.
    azure_openai_endpoint: str | None = None
    azure_openai_api_version: str = "2025-04-01-preview"
    jev_api_key: SecretStr | None = None  # older OpenRouter key; not used by the decision step
    # Phase 4 decisions go through Vercel AI Gateway's decision API.
    ai_gateway_api_key: SecretStr | None = None
    # Which engine answers Phase 4's typed questions when JEV_MODE=live:
    # "laya" (local, free, default) or "gateway" (Vercel AI Gateway, needs a card).
    decision_provider: Literal["laya", "gateway"] = "laya"
    decision_url: str = "http://127.0.0.1:8100"
    decision_model: str = "typed-decisions"
    # Eligibility policy: "permissive" excludes GPL/AGPL; "copyleft_ok" allows them.
    license_policy: Literal["permissive", "copyleft_ok"] = "permissive"
    exclude_archived: bool = True
    github_token: SecretStr | None = None
    brave_api_key: SecretStr | None = None  # optional: switches on general web search
    # Voice (Archy): speech to text and text to speech. Without a key, voice is off.
    deepgram_api_key: SecretStr | None = None
    archy_voice: str = "aura-2-thalia-en"  # which voice Archy speaks with
    # Optional quick model for Archy's tiny questions (set VOICE_LLM_MODEL to use Groq's quick model; needs
    # GROQ_API_KEY). Unset: the project's own model answers, which is slower. A failure falls back to it.
    voice_llm_model: str | None = None

    # --- Accounts (sign-in, admin, quotas) -------------------------------------
    # With auth on, every request except health and sign-in needs a signed-in account, and each account sees only
    # its own projects. Off (tests, or a single-person local setup): everything belongs to one built-in local admin.
    auth_enabled: bool = True
    # The account with this email becomes the admin when it signs up (no password is ever written in a file).
    admin_email: str | None = None
    session_days: int = Field(default=30, gt=0)
    # Secure cookies are only sent over HTTPS: switch on wherever the site is served over HTTPS (the deployed site).
    cookie_secure: bool = False
    # The sites allowed to send changes and open the voice WebSocket (comma-separated), e.g. the deployed
    # https://archway.vercel.app. On a local machine (COOKIE_SECURE=false) localhost and 127.0.0.1 are always allowed.
    allowed_origins: str = ""
    # Where the browser opens the voice WebSocket when the page is served from somewhere that cannot forward
    # WebSockets (Vercel), e.g. wss://152-67-1-2.sslip.io. Empty: the page's own address (local, or the server itself).
    voice_socket_url: str = ""
    # Password reset by email (Brevo, free plan, no card). Without BREVO_API_KEY and MAIL_FROM, reset is switched off.
    brevo_api_key: SecretStr | None = None
    mail_from: str | None = None  # the sender address, verified in Brevo
    mail_from_name: str = "Archway"
    # The site address used in emailed links, e.g. https://archway.vercel.app. Empty: the first ALLOWED_ORIGINS entry.
    # (Never taken from the request: a forged Host or Origin header must not be able to point a reset link elsewhere.)
    public_site_url: str = ""
    # The interactive API docs (/docs). Unset: on locally, OFF on the HTTPS site (they describe every endpoint).
    api_docs: bool | None = None
    # Model tokens a new account may use per calendar month (the admin changes it per person). 0 or unset = no limit.
    default_monthly_quota: int | None = Field(default=2_000_000, ge=0)

    # --- Storage and logging -------------------------------------------------
    # The folder name ends in ".nosync" so iCloud Drive leaves the live
    # database alone (a sync client can corrupt an open SQLite file).
    data_dir: Path = Field(default=BACKEND_DIR / "data.nosync", validation_alias="ARCHWAY_DATA_DIR")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("groq_api_key", "azure_openai_api_key", "azure_openai_endpoint", "jev_api_key", "github_token", "brave_api_key", "ai_gateway_api_key", "deepgram_api_key",
                     "llm_provider", "llm_model", "voice_llm_model", "admin_email", mode="before")
    @classmethod
    def empty_text_means_not_set(cls, value):
        """`GITHUB_TOKEN=` in .env arrives as "". Treat that as "not set"."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @model_validator(mode="after")
    def live_services_need_their_settings(self):
        """Refuse to start if a service is switched to live without its key.

        LEARNING NOTE: fail early
          It is far better for the server to stop at start-up with a clear
          message than to fail halfway through a user's run.
        """
        problems = []
        if self.llm_mode == "live":
            if not self.llm_provider or not self.llm_model:
                problems.append("LLM_MODE=live needs LLM_PROVIDER and LLM_MODEL")
            if self.llm_provider == "groq" and self.groq_api_key is None:
                problems.append("LLM_MODE=live with LLM_PROVIDER=groq needs GROQ_API_KEY")
            if self.llm_provider == "azure" and (self.azure_openai_api_key is None or not self.azure_openai_endpoint):
                problems.append("LLM_PROVIDER=azure needs AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT")
        if self.jev_mode == "live" and self.decision_provider == "gateway" and self.ai_gateway_api_key is None:
            problems.append("JEV_MODE=live with DECISION_PROVIDER=gateway needs AI_GATEWAY_API_KEY")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def database_path(self) -> Path:
        """The SQLite file that holds Archway's own tables."""
        return self.data_dir / "archway.db"

    @property
    def checkpoints_path(self) -> Path:
        """The SQLite file LangGraph saves its checkpoints in.

        Kept apart from archway.db on purpose: LangGraph creates and manages
        the tables in this file itself, and we never touch them.
        """
        return self.data_dir / "checkpoints.db"


@lru_cache
def get_settings() -> Settings:
    """Load the settings once and reuse the same object afterwards.

    LEARNING NOTE: lru_cache
      The first call does the work; later calls return the saved result.
    """
    return Settings()
