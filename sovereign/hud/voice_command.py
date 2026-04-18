"""Voice command — recognises spoken commands and routes them to the orchestrator."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

CommandHandler = Callable[[str, float], Awaitable[None]]


@dataclass
class RecognisedCommand:
    text: str
    confidence: float
    source: str        # "whisper_api" | "web_speech" | "stub"
    timestamp: float


class VoiceCommandRecogniser:
    """
    Two-backend voice recogniser:

    1. **Whisper API** (default) — sends audio chunks to the Anthropic/OpenAI
       Whisper endpoint. Requires OPENAI_API_KEY or compatible endpoint.
    2. **Web Speech stub** — placeholder for browser-based recognition
       (wired by the frontend JS and posted to /api/voice endpoint).
    3. **Stub mode** — falls back when no backend is configured.

    Usage::
        recogniser = VoiceCommandRecogniser(api_key="sk-...")
        await recogniser.start(handler=my_async_handler)
    """

    def __init__(
        self,
        api_key: str = "",
        whisper_model: str = "whisper-1",
        language: str = "en",
        sample_rate: int = 16000,
        chunk_duration_s: float = 3.0,
    ) -> None:
        self._api_key = api_key
        self._whisper_model = whisper_model
        self._language = language
        self._sample_rate = sample_rate
        self._chunk_duration_s = chunk_duration_s
        self._running = False
        self._handlers: list[CommandHandler] = []
        self._history: list[RecognisedCommand] = []

        self._pyaudio_available = False
        self._whisper_available = bool(api_key)

        try:
            import pyaudio  # type: ignore
            self._pyaudio_available = True
        except ImportError:
            logger.debug("VoiceCommandRecogniser: pyaudio not installed — mic capture disabled")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_handler(self, handler: CommandHandler) -> None:
        """Register an async callback invoked for every recognised command."""
        self._handlers.append(handler)

    async def start(self) -> None:
        """Start the continuous recognition loop (blocks until stop() is called)."""
        self._running = True
        if self._pyaudio_available and self._whisper_available:
            await self._mic_loop()
        else:
            logger.info(
                "VoiceCommandRecogniser: running in stub mode "
                "(pyaudio=%s, whisper=%s)",
                self._pyaudio_available, self._whisper_available,
            )
            await self._stub_loop()

    def stop(self) -> None:
        self._running = False

    async def transcribe_bytes(self, audio_bytes: bytes, mime: str = "audio/wav") -> RecognisedCommand:
        """
        Transcribe raw audio bytes using the Whisper API.
        Used by the /api/voice REST endpoint to handle browser uploads.
        """
        if not self._api_key:
            return RecognisedCommand(text="", confidence=0.0, source="stub",
                                     timestamp=time.time())
        return await asyncio.get_event_loop().run_in_executor(
            None, self._whisper_transcribe_sync, audio_bytes, mime
        )

    def get_history(self, limit: int = 20) -> list[RecognisedCommand]:
        return self._history[-limit:]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _mic_loop(self) -> None:
        """Capture microphone audio in chunks and transcribe via Whisper."""
        import pyaudio  # type: ignore
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._sample_rate,
            input=True,
            frames_per_buffer=1024,
        )
        logger.info("VoiceCommandRecogniser: mic loop started (%.1fs chunks)", self._chunk_duration_s)
        frames_per_chunk = int(self._sample_rate * self._chunk_duration_s)
        loop = asyncio.get_event_loop()
        try:
            while self._running:
                frames = []
                for _ in range(0, frames_per_chunk, 1024):
                    if not self._running:
                        break
                    data = await loop.run_in_executor(None, stream.read, 1024, False)
                    frames.append(data)
                if frames:
                    audio_bytes = b"".join(frames)
                    cmd = await loop.run_in_executor(
                        None, self._whisper_transcribe_sync, audio_bytes, "audio/pcm"
                    )
                    if cmd.text.strip():
                        await self._dispatch(cmd)
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

    def _whisper_transcribe_sync(self, audio_bytes: bytes, mime: str) -> RecognisedCommand:
        """Blocking Whisper API call — run in executor."""
        try:
            import httpx
            headers = {"Authorization": f"Bearer {self._api_key}"}
            files = {"file": ("audio.wav", audio_bytes, mime),
                     "model": (None, self._whisper_model),
                     "language": (None, self._language)}
            resp = httpx.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers, files=files, timeout=15.0,
            )
            resp.raise_for_status()
            text = resp.json().get("text", "").strip()
            return RecognisedCommand(text=text, confidence=0.9,
                                     source="whisper_api", timestamp=time.time())
        except Exception as exc:
            logger.warning("VoiceCommandRecogniser Whisper error: %s", exc)
            return RecognisedCommand(text="", confidence=0.0,
                                     source="whisper_api", timestamp=time.time())

    async def _stub_loop(self) -> None:
        while self._running:
            await asyncio.sleep(1.0)

    async def _dispatch(self, cmd: RecognisedCommand) -> None:
        self._history.append(cmd)
        if len(self._history) > 200:
            self._history = self._history[-200:]
        for handler in self._handlers:
            try:
                await handler(cmd.text, cmd.confidence)
            except Exception as exc:
                logger.error("VoiceCommandRecogniser handler error: %s", exc)
