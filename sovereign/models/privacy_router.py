"""Privacy router — routes sensitive tasks to local models, others to cloud providers."""
from __future__ import annotations

import logging
import re

from sovereign.models.base_provider import BaseProvider, CompletionRequest, CompletionResponse

logger = logging.getLogger(__name__)

_SENSITIVE_PATTERNS = [
    r"\bpassword\b", r"\bapi[_\s]?key\b", r"\bsecret\b", r"\bssn\b",
    r"\bcredit[_\s]?card\b", r"\biban\b", r"\bbank[_\s]?account\b",
    r"\bprivate[_\s]?key\b", r"\bseed[_\s]?phrase\b", r"\bpassphrase\b",
    r"\bmedical\b", r"\bdiagnos\b", r"\bprescription\b",
    r"\bconfidential\b", r"\bclassified\b", r"\btop[_\s]?secret\b",
]
_SENSITIVE_RE = re.compile("|".join(_SENSITIVE_PATTERNS), re.IGNORECASE)


class PrivacyRouter:
    """
    Routes requests:
    - If content contains sensitive keywords → local provider (no data leaves device)
    - Otherwise → cloud provider (faster, more capable)

    Falls back to cloud if local is unavailable.
    """

    def __init__(self, cloud_provider: BaseProvider, local_provider: BaseProvider | None = None) -> None:
        self._cloud = cloud_provider
        self._local = local_provider

    def _is_sensitive(self, request: CompletionRequest) -> bool:
        combined = request.system + " " + " ".join(
            m.get("content", "") if isinstance(m, dict) else ""
            for m in request.messages
        )
        return bool(_SENSITIVE_RE.search(combined))

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        if self._local and self._is_sensitive(request):
            try:
                logger.info("PrivacyRouter: routing to local provider (sensitive content)")
                return await self._local.complete(request)
            except Exception as exc:
                logger.warning("Local provider failed (%s) — escalating to cloud with warning", exc)

        return await self._cloud.complete(request)

    def sensitivity_check(self, text: str) -> bool:
        return bool(_SENSITIVE_RE.search(text))
