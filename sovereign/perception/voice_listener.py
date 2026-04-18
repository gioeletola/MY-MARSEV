"""Voice listener — captures audio and transcribes to text (stub; uses pyaudio + whisper)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ListenerState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    ERROR = "error"


@dataclass
class VoiceInput:
    text: str
    confidence: float = 1.0
    language: str = "en"
    duration_s: float = 0.0
    raw_audio: bytes | None = None


class VoiceListener:
    """
    Listens for voice input and returns transcribed text.
    Real implementation requires: pyaudio, openai-whisper (or faster-whisper).
    This stub simulates the interface for testing.
    """

    def __init__(self, model: str = "whisper-base", language: str = "en") -> None:
        self._model_name = model
        self._language = language
        self._state = ListenerState.IDLE
        self._whisper = None
        self._available = False
        try:
            import whisper  # type: ignore
            self._whisper = whisper.load_model(model)
            self._available = True
            logger.info("Whisper model loaded: %s", model)
        except ImportError:
            logger.warning("whisper not installed — VoiceListener in stub mode")
        except Exception as exc:
            logger.warning("Whisper load failed: %s", exc)

    @property
    def state(self) -> ListenerState:
        return self._state

    @property
    def available(self) -> bool:
        return self._available

    async def listen_once(self, duration_s: float = 5.0) -> VoiceInput | None:
        """Record for `duration_s` seconds and return transcription."""
        if not self._available:
            logger.debug("VoiceListener stub: returning None")
            return None

        self._state = ListenerState.LISTENING
        try:
            audio = await asyncio.get_event_loop().run_in_executor(
                None, self._record_audio, duration_s
            )
            self._state = ListenerState.PROCESSING
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._transcribe, audio
            )
            self._state = ListenerState.IDLE
            return result
        except Exception as exc:
            self._state = ListenerState.ERROR
            logger.error("VoiceListener error: %s", exc)
            return None

    def _record_audio(self, duration_s: float) -> bytes:
        try:
            import pyaudio  # type: ignore
            import wave
            import io
            pa = pyaudio.PyAudio()
            stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000,
                             input=True, frames_per_buffer=1024)
            frames = []
            for _ in range(int(16000 / 1024 * duration_s)):
                frames.append(stream.read(1024))
            stream.stop_stream()
            stream.close()
            pa.terminate()
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b"".join(frames))
            return buf.getvalue()
        except ImportError:
            return b""

    def _transcribe(self, audio_bytes: bytes) -> VoiceInput:
        if not audio_bytes or self._whisper is None:
            return VoiceInput(text="", confidence=0.0)
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            fname = f.name
        try:
            result = self._whisper.transcribe(fname, language=self._language)
            return VoiceInput(
                text=result.get("text", "").strip(),
                confidence=1.0,
                language=self._language,
            )
        finally:
            os.unlink(fname)
