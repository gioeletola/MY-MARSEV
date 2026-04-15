"""
Security Stack — multi-layer security orchestration for SOVEREIGN AI OS.

Layers:
1. Input scanning (prompt injection, malicious payloads)
2. Permission enforcement (action class gating)
3. Data leak prevention (PII/secret detection)
4. Audit logging (all security events)
5. Incident escalation (to IncidentRegistry)

Also exposes security agent factory for the swarm.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from sovereign.kernel.action_classes import ActionClass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore (previous|prior|above|all) instructions", re.I),
    re.compile(r"disregard (your|the|all) (instructions|guidelines|rules)", re.I),
    re.compile(r"you are (now |)(a |an |)(different|new|evil|jailbroken)", re.I),
    re.compile(r"pretend (you are|to be)", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"DAN mode", re.I),
    re.compile(r"override (constitution|safety|guidelines)", re.I),
]

_PII_PATTERNS = [
    re.compile(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b"),          # SSN
    re.compile(r"\b\d{16}\b"),                                    # Credit card (simple)
    re.compile(r"\b[A-Z]{2}\d{6}[A-Z]\b"),                       # Passport (generic)
    re.compile(r"password\s*[:=]\s*\S+", re.I),                  # Password literal
    re.compile(r"api[_\s-]?key\s*[:=]\s*\S+", re.I),            # API key literal
    re.compile(r"secret\s*[:=]\s*\S+", re.I),                    # Secret literal
]

_DANGEROUS_COMMANDS = [
    re.compile(r"\brm\s+-rf\b"),
    re.compile(r"\bformat\s+[Cc]:\b"),
    re.compile(r"\bdrop\s+table\b", re.I),
    re.compile(r"\bshutdown\b|\breboot\b", re.I),
    re.compile(r"\bdd\s+if="),
]


@dataclass
class SecurityEvent:
    """Immutable record of a security check result."""
    event_id: str
    check_type: str      # "injection" | "pii" | "dangerous_cmd" | "permission"
    severity: str        # "low" | "medium" | "high" | "critical"
    triggered: bool
    detail: str
    source: str          # agent_id or "input"
    timestamp: str


class SecurityStack:
    """
    Orchestrates all security layers.

    Usage:
        stack = SecurityStack(incident_registry=...)
        result = stack.scan_input(text, source="user_input")
        if result["blocked"]:
            raise SecurityError(result["reason"])
    """

    def __init__(self, incident_registry: Any | None = None) -> None:
        self._incident_registry = incident_registry
        self._event_log: list[SecurityEvent] = []
        self._callbacks: list[Callable[[SecurityEvent], None]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_input(self, text: str, source: str = "unknown") -> dict[str, Any]:
        """
        Full input scan: injection + PII + dangerous commands.
        Returns {"blocked": bool, "reason": str, "events": list}.
        """
        events: list[SecurityEvent] = []

        # 1. Prompt injection
        for pattern in _PROMPT_INJECTION_PATTERNS:
            if pattern.search(text):
                ev = self._make_event("injection", "critical", True,
                                      f"Injection pattern matched: {pattern.pattern[:40]}", source)
                events.append(ev)
                self._handle_event(ev)
                return {"blocked": True, "reason": "Prompt injection detected", "events": [e.__dict__ for e in events]}

        # 2. PII detection
        for pattern in _PII_PATTERNS:
            if pattern.search(text):
                ev = self._make_event("pii", "high", True,
                                      "PII pattern detected in content", source)
                events.append(ev)
                self._handle_event(ev)
                # PII: warn but don't hard-block (depends on context)
                break

        # 3. Dangerous commands
        for pattern in _DANGEROUS_COMMANDS:
            if pattern.search(text):
                ev = self._make_event("dangerous_cmd", "high", True,
                                      f"Dangerous command pattern: {pattern.pattern[:40]}", source)
                events.append(ev)
                self._handle_event(ev)

        blocked = any(e.triggered and e.severity == "critical" for e in events)
        return {
            "blocked": blocked,
            "reason": "Dangerous content detected" if blocked else "",
            "events": [e.__dict__ for e in events],
        }

    def check_permission(
        self,
        action_class: ActionClass,
        agent_id: str,
        max_allowed: ActionClass = ActionClass.SUGGEST,
    ) -> dict[str, Any]:
        """
        Enforce action class ceiling.
        Returns {"allowed": bool, "reason": str}.
        """
        allowed = action_class.value <= max_allowed.value
        if not allowed:
            ev = self._make_event(
                "permission", "high", True,
                f"Agent {agent_id} attempted {action_class.name} (max={max_allowed.name})",
                agent_id,
            )
            self._handle_event(ev)
            return {"allowed": False, "reason": f"Action class {action_class.name} exceeds limit {max_allowed.name}"}
        return {"allowed": True, "reason": ""}

    def scan_output(self, text: str, source: str = "agent") -> dict[str, Any]:
        """Scan outbound text for accidental secret leakage."""
        leaked: list[str] = []
        for pattern in _PII_PATTERNS:
            if pattern.search(text):
                leaked.append(pattern.pattern[:30])
        if leaked:
            ev = self._make_event("pii", "high", True,
                                  f"PII detected in output: {leaked}", source)
            self._handle_event(ev)
            return {"leaked": True, "patterns": leaked}
        return {"leaked": False, "patterns": []}

    def add_callback(self, fn: Callable[[SecurityEvent], None]) -> None:
        """Register a callback invoked on every security event."""
        self._callbacks.append(fn)

    def recent_events(self, limit: int = 50) -> list[dict]:
        return [e.__dict__ for e in self._event_log[-limit:]]

    def stats(self) -> dict[str, Any]:
        total = len(self._event_log)
        triggered = sum(1 for e in self._event_log if e.triggered)
        return {
            "total_checks": total,
            "triggered": triggered,
            "by_type": {
                t: sum(1 for e in self._event_log if e.check_type == t)
                for t in {e.check_type for e in self._event_log}
            },
        }

    # ------------------------------------------------------------------

    def _make_event(self, check_type, severity, triggered, detail, source) -> SecurityEvent:
        ev = SecurityEvent(
            event_id=str(uuid.uuid4())[:8],
            check_type=check_type,
            severity=severity,
            triggered=triggered,
            detail=detail,
            source=source,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._event_log.append(ev)
        return ev

    def _handle_event(self, ev: SecurityEvent) -> None:
        for cb in self._callbacks:
            try:
                cb(ev)
            except Exception:
                pass
        if ev.severity in ("high", "critical") and self._incident_registry:
            try:
                from sovereign.registries.incident_registry import Incident
                incident = Incident(
                    incident_id=ev.event_id,
                    severity=ev.severity,
                    category="security",
                    title=f"Security: {ev.check_type}",
                    description=ev.detail,
                    agent_id=ev.source,
                )
                self._incident_registry.record(incident)
            except Exception as exc:
                logger.error("SecurityStack: failed to record incident: %s", exc)
        if ev.severity == "critical":
            logger.critical("SECURITY [%s]: %s (source=%s)", ev.check_type, ev.detail, ev.source)
        elif ev.severity == "high":
            logger.warning("SECURITY [%s]: %s (source=%s)", ev.check_type, ev.detail, ev.source)
        else:
            logger.info("SECURITY [%s]: %s", ev.check_type, ev.detail)
