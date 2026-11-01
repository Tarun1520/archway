"""
Choosing the decision client from the settings (compare app/llm/factory.py).

    JEV_MODE=fixture                        fixed answers, labelled fixture
    JEV_MODE=live, DECISION_PROVIDER=laya    a local Laya server (default), DECISION_URL
                                             (default http://127.0.0.1:8100), DECISION_MODEL
                                             (default typed-decisions). Free, on this Mac.
    JEV_MODE=live, DECISION_PROVIDER=gateway Vercel AI Gateway (needs AI_GATEWAY_API_KEY and a
                                             card on the Vercel account), DECISION_MODEL e.g. typesafe-ai/jev

The receipts always name the engine that answered (laya/... or typesafe-ai/jev):
a substitute is never shown under the Jev name.
"""

from app.config.settings import Settings
from app.decisions.client import DecisionClient, FixtureDecisionClient, GatewayDecisionClient, SystemOneDecisionClient


def build_decision_client(settings: Settings) -> DecisionClient:
    if settings.jev_mode != "live":
        return FixtureDecisionClient()
    if settings.decision_provider == "gateway" and settings.ai_gateway_api_key is not None:
        return GatewayDecisionClient(api_key=settings.ai_gateway_api_key.get_secret_value(), model=settings.decision_model)
    return SystemOneDecisionClient(base_url=settings.decision_url, model=settings.decision_model or None)
