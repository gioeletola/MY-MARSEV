"""
Security Stack — 7-layer multi-layer security orchestration for SOVEREIGN AI OS.

Layers:
1. Prompt injection detection
2. PII detection and masking
3. Dangerous commands detection
4. RBAC (role-based access check)
5. Secret masking in output
6. Audit logging
7. Incident escalation

Exposes:
  SecurityStack.analyze(text, user_id, action) → SecurityAnalysis
  SecurityStack.scan_input(text, source) → dict   [backward-compatible]
  SecurityStack.check_permission(...)              [backward-compatible]
  SecurityStack.scan_output(...)                   [backward-compatible]
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
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
    re.compile(r"\bjailbreak\b", re.I),
    re.compile(r"\bDAN mode\b", re.I),
    re.compile(r"override (constitution|safety|guidelines)", re.I),
    re.compile(r"act as (if you are|an?)\s+\w+\s+without (restrictions|limits|filters)", re.I),
    re.compile(r"do anything now", re.I),
    re.compile(r"(forget|ignore|bypass)\s+(all\s+)?(your\s+)?(previous\s+)?(safety|ethical|system)\s+(rules?|prompt|instructions?)", re.I),
    re.compile(r"new\s+(system\s+)?prompt\s*:", re.I),
    re.compile(r"\[SYSTEM\]|\[INST\]|\[\/INST\]|\<\|im_start\|\>", re.I),
]

_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("SSN",         re.compile(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("PASSPORT",    re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")),
    ("EMAIL",       re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("PHONE",       re.compile(r"\b(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")),
    ("PASSWORD",    re.compile(r"password\s*[:=]\s*\S+", re.I)),
    ("API_KEY",     re.compile(r"api[_\s-]?key\s*[:=]\s*\S+", re.I)),
    ("SECRET",      re.compile(r"secret\s*[:=]\s*\S+", re.I)),
    ("IP_ADDRESS",  re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
]

_DANGEROUS_COMMANDS = [
    # Filesystem destruction
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b"),
    re.compile(r"\bformat\s+[Cc]:\b"),
    re.compile(r"\bsudo\s+rm\b", re.I),
    re.compile(r"\bdd\s+if="),
    re.compile(r"\bmkfs\b|\bwipefs\b"),
    # SQL destruction
    re.compile(r"\bdrop\s+table\b", re.I),
    re.compile(r"\bdrop\s+database\b", re.I),
    re.compile(r"\btruncate\s+table\b", re.I),
    re.compile(r"\bdelete\s+from\b.{0,60}\bwhere\b.{0,20}\b1\s*=\s*1\b", re.I),
    # System control
    re.compile(r"\bshutdown\b|\breboot\b|\bhalt\b|\bpoweroff\b", re.I),
    re.compile(r"\bkill\s+-9\s+-1\b"),
    re.compile(r"\bpkill\s+-[A-Z0-9]*\s+-[ua]\b", re.I),
    # Privilege escalation / persistence
    re.compile(r"\bchmod\s+-R\s+777\b"),
    re.compile(r"\bchmod\s+[a+]s\b"),          # setuid
    re.compile(r"\bcrontab\s+-[rle]"),
    re.compile(r"(^|\s|;|&|\|)\s*at\s+now\b", re.I),
    # Code execution via encoded payloads
    re.compile(r"\beval\s*\(.*\bbase64\b", re.I),
    re.compile(r"\bbase64\b.*\|\s*(ba)?sh\b", re.I),
    re.compile(r"\becho\b.*\bbase64\b.*\|\s*(ba)?sh\b", re.I),
    re.compile(r"\bpython\s+-c\s+['\"].*\\x[0-9a-f]{2}", re.I),
    re.compile(r"\bpython\s+-c\s+['\"].*__import__", re.I),
    re.compile(r"\bxxd\s+-r\b.*\|\s*(ba)?sh\b", re.I),
    # Network pivoting / exfiltration
    re.compile(r"\b(curl|wget)\s+.*(sh|bash|zsh|fish)\s*\|\s*(ba)?sh\b", re.I),
    re.compile(r"\bnc\s+(-[a-zA-Z]*[le][a-zA-Z]*\s+)+", re.I),  # netcat listener
    re.compile(r"\bsocat\b.*\bexec\b", re.I),
    re.compile(r"\b/dev/tcp/", re.I),
    # Fork bombs and resource exhaustion
    re.compile(r":\(\)\s*\{.*\}\s*;"),
    re.compile(r"\bfork\s*bomb\b", re.I),
]

_SECRET_MASK_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(sk-[A-Za-z0-9]{20,})", re.I),          "sk-***MASKED***"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.I), r"\1***MASKED***"),
    (re.compile(r"(api[_\s-]?key\s*[:=]\s*)\S+", re.I),   r"\1***MASKED***"),
    (re.compile(r"(token\s*[:=]\s*)\S+", re.I),            r"\1***MASKED***"),
    (re.compile(r"(password\s*[:=]\s*)\S+", re.I),         r"\1***MASKED***"),
    (re.compile(r"(secret\s*[:=]\s*)\S+", re.I),           r"\1***MASKED***"),
    (re.compile(r"(ANTHROPIC_API_KEY\s*=\s*)\S+", re.I),   r"\1***MASKED***"),
    (re.compile(r"(OPENAI_API_KEY\s*=\s*)\S+", re.I),      r"\1***MASKED***"),
    (re.compile(r"\b[A-Za-z0-9]{32,64}\b"),               "***TOKEN***"),
]

# ---------------------------------------------------------------------------
# RBAC role definitions
# ---------------------------------------------------------------------------

_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin":    {"read", "write", "execute", "delete", "configure", "audit"},
    "operator": {"read", "write", "execute"},
    "analyst":  {"read", "write"},
    "viewer":   {"read"},
    "guest":    {"read"},
}

# Resource-level restrictions per role
_RESOURCE_RESTRICTIONS: dict[str, set[str]] = {
    "viewer": {"secrets", "vault", "financial_ops", "config"},
    "guest":  {"secrets", "vault", "financial_ops", "config", "agent_management"},
}

# Known admin user IDs (can also be set at runtime)
_DEFAULT_ADMIN_USERS: set[str] = {"admin", "system", "sovereign", "ceo_agent"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SecurityEvent:
    """Immutable record of a security check result."""
    event_id: str
    check_type: str      # "injection" | "pii" | "dangerous_cmd" | "rbac" | "secret" | "audit" | "escalation"
    severity: str        # "low" | "medium" | "high" | "critical"
    triggered: bool
    detail: str
    source: str          # agent_id or "input"
    timestamp: str


@dataclass
class SecurityAnalysis:
    """
    Full analysis result from SecurityStack.analyze().

    Attributes:
        passed       – True if no critical/blocking threats detected
        score        – aggregate threat score 0.0-1.0
        threats      – list of threat descriptions
        masked_text  – input text with secrets/PII masked
        audit_id     – unique ID for this analysis (for tracing)
    """
    passed: bool
    score: float
    threats: list[str]
    masked_text: str
    audit_id: str
    events: list[SecurityEvent] = field(default_factory=list)
    layer_results: dict[str, Any] = field(default_factory=dict)

    @property
    def is_safe(self) -> bool:
        """True when aggregate threat score is below 0.3 (low risk)."""
        return self.score < 0.3


# ---------------------------------------------------------------------------
# SecurityStack
# ---------------------------------------------------------------------------

class SecurityStack:
    """
    7-layer security orchestrator.

    Usage (new API):
        stack = SecurityStack()
        analysis = stack.analyze(text, user_id="user123", action="read")
        if not analysis.is_safe:
            raise SecurityError(analysis.threats)

    Usage (backward-compatible):
        result = stack.scan_input(text, source="user_input")
        if result["blocked"]:
            raise SecurityError(result["reason"])
    """

    def __init__(
        self,
        incident_registry: Any | None = None,
        admin_users: set[str] | None = None,
        escalation_threshold: float = 0.7,
    ) -> None:
        self._incident_registry = incident_registry
        self._event_log: list[SecurityEvent] = []
        self._audit_trail: list[dict] = []
        self._callbacks: list[Callable[[SecurityEvent], None]] = []
        self._admin_users: set[str] = admin_users or set(_DEFAULT_ADMIN_USERS)
        self._user_roles: dict[str, str] = {}   # user_id → role
        self._escalation_threshold = escalation_threshold

    # =========================================================================
    # New Primary API
    # =========================================================================

    def analyze(
        self,
        text: str,
        user_id: str = "unknown",
        action: str = "read",
        resource: str = "general",
        source: str = "unknown",
    ) -> SecurityAnalysis:
        """
        Run all 7 security layers and return a SecurityAnalysis.

        Args:
            text      – text to analyze (user input or agent output)
            user_id   – ID of the requesting user/agent
            action    – action being attempted (read/write/execute/delete/…)
            resource  – resource being accessed
            source    – source identifier for audit trail
        """
        audit_id = str(uuid.uuid4())[:12]
        threats: list[str] = []
        score = 0.0
        events: list[SecurityEvent] = []
        layer_results: dict[str, Any] = {}

        # Layer 1 — Prompt injection
        l1 = self._layer_prompt_injection(text)
        layer_results["prompt_injection"] = l1
        if l1["detected"]:
            threats.extend(l1["threats"])
            score += 0.6
            for t in l1["threats"]:
                ev = self._make_event("injection", "critical", True, t, source)
                events.append(ev)
                self._handle_event(ev)

        # Layer 2 — PII detection
        l2 = self._layer_pii_detection(text)
        layer_results["pii"] = l2
        if l2["detected"]:
            threats.extend([f"PII detected: {m}" for m in l2["types"]])
            score += 0.15
            ev = self._make_event("pii", "high", True,
                                  f"PII types found: {l2['types']}", source)
            events.append(ev)
            self._handle_event(ev)

        # Layer 3 — Dangerous commands
        l3 = self._layer_dangerous_commands(text)
        layer_results["dangerous_commands"] = l3
        if l3["detected"]:
            threats.extend(l3["threats"])
            score += 0.4
            for t in l3["threats"]:
                ev = self._make_event("dangerous_cmd", "high", True, t, source)
                events.append(ev)
                self._handle_event(ev)

        # Layer 4 — RBAC
        l4 = self._layer_rbac_check(user_id, action, resource)
        layer_results["rbac"] = l4
        if not l4["allowed"]:
            threats.append(f"RBAC denied: {l4['reason']}")
            score += 0.5
            ev = self._make_event("rbac", "high", True, l4["reason"], user_id)
            events.append(ev)
            self._handle_event(ev)

        # Layer 5 — Secret masking
        l5 = self._layer_secret_masking(text)
        layer_results["secret_masking"] = l5
        masked_text = l5["masked_text"]
        if l5["masked_count"] > 0:
            threats.append(f"Secrets/tokens masked in text ({l5['masked_count']} patterns)")
            score += 0.1

        # Layer 6 — Audit log
        audit_event = {
            "audit_id": audit_id,
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "source": source,
            "threats": threats,
            "score": round(min(score, 1.0), 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._layer_audit_log(audit_event)
        layer_results["audit"] = {"audit_id": audit_id}

        # Layer 7 — Incident escalation
        final_score = min(score, 1.0)
        if final_score >= self._escalation_threshold:
            self._layer_incident_escalation(
                severity="critical" if final_score >= 0.9 else "high",
                description=f"Threat score {final_score:.2f} for user={user_id} action={action}: {threats}",
                audit_id=audit_id,
            )

        passed = not any(
            ev.severity == "critical" for ev in events
        ) and l4["allowed"]

        return SecurityAnalysis(
            passed=passed,
            score=final_score,
            threats=threats,
            masked_text=masked_text,
            audit_id=audit_id,
            events=events,
            layer_results=layer_results,
        )

    # =========================================================================
    # 7 Layer methods
    # =========================================================================

    def _layer_prompt_injection(self, text: str) -> dict[str, Any]:
        """Layer 1: Detect prompt injection patterns."""
        detected_threats: list[str] = []
        for pat in _PROMPT_INJECTION_PATTERNS:
            m = pat.search(text)
            if m:
                detected_threats.append(
                    f"Prompt injection pattern: '{m.group(0)[:60]}'"
                )
        return {
            "detected": bool(detected_threats),
            "threats": detected_threats,
            "count": len(detected_threats),
        }

    def _layer_pii_detection(self, text: str) -> dict[str, Any]:
        """Layer 2: Detect PII (email, phone, SSN, credit card, passport, IP)."""
        found_types: list[str] = []
        matches: list[dict] = []
        for pii_type, pat in _PII_PATTERNS:
            for m in pat.finditer(text):
                found_types.append(pii_type)
                matches.append({"type": pii_type, "span": m.span(), "preview": m.group(0)[:8] + "…"})
        return {
            "detected": bool(found_types),
            "types": list(set(found_types)),
            "matches": matches,
            "count": len(matches),
        }

    def _layer_pii_mask(self, text: str) -> str:
        """Mask all PII in text (used internally and by privacy layer)."""
        masked = text
        for pii_type, pat in _PII_PATTERNS:
            masked = pat.sub(f"[{pii_type}_REDACTED]", masked)
        return masked

    def _layer_dangerous_commands(self, text: str) -> dict[str, Any]:
        """Layer 3: Detect dangerous shell commands and SQL drop statements."""
        threats: list[str] = []
        for pat in _DANGEROUS_COMMANDS:
            m = pat.search(text)
            if m:
                threats.append(f"Dangerous command detected: '{m.group(0)[:60]}'")
        return {
            "detected": bool(threats),
            "threats": threats,
            "count": len(threats),
        }

    def _layer_rbac_check(
        self,
        user_id: str,
        action: str,
        resource: str = "general",
    ) -> dict[str, Any]:
        """Layer 4: Role-based access control check."""
        # Admin users bypass all restrictions
        if user_id in self._admin_users:
            return {"allowed": True, "reason": f"Admin user '{user_id}' granted full access", "role": "admin"}

        role = self._user_roles.get(user_id, "viewer")
        permissions = _ROLE_PERMISSIONS.get(role, {"read"})
        restrictions = _RESOURCE_RESTRICTIONS.get(role, set())

        if action not in permissions:
            return {
                "allowed": False,
                "reason": f"Role '{role}' does not have '{action}' permission",
                "role": role,
            }
        if resource in restrictions:
            return {
                "allowed": False,
                "reason": f"Role '{role}' cannot access restricted resource '{resource}'",
                "role": role,
            }
        return {"allowed": True, "reason": f"Role '{role}' permits '{action}' on '{resource}'", "role": role}

    def _layer_secret_masking(self, text: str) -> dict[str, Any]:
        """Layer 5: Mask API keys, tokens, passwords in output text."""
        masked = text
        masked_count = 0
        for pat, replacement in _SECRET_MASK_PATTERNS[:-1]:   # skip catch-all last
            new = pat.sub(replacement, masked)
            if new != masked:
                masked_count += new.count("***MASKED***") - masked.count("***MASKED***")
                masked = new
        # apply catch-all token pattern only if no already-masked content
        catch_all_pat, _ = _SECRET_MASK_PATTERNS[-1]
        # only mask 40+ char tokens not already masked
        def _mask_token(m: re.Match) -> str:
            val = m.group(0)
            if "***" in val or len(val) < 40:
                return val
            return "***TOKEN***"
        new = catch_all_pat.sub(_mask_token, masked)
        if new != masked:
            masked_count += new.count("***TOKEN***")
        masked = new

        return {
            "masked_text": masked,
            "masked_count": masked_count,
            "changed": masked != text,
        }

    def _layer_audit_log(self, event: dict) -> None:
        """Layer 6: Append to the immutable audit trail."""
        record = {
            **event,
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        self._audit_trail.append(record)
        logger.debug("AUDIT [%s] user=%s action=%s score=%.2f",
                     record.get("audit_id"), record.get("user_id"),
                     record.get("action"), record.get("score", 0.0))

    def _layer_incident_escalation(
        self,
        severity: str,
        description: str,
        audit_id: str = "",
    ) -> None:
        """Layer 7: Escalate high-severity incidents to the incident registry."""
        ev = self._make_event(
            "escalation", severity, True,
            description, "security_stack"
        )
        self._handle_event(ev)
        logger.warning(
            "SECURITY ESCALATION [%s]: %s (audit_id=%s)",
            severity.upper(), description[:120], audit_id
        )

    # =========================================================================
    # Role management
    # =========================================================================

    def set_user_role(self, user_id: str, role: str) -> None:
        """Assign a role to a user (admin/operator/analyst/viewer/guest)."""
        if role not in _ROLE_PERMISSIONS:
            raise ValueError(f"Unknown role '{role}'. Valid: {list(_ROLE_PERMISSIONS)}")
        self._user_roles[user_id] = role

    def add_admin_user(self, user_id: str) -> None:
        self._admin_users.add(user_id)

    # =========================================================================
    # Backward-compatible public API
    # =========================================================================

    def scan_input(self, text: str, source: str = "unknown") -> dict[str, Any]:
        """
        Backward-compatible input scan.
        Returns {"blocked": bool, "reason": str, "events": list}.
        """
        events: list[SecurityEvent] = []

        # Layer 1 — Prompt injection
        l1 = self._layer_prompt_injection(text)
        if l1["detected"]:
            for t in l1["threats"]:
                ev = self._make_event("injection", "critical", True, t, source)
                events.append(ev)
                self._handle_event(ev)
            return {
                "blocked": True,
                "reason": "Prompt injection detected",
                "events": [e.__dict__ for e in events],
            }

        # Layer 2 — PII
        l2 = self._layer_pii_detection(text)
        if l2["detected"]:
            ev = self._make_event("pii", "high", True,
                                  f"PII found: {l2['types']}", source)
            events.append(ev)
            self._handle_event(ev)

        # Layer 3 — Dangerous commands
        l3 = self._layer_dangerous_commands(text)
        if l3["detected"]:
            for t in l3["threats"]:
                ev = self._make_event("dangerous_cmd", "high", True, t, source)
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
        """Backward-compatible: enforce action class ceiling."""
        allowed = action_class.value <= max_allowed.value
        if not allowed:
            ev = self._make_event(
                "permission", "high", True,
                f"Agent {agent_id} attempted {action_class.name} (max={max_allowed.name})",
                agent_id,
            )
            self._handle_event(ev)
            return {
                "allowed": False,
                "reason": f"Action class {action_class.name} exceeds limit {max_allowed.name}",
            }
        return {"allowed": True, "reason": ""}

    def scan_output(self, text: str, source: str = "agent") -> dict[str, Any]:
        """Backward-compatible: scan outbound text for accidental secret leakage."""
        l2 = self._layer_pii_detection(text)
        l5 = self._layer_secret_masking(text)
        leaked_types = l2["types"]
        if l5["masked_count"] > 0:
            leaked_types.append("TOKEN/SECRET")
        if leaked_types:
            ev = self._make_event("pii", "high", True,
                                  f"Data detected in output: {leaked_types}", source)
            self._handle_event(ev)
            return {"leaked": True, "patterns": leaked_types, "masked_text": l5["masked_text"]}
        return {"leaked": False, "patterns": [], "masked_text": text}

    # =========================================================================
    # Helpers & observability
    # =========================================================================

    def add_callback(self, fn: Callable[[SecurityEvent], None]) -> None:
        """Register a callback invoked on every security event."""
        self._callbacks.append(fn)

    def recent_events(self, limit: int = 50) -> list[dict]:
        return [e.__dict__ for e in self._event_log[-limit:]]

    @property
    def audit_trail(self) -> list[dict]:
        return list(self._audit_trail)

    def stats(self) -> dict[str, Any]:
        total = len(self._event_log)
        triggered = sum(1 for e in self._event_log if e.triggered)
        return {
            "total_checks": total,
            "triggered": triggered,
            "audit_entries": len(self._audit_trail),
            "by_type": {
                t: sum(1 for e in self._event_log if e.check_type == t)
                for t in {e.check_type for e in self._event_log}
            },
        }

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
