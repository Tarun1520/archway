"""
Deepgram as the voice provider.

What this file does
    listen()  opens Deepgram's live speech-to-text over a WebSocket and turns
              its replies into simple {"type": "transcript", ...} events.
    speak()   asks Deepgram's text-to-speech for mp3 and passes it on in pieces.

The settings it uses for listening, and why
    nova-3              Deepgram's speech model; it covers all five languages
    interim_results     words arrive WHILE the person speaks, then get corrected
    filler_words        "um", "uh", "hmm" are kept, so the person can see that
                        every sound is being heard
    smart_format        numbers, punctuation and capitals, as written text
    endpointing=300     a pause of 0.3 s ends a phrase (Archy's own 4-second
                        "are you done?" timer runs in the browser)

The key is sent only from here, in a request header, never to the browser.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlencode

import httpx
import websockets

from app.voice.base import LANGUAGES, MAX_SPEED, MIN_SPEED, VOICE_ID, VoiceError, VoiceInfo

LISTEN_URL = "wss://api.deepgram.com/v1/listen"
SPEAK_URL = "https://api.deepgram.com/v1/speak"
MODELS_URL = "https://api.deepgram.com/v1/models"
KEEP_ALIVE_SECONDS = 5  # Deepgram hangs up after ~10 s without audio: a tiny "still here" message every 5 s prevents it
log = logging.getLogger(__name__)
VOICES_KEPT_SECONDS = 3600  # the catalogue hardly ever changes: ask the service once an hour at most


class DeepgramStream:
    """One open listening session with Deepgram."""

    def __init__(self, socket):
        self._socket = socket
        # LEARNING NOTE: while the browser is silent (Archy talking, the microphone paused) no audio goes
        # out, and Deepgram would close the line. A background task sends "KeepAlive" so it stays open.
        self._keeper = asyncio.create_task(self._keep_alive())

    async def _keep_alive(self) -> None:
        try:
            while True:
                await asyncio.sleep(KEEP_ALIVE_SECONDS)
                await self._socket.send(json.dumps({"type": "KeepAlive"}))
        except (asyncio.CancelledError, websockets.WebSocketException):
            return

    def stop_keeping_alive(self) -> None:
        self._keeper.cancel()

    async def send_audio(self, chunk: bytes) -> None:
        await self._socket.send(chunk)

    async def finish(self) -> None:
        # Deepgram's own "no more audio" message: it replies with its last words, then closes.
        await self._socket.send(json.dumps({"type": "CloseStream"}))

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        try:
            async for raw in self._socket:
                event = self._read(raw)
                if event is not None:
                    yield event
        except websockets.ConnectionClosedError as closed:
            code = closed.rcvd.code if closed.rcvd else None
            log.warning("speech service closed the listening line (code %s, reason %r)", code, closed.rcvd.reason if closed.rcvd else "")
            raise VoiceError("the speech service closed the connection") from None

    @staticmethod
    def _read(raw) -> dict[str, Any] | None:
        """Deepgram's reply as a simple event, or None for replies without words."""
        if isinstance(raw, bytes):
            return None
        message = json.loads(raw)
        if message.get("type") != "Results":
            return None  # metadata and keep-alive replies carry no words
        alternatives = message.get("channel", {}).get("alternatives") or [{}]
        return {
            "type": "transcript",
            "text": alternatives[0].get("transcript", ""),
            "final": bool(message.get("is_final")),
            "speech_final": bool(message.get("speech_final")),
        }


class DeepgramVoice:
    def __init__(self, api_key: str, voice: str):
        self._api_key = api_key
        self._voice = voice
        self._voices: list[VoiceInfo] = []
        self._voices_at = 0.0

    @asynccontextmanager
    async def listen(self, language: str, fillers: bool = True):
        if language not in LANGUAGES:
            raise VoiceError(f"unsupported language: {language}")
        query = urlencode({
            "model": "nova-3", "language": language,
            "encoding": "linear16", "sample_rate": 16000, "channels": 1,
            "interim_results": "true", "filler_words": str(fillers).lower(), "smart_format": "true",
            "punctuate": "true", "endpointing": 300,
        })
        try:
            socket = await websockets.connect(f"{LISTEN_URL}?{query}", additional_headers={"Authorization": f"Token {self._api_key}"})
        except (OSError, websockets.WebSocketException) as error:
            raise VoiceError(f"could not reach the speech service ({type(error).__name__})") from None
        try:
            stream = DeepgramStream(socket)
            yield stream
        finally:
            if "stream" in locals():
                stream.stop_keeping_alive()
            await socket.close()

    async def speak(self, text: str, voice: str | None = None, speed: float | None = None) -> AsyncIterator[bytes]:
        chosen = voice or self._voice
        if not VOICE_ID.match(chosen):
            raise VoiceError(f"unknown voice: {chosen[:40]}")
        params: dict[str, str | float] = {"model": chosen, "encoding": "mp3"}
        if speed is not None and speed != 1.0:
            params["speed"] = min(MAX_SPEED, max(MIN_SPEED, speed))
        headers = {"Authorization": f"Token {self._api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream("POST", SPEAK_URL, params=params, headers=headers, json={"text": text}) as response:
                if response.status_code != 200:
                    raise VoiceError(f"the voice service answered {response.status_code}")
                async for chunk in response.aiter_bytes():
                    yield chunk

    async def voices(self) -> list[VoiceInfo]:
        """The English voices, from the service's own catalogue (name, accent, age, gender, style)."""
        if self._voices and time.monotonic() - self._voices_at < VOICES_KEPT_SECONDS:
            return self._voices
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(MODELS_URL, headers={"Authorization": f"Token {self._api_key}"})
        except httpx.HTTPError as error:
            raise VoiceError(f"could not reach the voice service ({type(error).__name__})") from None
        if response.status_code != 200:
            raise VoiceError(f"the voice service answered {response.status_code}")
        found: list[VoiceInfo] = []
        for model in response.json().get("tts", []):
            details = model.get("metadata", {})
            tags = details.get("tags", [])
            gender = "feminine" if "feminine" in tags else "masculine" if "masculine" in tags else None
            name = model.get("canonical_name", "")
            if model.get("architecture") != "aura-2" or not VOICE_ID.match(name) or not name.endswith("-en") or gender is None:
                continue  # English Aura-2 voices only: they are the ones that can speak Archy's lines
            found.append(VoiceInfo(
                id=name, name=(details.get("display_name") or model.get("name") or name).capitalize(), accent=details.get("accent", ""),
                age=details.get("age", ""), gender=gender, tags=[tag for tag in tags if tag not in ("feminine", "masculine")],
            ))
        found.sort(key=lambda voice: (voice.accent != "American", voice.accent, voice.name))
        self._voices, self._voices_at = found, time.monotonic()
        return found
