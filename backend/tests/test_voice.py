"""
Voice (Archy): the speech endpoint and the live listening relay.

A fake voice service stands in for Deepgram, so these tests never use the
network or a key. It records the audio it is sent and answers with words.
"""

from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from app.main import create_app
from app.voice.base import VoiceError, VoiceInfo


class FakeStream:
    def __init__(self, heard: list[bytes]):
        self.heard = heard
        self.finished = False

    async def send_audio(self, chunk: bytes) -> None:
        self.heard.append(chunk)

    async def finish(self) -> None:
        self.finished = True

    async def events(self):
        # Words come back only once the audio has ended, like a service finishing up.
        import asyncio
        while not self.finished:
            await asyncio.sleep(0.01)
        yield {"type": "transcript", "text": "um a notes app", "final": True, "speech_final": True}


class FakeVoice:
    def __init__(self, fail_speaking: bool = False):
        self.heard: list[bytes] = []
        self.languages: list[str] = []
        self.fillers: list[bool] = []
        self.spoken: list[tuple[str, str | None, float | None]] = []
        self.fail_speaking = fail_speaking

    @asynccontextmanager
    async def listen(self, language: str, fillers: bool = True):
        self.languages.append(language)
        self.fillers.append(fillers)
        yield FakeStream(self.heard)

    async def speak(self, text: str, voice: str | None = None, speed: float | None = None):
        self.spoken.append((text, voice, speed))
        if self.fail_speaking:
            raise VoiceError("the voice service answered 401")
        yield b"ID3-mp3-" + text.encode()

    async def voices(self):
        return [
            VoiceInfo(id="aura-2-thalia-en", name="Thalia", accent="American", age="Adult", gender="feminine", tags=["clear"]),
            VoiceInfo(id="aura-2-draco-en", name="Draco", accent="British", age="Adult", gender="masculine", tags=["warm"]),
        ]


def make_client(settings, voice):
    return TestClient(create_app(settings, voice_client=voice))


def test_without_a_key_voice_is_off_and_says_how_to_switch_it_on(client):
    assert client.get("/api/config").json()["voice"]["available"] is False
    response = client.get("/api/voice/speak", params={"text": "Hello"})
    assert response.status_code == 503
    assert "DEEPGRAM_API_KEY" in response.json()["detail"]


def test_config_lists_the_languages_and_never_the_key(settings):
    with make_client(settings, FakeVoice()) as client:
        body = client.get("/api/config").json()
    assert body["voice"] == {"available": True, "languages": {"en": "English", "en-IN": "English (India)", "te": "Telugu", "kn": "Kannada", "ta": "Tamil", "hi": "Hindi"}}


def test_archy_speaks_as_streamed_mp3(settings):
    with make_client(settings, FakeVoice()) as client:
        response = client.get("/api/voice/speak", params={"text": "Hi, I am Archy."})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"ID3-mp3-Hi, I am Archy."


def test_a_refusal_from_the_service_is_a_clear_error_not_broken_audio(settings):
    with make_client(settings, FakeVoice(fail_speaking=True)) as client:
        response = client.get("/api/voice/speak", params={"text": "Hi"})
    assert response.status_code == 502
    assert "401" in response.json()["detail"]


def test_very_long_text_is_refused(settings):
    with make_client(settings, FakeVoice()) as client:
        assert client.get("/api/voice/speak", params={"text": "x" * 601}).status_code == 422


def test_listening_relays_audio_out_and_words_back(settings):
    voice = FakeVoice()
    with make_client(settings, voice) as client:
        with client.websocket_connect("/api/voice/listen?language=te") as socket:
            assert socket.receive_json() == {"type": "ready"}
            socket.send_bytes(b"\x00\x01" * 800)
            socket.send_bytes(b"\x02\x03" * 800)
            socket.send_json({"type": "stop"})
            assert socket.receive_json() == {"type": "transcript", "text": "um a notes app", "final": True, "speech_final": True}
            assert socket.receive_json() == {"type": "closed"}
    assert voice.languages == ["te"]
    assert b"".join(voice.heard) == b"\x00\x01" * 800 + b"\x02\x03" * 800


def test_an_unsupported_language_is_refused(settings):
    with make_client(settings, FakeVoice()) as client:
        with client.websocket_connect("/api/voice/listen?language=xx") as socket:
            message = socket.receive_json()
    assert message["type"] == "error" and "xx" in message["message"]


def test_the_voice_list_names_accent_and_gender(settings):
    with make_client(settings, FakeVoice()) as client:
        body = client.get("/api/voice/voices").json()
    assert [v["id"] for v in body] == ["aura-2-thalia-en", "aura-2-draco-en"]
    assert body[1] == {"id": "aura-2-draco-en", "name": "Draco", "accent": "British", "age": "Adult", "gender": "masculine", "tags": ["warm"]}


def test_the_chosen_voice_and_speed_reach_the_service(settings):
    voice = FakeVoice()
    with make_client(settings, voice) as client:
        client.get("/api/voice/speak", params={"text": "Hi", "voice": "aura-2-draco-en", "speed": 1.25})
        client.get("/api/voice/speak", params={"text": "Plain"})
    assert voice.spoken == [("Hi", "aura-2-draco-en", 1.25), ("Plain", None, None)]


def test_a_voice_id_or_speed_that_does_not_fit_is_refused_before_the_service_is_asked(settings):
    voice = FakeVoice()
    with make_client(settings, voice) as client:
        assert client.get("/api/voice/speak", params={"text": "Hi", "voice": "../../etc"}).status_code == 422
        assert client.get("/api/voice/speak", params={"text": "Hi", "voice": "aura-2-thalia-en&model=x"}).status_code == 422
        assert client.get("/api/voice/speak", params={"text": "Hi", "speed": 3}).status_code == 422
        assert client.get("/api/voice/speak", params={"text": "Hi", "speed": 0.2}).status_code == 422
    assert voice.spoken == []


def test_listening_can_drop_the_ums(settings):
    voice = FakeVoice()
    with make_client(settings, voice) as client:
        for query in ("language=en", "language=en&fillers=false"):
            with client.websocket_connect(f"/api/voice/listen?{query}") as socket:
                socket.receive_json()
                socket.send_json({"type": "stop"})
                while socket.receive_json()["type"] != "closed":
                    pass
    assert voice.fillers == [True, False]


def test_voices_are_off_without_a_key(client):
    assert client.get("/api/voice/voices").status_code == 503
