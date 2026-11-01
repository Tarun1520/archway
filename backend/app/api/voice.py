"""
Voice endpoints: the user speaks their idea, and Archy talks.

    GET /api/voice/voices                         the voices on offer (name, accent, gender, style)
    POST /api/voice/understand                    is what was just said the person's IDEA, or conversation (and a reply)?
    POST /api/voice/judge                         is the idea enough to draft a brief? If not, what is missing?
    POST /api/voice/tidy                          a dictated idea, written once and clearly
    POST /api/voice/answer                        what a spoken answer to one of Archway's questions means
    GET /api/voice/speak?text=&voice=&speed=      Archy saying `text`, as mp3, streamed
    POST /api/voice/pass                          a one-time pass for the listening WebSocket (and where to open it)
    WS  /api/voice/listen?language=&fillers=&pass= microphone audio in, words out, live

Why the browser talks to US and not to the voice service directly
    The voice service needs a key. Anything sent to the browser can be read
    by anyone using it, so the key must stay here. The browser streams its
    microphone to this endpoint; this endpoint passes it on to the service
    with the key, and passes the words back. (LEARNING_GUIDE.md topic 64)

LEARNING NOTE: WebSocket
    A normal request is one question, one answer. A WebSocket stays open, and
    both sides can send at any time. That is what live listening needs:
    audio keeps flowing one way while words keep flowing back the other.
"""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from pydantic import BaseModel, Field

from app.auth import voice_pass
from app.auth.access import UserDep
from app.voice.base import LANGUAGES, MAX_SPEED, MIN_SPEED, VOICE_ID, VoiceError, VoiceInfo
from app.voice.answers import MAX_QUESTIONS, Interpreted, Question, interpret_answer
from app.voice.dictation import MAX_DICTATION, tidy_idea
from app.voice.understanding import MAX_IDEA, MAX_TEXT, judge, understand

router = APIRouter(tags=["voice"])

MAX_SPEAK_CHARACTERS = 600  # Archy's lines are short; this stops accidental huge requests
MAX_LISTEN_SECONDS = 300  # one listening session at most 5 minutes, so a forgotten tab cannot run up costs
NOT_SET_UP = "voice is not set up: add DEEPGRAM_API_KEY to backend/.env and restart the backend"


class UnderstandIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT)
    idea_so_far: str = Field(default="", max_length=MAX_IDEA)
    want_reply: bool = False


class UnderstandOut(BaseModel):
    kind: str
    reply: str


class JudgeIn(BaseModel):
    idea: str = Field(min_length=1, max_length=MAX_IDEA)


class JudgeOut(BaseModel):
    enough: bool
    missing: str


class TidyIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_DICTATION)


class TidyOut(BaseModel):
    text: str


class AnswerIn(BaseModel):
    questions: list[Question] = Field(min_length=1, max_length=MAX_QUESTIONS)
    current: str = Field(max_length=40)
    idea: str = Field(default="", max_length=MAX_IDEA)
    said: str = Field(min_length=1, max_length=MAX_TEXT)


@router.post("/voice/tidy")
async def tidy(body: TidyIn, request: Request) -> TidyOut:
    """The dictated idea, written once and clearly (nothing added, nothing lost)."""
    return TidyOut(text=await tidy_idea(request.app.state.voice_llm, body.text))


@router.post("/voice/answer")
async def answer(body: AnswerIn, request: Request) -> Interpreted:
    """What a spoken answer to one of Archway's questions means, matched to the right questions."""
    return await interpret_answer(request.app.state.voice_llm, body.questions, body.current, body.idea, body.said)


@router.post("/voice/understand")
async def understand_speech(body: UnderstandIn, request: Request) -> UnderstandOut:
    found = await understand(request.app.state.voice_llm, body.text, body.idea_so_far, want_reply=body.want_reply)
    return UnderstandOut(kind=found.kind, reply=found.reply)


@router.post("/voice/judge")
async def judge_idea(body: JudgeIn, request: Request) -> JudgeOut:
    found = await judge(request.app.state.voice_llm, body.idea)
    return JudgeOut(enough=found.enough, missing=found.missing)


@router.get("/voice/voices")
async def voices(request: Request) -> list[VoiceInfo]:
    service = request.app.state.voice
    if service is None:
        raise HTTPException(status_code=503, detail=NOT_SET_UP)
    try:
        return await service.voices()
    except VoiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None


@router.get("/voice/speak")
async def speak(
    request: Request,
    text: str = Query(min_length=1, max_length=MAX_SPEAK_CHARACTERS),
    voice: str | None = Query(default=None, pattern=VOICE_ID.pattern),
    speed: float | None = Query(default=None, ge=MIN_SPEED, le=MAX_SPEED),
) -> StreamingResponse:
    service = request.app.state.voice
    if service is None:
        raise HTTPException(status_code=503, detail=NOT_SET_UP)
    audio = service.speak(text, voice, speed)
    # Wait for the first piece before answering, so a refusal from the service
    # becomes a clear error instead of a broken audio file.
    try:
        first = await anext(audio)
    except StopAsyncIteration:
        first = b""
    except VoiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None

    async def body():
        yield first
        async for chunk in audio:
            yield chunk

    return StreamingResponse(body(), media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


class PassOut(BaseModel):
    voice_pass: str
    # Where to open the WebSocket ("" = this page's own address).
    socket_url: str


@router.post("/voice/pass")
async def voice_pass_for_listening(request: Request, user: UserDep) -> PassOut:
    """A one-time pass for the listening WebSocket, which may live on another address (see app/auth/voice_pass.py)."""
    return PassOut(voice_pass=voice_pass.issue(user.id), socket_url=request.app.state.settings.voice_socket_url.rstrip("/"))


@router.websocket("/voice/listen")
async def listen(socket: WebSocket, language: str = "en", fillers: bool = True) -> None:
    await socket.accept()
    voice = socket.app.state.voice
    if voice is None or language not in LANGUAGES:
        await socket.send_json({"type": "error", "message": NOT_SET_UP if voice is None else f"unsupported language: {language}"})
        await socket.close()
        return

    try:
        async with voice.listen(language, fillers) as stream:
            await socket.send_json({"type": "ready"})

            async def from_browser() -> None:
                """Audio in; a {"type": "stop"} message (or the browser leaving) ends it."""
                async with asyncio.timeout(MAX_LISTEN_SECONDS):
                    try:
                        while True:
                            message = await socket.receive()
                            if message["type"] == "websocket.disconnect":
                                break
                            if message.get("bytes"):
                                await stream.send_audio(message["bytes"])
                            elif message.get("text") and json.loads(message["text"]).get("type") == "stop":
                                break
                    finally:
                        await stream.finish()

            sender = asyncio.create_task(from_browser())
            try:
                # Words out, until the service closes (it does after the stop).
                async for event in stream.events():
                    await socket.send_json(event)
            finally:
                sender.cancel()
        await socket.send_json({"type": "closed"})
    except VoiceError as error:
        await _send_quietly(socket, {"type": "error", "message": str(error)})
    except (WebSocketDisconnect, RuntimeError, TimeoutError):
        pass  # the browser left, or the session hit its time limit: nothing more to send
    await _close_quietly(socket)


async def _send_quietly(socket: WebSocket, message: dict) -> None:
    try:
        await socket.send_json(message)
    except (WebSocketDisconnect, RuntimeError):
        pass


async def _close_quietly(socket: WebSocket) -> None:
    try:
        await socket.close()
    except RuntimeError:
        pass  # already closed
