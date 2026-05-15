"""TTS engine — OpenAI TTS (primary), ElevenLabs (secondary), pyttsx3 (offline fallback)."""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_MAX_TEXT = 4096


class TTSEngine:
    """Text-to-speech with three backends in priority order:

    1. OpenAI TTS (requires OPENAI_API_KEY)
    2. ElevenLabs (requires ELEVENLABS_API_KEY)
    3. pyttsx3 (offline, requires ``pip install pyttsx3``)
    """

    def __init__(self) -> None:
        self._openai_key: str = os.environ.get("OPENAI_API_KEY", "")
        self._elevenlabs_key: str = os.environ.get("ELEVENLABS_API_KEY", "")
        self._elevenlabs_voice_id: str = os.environ.get(
            "ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"
        )
        self._pyttsx3_available = self._check_pyttsx3()
        logger.info("TTSEngine initialised — backend: %s", self.backend)

    @staticmethod
    def _check_pyttsx3() -> bool:
        try:
            import pyttsx3  # type: ignore  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def backend(self) -> str:
        if self._openai_key:
            return "openai"
        if self._elevenlabs_key:
            return "elevenlabs"
        if self._pyttsx3_available:
            return "pyttsx3"
        return "unavailable"

    @property
    def available(self) -> bool:
        return self.backend != "unavailable"

    async def speak(self, text: str, voice: str = "onyx") -> bytes:
        """Return mp3 audio bytes for *text* using the active backend."""
        text = text[:_MAX_TEXT]
        if self._openai_key:
            return await self._openai_tts(text, voice)
        if self._elevenlabs_key:
            return await self._elevenlabs_tts(text)
        if self._pyttsx3_available:
            return await self._pyttsx3_tts(text)
        logger.warning(
            "TTSEngine.speak: no backend available — set OPENAI_API_KEY, ELEVENLABS_API_KEY, "
            "or install pyttsx3. Returning empty audio."
        )
        return b""

    async def speak_to_file(self, text: str, path: Path) -> bool:
        """Write mp3 audio to *path*. Returns True on success."""
        audio = await self.speak(text)
        if not audio:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio)
        return True

    async def _openai_tts(self, text: str, voice: str) -> bytes:
        logger.info("TTSEngine: using openai backend (voice=%s)", voice)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={"Authorization": f"Bearer {self._openai_key}"},
                    json={"model": "tts-1", "input": text, "voice": voice},
                )
                resp.raise_for_status()
                return resp.content
        except Exception as exc:
            logger.warning("TTSEngine openai error: %s", exc)
            if self._elevenlabs_key:
                return await self._elevenlabs_tts(text)
            if self._pyttsx3_available:
                return await self._pyttsx3_tts(text)
            return b""

    async def _elevenlabs_tts(self, text: str) -> bytes:
        logger.info("TTSEngine: using elevenlabs backend (voice_id=%s)", self._elevenlabs_voice_id)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{self._elevenlabs_voice_id}",
                    headers={
                        "xi-api-key": self._elevenlabs_key,
                        "Content-Type": "application/json",
                    },
                    json={"text": text, "model_id": "eleven_monolingual_v1"},
                )
                resp.raise_for_status()
                return resp.content
        except Exception as exc:
            logger.warning("TTSEngine elevenlabs error: %s", exc)
            if self._pyttsx3_available:
                return await self._pyttsx3_tts(text)
            return b""

    async def _pyttsx3_tts(self, text: str) -> bytes:
        logger.info("TTSEngine: using pyttsx3 backend")
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._pyttsx3_sync, text)
        except Exception as exc:
            logger.warning("TTSEngine pyttsx3 error: %s", exc)
            return b""

    @staticmethod
    def _pyttsx3_sync(text: str) -> bytes:
        import pyttsx3  # type: ignore

        engine = pyttsx3.init()
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            return Path(tmp_path).read_bytes()
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass
