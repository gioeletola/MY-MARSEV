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
        path = pathlib.Path(file_path)
        exists = path.exists()
        suffix = path.suffix.lower()
        audio_exts = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".aac"}
        if exists and suffix not in audio_exts:
            return {
                "error": f"Unsupported file type '{suffix}'. Supported: {sorted(audio_exts)}",
                "file_path": file_path,
            }
        logger.info("TranscriberTool.transcribe_file (stub) path=%s", file_path)
        return {
            "transcript": "Audio transcription not available — wire Whisper API",
            "duration_s": 0,
            "file_path": file_path,
            "file_exists": exists,
            "note": "Stub — integrate OpenAI Whisper or local whisper.cpp for live transcription.",
        }

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
