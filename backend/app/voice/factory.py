"""Builds the voice provider from the settings, or None when no key is set (voice is then switched off)."""

from app.config.settings import Settings
from app.voice.base import VoiceClient
from app.voice.deepgram import DeepgramVoice


def build_voice(settings: Settings) -> VoiceClient | None:
    if settings.deepgram_api_key is None:
        return None
    return DeepgramVoice(settings.deepgram_api_key.get_secret_value(), settings.archy_voice)
