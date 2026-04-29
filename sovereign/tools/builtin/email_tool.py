"""
Email tool — compose, reply, summarize, and extract action items from emails.

No external dependencies — pure text processing with smart templates.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)

_TONE_OPENERS = {
    "formal": "Dear {recipient},",
    "professional": "Hi {recipient},",
    "casual": "Hey {recipient},",
    "friendly": "Hello {recipient},",
    "assertive": "{recipient},",
}

_TONE_CLOSERS = {
    "formal": "Yours sincerely,",
    "professional": "Best regards,",
    "casual": "Cheers,",
    "friendly": "Thanks!",
    "assertive": "Regards,",
}


def _generate_subject(body_context: str, subject: str) -> str:
    """Return a subject line — use provided subject or derive from body."""
    if subject.strip():
        return subject.strip()
    first_line = body_context.strip().splitlines()[0] if body_context.strip() else ""
    words = first_line.split()[:8]
    return " ".join(words) if words else "No Subject"


def _compose_body(body_context: str, tone: str, recipient: str) -> str:
    """Build a formatted email body from context, tone, and recipient."""
    opener = _TONE_OPENERS.get(tone, _TONE_OPENERS["professional"]).format(
        recipient=recipient or "there"
    )
    closer = _TONE_CLOSERS.get(tone, _TONE_CLOSERS["professional"])
    paragraphs = [p.strip() for p in body_context.strip().split("\n\n") if p.strip()]
    body_lines = "\n\n".join(paragraphs) if paragraphs else body_context.strip()
    return f"{opener}\n\n{body_lines}\n\n{closer}"


def _summarize_email(email_text: str) -> list[str]:
    """Return a bullet-point summary of an email text."""
    sentences = re.split(r"(?<=[.!?])\s+", email_text.strip())
    summary: list[str] = []
    for sent in sentences:
        sent = sent.strip()
        if len(sent) > 20 and not _is_greeting_or_closing(sent):
            # Trim very long sentences
            if len(sent) > 120:
                sent = sent[:117] + "..."
            summary.append(sent)
    return summary[:8] if summary else [email_text[:200]]


def _is_greeting_or_closing(sentence: str) -> bool:
    patterns = [
        r"^(dear|hi|hey|hello|greetings|good morning|good afternoon)",
        r"^(best|regards|sincerely|cheers|thanks|thank you|yours)",
        r"^(warm regards|kind regards|looking forward)",
    ]
    lower = sentence.lower()
    return any(re.match(p, lower) for p in patterns)


def _extract_action_items(email_text: str) -> list[str]:
    """Extract action items from email text using pattern matching."""
    action_patterns = [
        r"(?:please|kindly|could you|can you|would you)[^.!?\n]+[.!?]?",
        r"(?:need to|needs to|should|must|have to|has to)[^.!?\n]+[.!?]?",
        r"(?:action required|action item|to-do|todo|follow up|follow-up)[^.!?\n]+[.!?]?",
        r"(?:by|before|deadline|due)[^.!?\n]+[.!?]?",
        r"(?:send|review|update|schedule|confirm|approve|complete|submit|prepare|create)[^.!?\n]+[.!?]?",
    ]
    items: list[str] = []
    seen: set[str] = set()
    for pattern in action_patterns:
        for match in re.finditer(pattern, email_text, re.IGNORECASE):
            text = match.group(0).strip()
            key = text.lower()
            if key not in seen and len(text) > 15:
                seen.add(key)
                if len(text) > 120:
                    text = text[:117] + "..."
                items.append(text)
    return items[:10]


def _build_reply(original_text: str, reply_context: str, tone: str, recipient: str) -> str:
    """Build a reply email quoting the original."""
    opener = _TONE_OPENERS.get(tone, _TONE_OPENERS["professional"]).format(
        recipient=recipient or "there"
    )
    closer = _TONE_CLOSERS.get(tone, _TONE_CLOSERS["professional"])
    quoted = "\n".join(f"> {line}" for line in original_text.strip().splitlines())
    return (
        f"{opener}\n\n"
        f"{reply_context.strip()}\n\n"
        f"--- Original Message ---\n{quoted}\n\n"
        f"{closer}"
    )


class EmailTool(BaseTool):
    """
    Compose, reply, summarize emails and extract action items.

    No external dependencies — all processing is pure text / regex.
    """

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="email_tool",
            description=(
                "Email utility: compose drafts, build replies, summarize email text, "
                "or extract action items from an email."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["compose", "reply", "summarize", "extract_action_items"],
                        "description": (
                            "'compose' — draft a new email; "
                            "'reply' — draft a reply to an existing email; "
                            "'summarize' — bullet-point summary of email text; "
                            "'extract_action_items' — list action items from email text."
                        ),
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject (compose/reply). Auto-generated if empty.",
                    },
                    "body_context": {
                        "type": "string",
                        "description": "Main content / context for the email body (compose/reply).",
                    },
                    "email_text": {
                        "type": "string",
                        "description": "Raw email text for summarize / extract_action_items / reply.",
                    },
                    "tone": {
                        "type": "string",
                        "enum": ["formal", "professional", "casual", "friendly", "assertive"],
                        "description": "Tone of the drafted email. Default: professional.",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Recipient name or address for salutation.",
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(
        self,
        action: str,
        subject: str = "",
        body_context: str = "",
        email_text: str = "",
        tone: str = "professional",
        recipient: str = "",
        **_: Any,
    ) -> Any:
        """Execute an email operation."""
        try:
            if action == "compose":
                if not body_context:
                    return {"error": "body_context is required for compose"}
                draft_subject = _generate_subject(body_context, subject)
                draft_body = _compose_body(body_context, tone, recipient)
                return {
                    "action": "compose",
                    "subject": draft_subject,
                    "body": draft_body,
                    "tone": tone,
                    "recipient": recipient,
                    "error": None,
                }

            if action == "reply":
                if not email_text:
                    return {"error": "email_text (original email) is required for reply"}
                if not body_context:
                    return {"error": "body_context (reply content) is required for reply"}
                draft_subject = f"Re: {_generate_subject(email_text, subject)}"
                draft_body = _build_reply(email_text, body_context, tone, recipient)
                return {
                    "action": "reply",
                    "subject": draft_subject,
                    "body": draft_body,
                    "tone": tone,
                    "error": None,
                }

            if action == "summarize":
                if not email_text:
                    return {"error": "email_text is required for summarize"}
                bullets = _summarize_email(email_text)
                return {
                    "action": "summarize",
                    "summary": bullets,
                    "bullet_count": len(bullets),
                    "error": None,
                }

            if action == "extract_action_items":
                if not email_text:
                    return {"error": "email_text is required for extract_action_items"}
                items = _extract_action_items(email_text)
                return {
                    "action": "extract_action_items",
                    "action_items": items,
                    "count": len(items),
                    "error": None,
                }

            return {"error": f"Unknown action: {action}"}

        except Exception as exc:
            logger.error("EmailTool error action=%s: %s", action, exc)
            return {"result": None, "error": str(exc)}
