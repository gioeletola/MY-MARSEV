"""
Privacy mode — restricts data egress and routes sensitive tasks to local models.

Levels:
  OFF      — no filtering
  STANDARD — mask PII in logs only
  STRICT   — mask PII everywhere, route to local models only
  PARANOID — mask everything, no network calls, local only, encrypted memory

Public API:
  PrivacyMode         — context manager / global policy switcher
  PrivacyFilter       — applies filtering to text
  PrivacyProfile      — per-user config
  detect_pii(text)    — returns list[PIIMatch]
  filter_text(text, level) → str
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PII types
# ---------------------------------------------------------------------------

class PIIType(str, Enum):
    EMAIL       = "EMAIL"
    PHONE       = "PHONE"
    SSN         = "SSN"
    CREDIT_CARD = "CREDIT_CARD"
    PASSPORT    = "PASSPORT"
    NAME        = "NAME"
    ADDRESS     = "ADDRESS"
    IP          = "IP"
    API_KEY     = "API_KEY"
    PASSWORD    = "PASSWORD"
    SECRET      = "SECRET"


# ---------------------------------------------------------------------------
# Privacy levels
# ---------------------------------------------------------------------------

class PrivacyLevel(IntEnum):
    PUBLIC   = 0   # No filtering at all
    STANDARD = 1   # Mask PII in logs only
    STRICT   = 2   # Mask PII everywhere, local models only
    PARANOID = 3   # Mask everything, no network, encrypted memory

# Aliases for backward compatibility
PrivacyLevel.OFF     = PrivacyLevel.PUBLIC    # type: ignore[attr-defined]
PrivacyLevel.PRIVATE = PrivacyLevel.STANDARD  # type: ignore[attr-defined]
PrivacyLevel.LOCKED  = PrivacyLevel.STRICT    # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# PII patterns (type → compiled regex)
# ---------------------------------------------------------------------------

_PII_REGEX: list[tuple[PIIType, re.Pattern]] = [
    (PIIType.EMAIL,       re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    (PIIType.PHONE,       re.compile(r"\b(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")),
    (PIIType.SSN,         re.compile(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b")),
    (PIIType.CREDIT_CARD, re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    (PIIType.PASSPORT,    re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")),
    (PIIType.IP,          re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    (PIIType.PASSWORD,    re.compile(r"password\s*[:=]\s*\S+", re.I)),
    (PIIType.API_KEY,     re.compile(r"api[_\s-]?key\s*[:=]\s*\S+", re.I)),
    (PIIType.SECRET,      re.compile(r"secret\s*[:=]\s*\S+", re.I)),
]

# Name/address patterns (heuristic only)
_NAME_PATTERN = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]{1,15}(?:\s+[A-Z][a-z]{1,15}){0,2}\b"
)
_ADDRESS_PATTERN = re.compile(
    r"\b\d{1,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4}\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# PIIMatch
# ---------------------------------------------------------------------------

@dataclass
class PIIMatch:
    pii_type: PIIType
    value: str
    span: tuple[int, int]
    confidence: float = 1.0

    @property
    def redaction_token(self) -> str:
        return f"[{self.pii_type.value}_REDACTED]"


# ---------------------------------------------------------------------------
# detect_pii / filter_text (module-level helpers)
# ---------------------------------------------------------------------------

def detect_pii(text: str) -> list[PIIMatch]:
    """
    Scan *text* for PII and return all matches as PIIMatch objects.

    Covers: EMAIL, PHONE, SSN, CREDIT_CARD, PASSPORT, IP, PASSWORD, API_KEY,
            SECRET, NAME (heuristic), ADDRESS (heuristic).
    """
    matches: list[PIIMatch] = []
    for pii_type, pat in _PII_REGEX:
        for m in pat.finditer(text):
            matches.append(PIIMatch(
                pii_type=pii_type,
                value=m.group(0),
                span=m.span(),
                confidence=1.0,
            ))
    # Heuristic patterns with lower confidence
    for m in _NAME_PATTERN.finditer(text):
        matches.append(PIIMatch(pii_type=PIIType.NAME, value=m.group(0), span=m.span(), confidence=0.75))
    for m in _ADDRESS_PATTERN.finditer(text):
        matches.append(PIIMatch(pii_type=PIIType.ADDRESS, value=m.group(0), span=m.span(), confidence=0.8))

    # Sort by span start
    matches.sort(key=lambda x: x.span[0])
    return matches


def filter_text(text: str, level: PrivacyLevel = PrivacyLevel.STANDARD) -> str:
    """
    Apply PII masking to *text* according to *level*.

    OFF      → return text unchanged
    STANDARD → mask high-confidence PII only (SSN, CC, email, phone, password, keys)
    STRICT   → mask all PII types including heuristic (name, address, IP)
    PARANOID → mask all PII + redact any token-looking string (40+ char alphanumeric)
    """
    if level == PrivacyLevel.OFF:
        return text

    masked = text

    if level >= PrivacyLevel.STANDARD:
        # Mask high-confidence PII from regex patterns
        for pii_type, pat in _PII_REGEX:
            masked = pat.sub(f"[{pii_type.value}_REDACTED]", masked)

    if level >= PrivacyLevel.STRICT:
        # Also mask heuristic patterns
        masked = _NAME_PATTERN.sub("[NAME_REDACTED]", masked)
        masked = _ADDRESS_PATTERN.sub("[ADDRESS_REDACTED]", masked)

    if level >= PrivacyLevel.PARANOID:
        # Mask any remaining 40+ char alphanumeric token
        masked = re.sub(
            r"\b[A-Za-z0-9+/]{40,}\b",
            "[TOKEN_REDACTED]",
            masked,
        )

    return masked


# ---------------------------------------------------------------------------
# PrivacyFilter
# ---------------------------------------------------------------------------

class PrivacyFilter:
    """
    Applies privacy filtering to all text in/out based on the active level.

    Usage:
        f = PrivacyFilter(PrivacyLevel.STRICT)
        safe_text = f.filter(raw_input)
        safe_log = f.filter_for_log(output_text)
    """

    def __init__(self, level: PrivacyLevel = PrivacyLevel.STANDARD) -> None:
        self._level = level

    @property
    def level(self) -> PrivacyLevel:
        return self._level

    def set_level(self, level: PrivacyLevel) -> None:
        self._level = level

    def filter(self, text: str) -> str:
        """Apply full privacy filtering at the active level."""
        return filter_text(text, self._level)

    def filter_for_log(self, text: str) -> str:
        """
        Apply log-level filtering.
        STANDARD+: always mask PII in logs.
        OFF: return as-is.
        """
        log_level = max(self._level, PrivacyLevel.STANDARD) if self._level != PrivacyLevel.OFF else PrivacyLevel.OFF
        return filter_text(text, log_level)

    def should_route_local(self) -> bool:
        """Return True if tasks must be routed to local models only."""
        return self._level >= PrivacyLevel.STRICT

    def network_allowed(self) -> bool:
        """Return True if external network calls are permitted."""
        return self._level < PrivacyLevel.PARANOID

    def detect(self, text: str) -> list[PIIMatch]:
        return detect_pii(text)


# ---------------------------------------------------------------------------
# PrivacyProfile
# ---------------------------------------------------------------------------

@dataclass
class PrivacyProfile:
    """Per-user privacy configuration."""

    user_id: str
    level: PrivacyLevel = PrivacyLevel.STANDARD
    exceptions: list[str] = field(default_factory=list)   # domain/service exceptions
    notes: str = ""

    def filter(self, text: str) -> str:
        return filter_text(text, self.level)

    def allows_domain(self, domain: str) -> bool:
        if self.level == PrivacyLevel.PARANOID:
            return False
        if self.level == PrivacyLevel.STRICT:
            return domain in self.exceptions
        return True

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "level": self.level.name,
            "exceptions": self.exceptions,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# PrivacyMode (global switcher — backward compatible with old PrivacyMode)
# ---------------------------------------------------------------------------

@dataclass
class PrivacyPolicy:
    """Backward-compatible policy dataclass."""
    level: PrivacyLevel = PrivacyLevel.OFF
    allow_cloud_for_non_sensitive: bool = True
    log_inputs: bool = True
    log_outputs: bool = True
    strip_pii_from_logs: bool = False
    allowed_external_domains: list[str] = field(default_factory=lambda: ["api.anthropic.com"])


class PrivacyMode:
    """
    Global privacy mode manager.

    Backward-compatible with old PUBLIC/PRIVATE/LOCKED/PARANOID levels
    (those are now aliases to OFF/STANDARD/STRICT/PARANOID).

    New levels: OFF, STANDARD, STRICT, PARANOID
    """

    def __init__(self, level: PrivacyLevel = PrivacyLevel.OFF) -> None:
        self._policy = PrivacyPolicy()
        self._active_level = level
        self._filter = PrivacyFilter(level)
        self._user_profiles: dict[str, PrivacyProfile] = {}
        self._apply_policy()

    def _apply_policy(self) -> None:
        level = self._active_level
        self._policy.level = level
        self._policy.strip_pii_from_logs = level >= PrivacyLevel.STANDARD
        if level >= PrivacyLevel.STRICT:
            self._policy.allow_cloud_for_non_sensitive = False
            self._policy.log_inputs = False
            self._policy.log_outputs = False
        else:
            self._policy.allow_cloud_for_non_sensitive = True
            self._policy.log_inputs = True
            self._policy.log_outputs = True
        if level == PrivacyLevel.PARANOID:
            self._policy.allowed_external_domains = []

    def set_level(self, level: PrivacyLevel) -> None:
        old = self._active_level
        self._active_level = level
        self._filter.set_level(level)
        self._apply_policy()
        logger.info("PrivacyMode: %s → %s", old.name, level.name)

    def is_cloud_allowed(self, is_sensitive: bool = False) -> bool:
        if self._active_level >= PrivacyLevel.STRICT:
            return False
        if is_sensitive and self._active_level >= PrivacyLevel.STANDARD:
            return False
        return True

    def is_logging_allowed(self) -> bool:
        return self._policy.log_inputs

    def should_strip_pii(self) -> bool:
        return self._policy.strip_pii_from_logs

    def is_external_domain_allowed(self, domain: str) -> bool:
        if self._active_level == PrivacyLevel.PARANOID:
            return False
        return domain in self._policy.allowed_external_domains

    def filter_text(self, text: str) -> str:
        return self._filter.filter(text)

    def filter_for_log(self, text: str) -> str:
        return self._filter.filter_for_log(text)

    def detect_pii(self, text: str) -> list[PIIMatch]:
        return detect_pii(text)

    @property
    def level(self) -> PrivacyLevel:
        return self._active_level

    @property
    def policy(self) -> PrivacyPolicy:
        return self._policy

    @property
    def filter(self) -> PrivacyFilter:
        return self._filter

    # Per-user profiles
    def set_profile(self, profile: PrivacyProfile) -> None:
        self._user_profiles[profile.user_id] = profile

    def get_profile(self, user_id: str) -> PrivacyProfile:
        return self._user_profiles.get(
            user_id,
            PrivacyProfile(user_id=user_id, level=self._active_level),
        )

    def status(self) -> dict[str, Any]:
        return {
            "level": self._active_level.name,
            "cloud_allowed": self.is_cloud_allowed(),
            "logging": self.is_logging_allowed(),
            "strip_pii": self.should_strip_pii(),
            "local_only": not self.is_cloud_allowed(),
            "network_allowed": self._active_level < PrivacyLevel.PARANOID,
        }
