"""
Choosing the language-model client from the settings.

This is the ONLY place that decides whether calls are live or fixture, and
which provider is used. To add a provider, add a branch here.
"""

from app.config.settings import Settings
from app.llm.azure import AzureOpenAILLM
from app.llm.base import LLMClient
from app.llm.fixture import FixtureLLM
from app.llm.groq import GroqLLM


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_mode == "fixture":
        return FixtureLLM()

    # Settings already refused to start if live mode lacks a provider or key
    # (see live_services_need_their_settings in app/config/settings.py).
    if settings.llm_provider == "groq" and settings.groq_api_key and settings.llm_model:
        return GroqLLM(api_key=settings.groq_api_key.get_secret_value(), model=settings.llm_model,
                       max_concurrency=settings.llm_max_concurrency or 1)

    if (settings.llm_provider == "azure" and settings.azure_openai_api_key and settings.azure_openai_endpoint
            and settings.llm_model):
        return AzureOpenAILLM(
            api_key=settings.azure_openai_api_key.get_secret_value(), endpoint=settings.azure_openai_endpoint,
            deployment=settings.llm_model, api_version=settings.azure_openai_api_version,
            max_concurrency=settings.llm_max_concurrency or 4,
        )

    raise ValueError(f"LLM_PROVIDER '{settings.llm_provider}' is not supported yet. Supported: groq, azure")
