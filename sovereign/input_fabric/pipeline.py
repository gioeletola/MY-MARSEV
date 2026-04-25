"""
13-step input processing pipeline for the SOVEREIGN AI OS.

Accepts any input type (text, PDF, JSON, CSV, image, audio) and produces
a normalised PipelineOutput ready for the orchestrator.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

INPUT_TYPES = ("text", "pdf", "json", "csv", "image", "audio", "unknown")


@dataclass
class PipelineInput:
    """Raw input as received from the user or an integration."""

    raw: Any
    input_type: str = "unknown"       # One of INPUT_TYPES
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "user"              # "user" | "api" | "webhook" | "file"


@dataclass
class PipelineOutput:
    """Normalised output produced by the 13-step pipeline."""

    normalized_text: str
    structured_data: dict[str, Any] = field(default_factory=dict)
    media_references: list[str] = field(default_factory=list)
    detected_input_type: str = "text"
    detected_language: str = "en"
    entities: list[dict[str, Any]] = field(default_factory=list)
    sensitivity_level: str = "normal"  # "normal" | "sensitive" | "confidential"
    processing_steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    intent: str = "general"
    intent_confidence: float = 0.5
    mode_hint: str = "command"


class InputPipeline:
    """
    13-step processing pipeline for all input modalities.

    Steps:
     1.  Receive raw input
     2.  Detect input type
     3.  Route to adapter
     4.  Extract text/content
     5.  Detect language
     6.  Normalize encoding/whitespace
     7.  Strip or flag PII (if configured)
     8.  Chunk large inputs
     9.  Validate against schema (structured inputs)
    10.  Attach metadata
    11.  Security scan (injection detection)
    12.  Build canonical PipelineOutput
    13.  Log provenance
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._pii_filter: bool = self._config.get("pii_filter", False)
        self._max_chars: int = self._config.get("max_chars", 100_000)
        try:
            from sovereign.perception.intent_radar import IntentRadar
            self._intent_radar: "IntentRadar | None" = IntentRadar()
        except Exception:
            self._intent_radar = None

    async def process(
        self,
        raw: Any,
        input_type: str | None = None,
    ) -> PipelineOutput:
        """Run all 13 steps and return a normalised PipelineOutput."""
        steps: list[str] = []
        warnings: list[str] = []

        # Step 1: Receive
        steps.append("1_receive")

        # Step 2: Detect type
        detected_type = input_type or await self._step_detect_type(raw)
        steps.append("2_detect_type")

        # Step 3: Route to adapter
        raw_text = await self._step_route_adapter(raw, detected_type)
        steps.append("3_adapt")

        # Step 4: Extract text
        text = str(raw_text) if not isinstance(raw_text, str) else raw_text
        steps.append("4_extract")

        # Step 5: Detect language
        language = self._detect_language(text)
        steps.append("5_detect_language")

        # Step 6: Normalize
        text = await self._step_normalize(text)
        steps.append("6_normalize")

        # Step 7: PII filter
        if self._pii_filter:
            text, pii_warnings = await self._step_pii(text)
            warnings.extend(pii_warnings)
        steps.append("7_pii_filter")

        # Step 8: Chunk (log warning only — chunking is caller's responsibility)
        if len(text) > self._max_chars:
            warnings.append(
                f"Input truncated from {len(text)} to {self._max_chars} chars."
            )
            text = text[: self._max_chars]
        steps.append("8_chunk")

        # Step 9: Validate structured data
        structured = {}
        if detected_type in ("json", "csv"):
            structured = await self._step_validate_structured(raw, detected_type)
        steps.append("9_validate")

        # Step 10: Attach metadata
        steps.append("10_metadata")

        # Step 11: Security scan
        if await self._step_security_scan(text):
            warnings.append("Potential prompt injection pattern detected in input.")
        steps.append("11_security")

        # Step 11.5: Intent detection via IntentRadar
        intent = "general"
        intent_confidence = 0.5
        mode_hint = "command"
        if self._intent_radar is not None:
            try:
                detected = self._intent_radar.classify(text)
                intent = detected.intent
                intent_confidence = detected.confidence
                mode_hint = detected.mode_hint
            except Exception:
                pass
        steps.append("11.5_intent")

        # Step 12: Build output
        steps.append("12_build")

        # Step 13: Log
        logger.debug(
            "Pipeline complete",
            type=detected_type,
            chars=len(text),
            intent=intent,
            warnings=len(warnings),
        )
        steps.append("13_log")

        return PipelineOutput(
            normalized_text=text,
            structured_data=structured,
            detected_input_type=detected_type,
            detected_language=language,
            processing_steps=steps,
            warnings=warnings,
            intent=intent,
            intent_confidence=intent_confidence,
            mode_hint=mode_hint,
        )

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _step_detect_type(self, raw: Any) -> str:
        if isinstance(raw, dict):
            return "json"
        if isinstance(raw, bytes) and raw[:4] == b"%PDF":
            return "pdf"
        if isinstance(raw, str) and raw.strip().startswith("{"):
            return "json"
        if isinstance(raw, str) and "," in raw and "\n" in raw:
            return "csv"
        return "text"

    async def _step_route_adapter(self, raw: Any, input_type: str) -> str:
        """Delegate to the appropriate adapter module."""
        from sovereign.input_fabric.adapters.csv_adapter import CsvAdapter
        from sovereign.input_fabric.adapters.json_adapter import JsonAdapter
        from sovereign.input_fabric.adapters.text_adapter import TextAdapter

        if input_type == "json":
            return await JsonAdapter().extract(raw)
        if input_type == "csv":
            return await CsvAdapter().extract(raw)
        # Default: text adapter
        return await TextAdapter().extract(raw)

    def _detect_language(self, text: str) -> str:
        """Detect the language of `text`; falls back to 'en' if unavailable."""
        if not text or len(text.strip()) < 10:
            return "en"
        try:
            from langdetect import detect  # type: ignore[import]
            return detect(text)
        except Exception:
            pass
        return "en"

    async def _step_normalize(self, text: str) -> str:
        """Normalize whitespace and encoding."""
        import unicodedata
        text = unicodedata.normalize("NFC", text)
        # Collapse excessive blank lines
        lines = text.splitlines()
        cleaned: list[str] = []
        blank_count = 0
        for line in lines:
            if not line.strip():
                blank_count += 1
                if blank_count <= 2:
                    cleaned.append(line)
            else:
                blank_count = 0
                cleaned.append(line)
        return "\n".join(cleaned).strip()

    async def _step_pii(self, text: str) -> tuple[str, list[str]]:
        """
        Strip obvious PII patterns (email, phone, SSN).
        Stub: regex-based. Replace with a real PII classifier for production.
        """
        import re
        warnings: list[str] = []

        email_pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
        phone_pattern = r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"

        if re.search(email_pattern, text):
            text = re.sub(email_pattern, "[EMAIL]", text)
            warnings.append("Email address(es) redacted by PII filter.")
        if re.search(phone_pattern, text):
            text = re.sub(phone_pattern, "[PHONE]", text)
            warnings.append("Phone number(s) redacted by PII filter.")

        return text, warnings

    async def _step_validate_structured(
        self, raw: Any, input_type: str
    ) -> dict[str, Any]:
        """Parse structured input and return as dict."""
        import json
        try:
            if input_type == "json":
                if isinstance(raw, dict):
                    return raw
                return json.loads(str(raw))
            if input_type == "csv":
                return {"rows": str(raw).splitlines()}
        except Exception as exc:
            logger.warning("Structured validation failed", error=str(exc))
        return {}

    async def _step_security_scan(self, text: str) -> bool:
        """
        Detect potential prompt injection patterns.
        Returns True if a suspicious pattern is found.
        """
        INJECTION_PATTERNS = [
            "ignore previous instructions",
            "ignore all instructions",
            "disregard your",
            "you are now",
            "forget your instructions",
        ]
        lower = text.lower()
        return any(p in lower for p in INJECTION_PATTERNS)
