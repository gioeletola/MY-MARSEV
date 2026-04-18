"""
Audio adapter — stub for audio transcription.

Requires the 'audio' optional dependency: pip install sovereign-ai-os[audio]
which installs openai-whisper.
"""
from __future__ import annotations
from typing import Any


class AudioAdapter:
    async def extract(self, raw: Any) -> str:
        try:
            import whisper  # type: ignore[import]
            import tempfile
            import pathlib
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(raw if isinstance(raw, bytes) else str(raw).encode())
                tmp_path = f.name
            model = whisper.load_model("base")
            result = model.transcribe(tmp_path)
            pathlib.Path(tmp_path).unlink(missing_ok=True)
            return result.get("text", "")
        except ImportError:
            return (
                "[Audio adapter requires openai-whisper: "
                "pip install sovereign-ai-os[audio]]"
            )
        except Exception as exc:
            return f"[Audio transcription failed: {exc}]"
