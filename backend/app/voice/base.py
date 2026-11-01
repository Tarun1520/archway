"""
The voice service's shape, independent of who provides it.

What this file does
    Says what any voice provider must offer, so the rest of the app never
    depends on one company (the same "plug-and-play" idea as app/llm/):

        listen(language)   a live stream: audio in, words out, as they are spoken
        speak(text)        Archy's voice: text in, audio (mp3) out, in pieces

    Today the provider is Deepgram (deepgram.py). Tests use a fake.

LEARNING NOTE: Protocol
    A Protocol lists the methods a class must have, without making anyone
    inherit from it. Anything with these methods "is" a VoiceClient. That is
    how a test can hand the app a tiny fake instead of the real service.
"""

import re
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol

from pydantic import BaseModel

# The languages the user may speak in, by code. Archy itself speaks English:
# the voice service has no voices in the other four.
LANGUAGES: dict[str, str] = {
    "en": "English",
    "en-IN": "English (India)",
    "te": "Telugu",
    "kn": "Kannada",
    "ta": "Tamil",
    "hi": "Hindi",
}


class VoiceError(Exception):
    """The voice service failed or refused. The message never contains a key."""


# What a voice id looks like ("aura-2-thalia-en"). Checked before an id is sent on to the
# service, so the browser cannot make the backend request anything else.
VOICE_ID = re.compile(r"^aura-2-[a-z]{3,20}-[a-z]{2}$")
MIN_SPEED = 0.7
MAX_SPEED = 1.5


class VoiceInfo(BaseModel):
    """One voice Archy can speak with, as the settings page lists it."""

    id: str
    name: str
    accent: str
    age: str
    gender: str  # "feminine" or "masculine"
    tags: list[str]


class SpeechStream(Protocol):
    """One live listening session."""

    async def send_audio(self, chunk: bytes) -> None:
        """A piece of microphone audio: 16-bit samples, 16 000 a second, one channel."""

    async def finish(self) -> None:
        """No more audio is coming; the service sends its last words and ends."""

    def events(self) -> AsyncIterator[dict[str, Any]]:
        """What the service heard, as {"type": "transcript", "text", "final", "speech_final"}."""


class VoiceClient(Protocol):
    def listen(self, language: str, fillers: bool = True) -> AbstractAsyncContextManager[SpeechStream]:
        """Open a listening session for one language code from LANGUAGES.

        With `fillers`, sounds like "um" and "hmm" are kept in the words.
        """

    def speak(self, text: str, voice: str | None = None, speed: float | None = None) -> AsyncIterator[bytes]:
        """Archy saying `text`, as mp3 audio in pieces (so playback can start at once).

        `voice` is one id from voices() (default: the configured one); `speed`
        is a multiplier from MIN_SPEED to MAX_SPEED.
        """

    async def voices(self) -> list[VoiceInfo]:
        """The English voices on offer."""
