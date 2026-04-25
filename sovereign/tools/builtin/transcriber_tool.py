"""
Transcriber tool — transcribe audio or text content.

Audio transcription is a stub pending Whisper API integration.
Text summarization uses simple extractive (first-3-sentences) logic.
"""
from __future__ import annotations

import logging
import pathlib
import re
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)


class TranscriberTool(BaseTool):
    """
    Transcribe audio files or text content.

    - transcribe_file: stub — returns placeholder until Whisper is wired.
    - transcribe_text: echoes the supplied text as the transcript.
    - summarize_transcript: extractive summary (first 3 sentences).
    """

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="transcriber_tool",
            description="Transcribe audio or text content",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["transcribe_file", "transcribe_text", "summarize_transcript"],
                        "description": (
                            "'transcribe_file' — transcribe an audio file at file_path; "
                            "'transcribe_text' — return text as-is (normalised); "
                            "'summarize_transcript' — extractive summary of text."
                        ),
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Absolute or relative path to audio file (required for transcribe_file).",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text content to process (required for transcribe_text and summarize_transcript).",
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(
        self,
        action: str,
        file_path: str = "",
        text: str = "",
        **_: Any,
    ) -> Any:
        """Execute a transcriber operation."""
        try:
            if action == "transcribe_file":
                if not file_path:
                    return {"error": "file_path is required for transcribe_file"}
                return self._transcribe_file(file_path)
            if action == "transcribe_text":
                if not text:
                    return {"error": "text is required for transcribe_text"}
                return self._transcribe_text(text)
            if action == "summarize_transcript":
                if not text:
                    return {"error": "text is required for summarize_transcript"}
                return self._summarize(text)
            return {"error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.error("TranscriberTool error action=%s: %s", action, exc)
            return {"result": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _transcribe_file(self, file_path: str) -> dict[str, Any]:
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self._transcribe_file_async(file_path))

    async def _transcribe_file_async(self, file_path: str) -> dict[str, Any]:
        path = pathlib.Path(file_path)
        audio_exts = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".aac"}
        if not path.exists():
            return {"error": f"File not found: {file_path}", "file_path": file_path}
        if path.suffix.lower() not in audio_exts:
            return {
                "error": f"Unsupported type '{path.suffix}'. Supported: {sorted(audio_exts)}",
                "file_path": file_path,
            }

        # Path 1: OpenAI Whisper API
        import os
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            result = await self._whisper_api(path, openai_key)
            if result:
                return result

        # Path 2: local openai-whisper package
        result = self._local_whisper(path)
        if result:
            return result

        return {
            "transcript": "",
            "file_path": str(path),
            "note": (
                "No transcription backend available. "
                "Set OPENAI_API_KEY or: pip install openai-whisper"
            ),
        }

    async def _whisper_api(self, path: pathlib.Path, api_key: str) -> dict[str, Any] | None:
        try:
            import httpx
            with open(path, "rb") as audio_file:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        data={"model": "whisper-1"},
                        files={"file": (path.name, audio_file, "application/octet-stream")},
                    )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "transcript": data.get("text", ""),
                    "file_path": str(path),
                    "backend": "openai_whisper_api",
                }
            logger.warning("Whisper API returned %d: %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.warning("Whisper API error: %s", exc)
        return None

    def _local_whisper(self, path: pathlib.Path) -> dict[str, Any] | None:
        try:
            import whisper  # type: ignore[import]
            model = whisper.load_model("base")
            result = model.transcribe(str(path))
            return {
                "transcript": result.get("text", "").strip(),
                "language": result.get("language", ""),
                "file_path": str(path),
                "backend": "local_whisper",
            }
        except ImportError:
            return None
        except Exception as exc:
            logger.warning("Local whisper error: %s", exc)
            return None

    def _transcribe_text(self, text: str) -> dict[str, Any]:
        normalised = " ".join(text.split())
        return {
            "transcript": normalised,
            "char_count": len(normalised),
            "word_count": len(normalised.split()),
        }

    def _summarize(self, text: str) -> dict[str, Any]:
        sentences = self._split_sentences(text)
        summary_sentences = sentences[:3]
        summary = " ".join(summary_sentences)
        return {
            "summary": summary,
            "sentence_count_original": len(sentences),
            "sentence_count_summary": len(summary_sentences),
        }

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Simple sentence splitter on '.', '!', '?' boundaries."""
        raw = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s.strip() for s in raw if s.strip()]
