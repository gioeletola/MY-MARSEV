"""
Template registry — full template engine with Jinja2-style {{variable}} substitution.

Features:
- load_directory(path) — scan a directory for .txt / .md / .jinja template files
- register(template) — add/update a TemplateEntry
- get(template_id) — retrieve by ID
- render(template_id, context) — substitute {{vars}}, raise on missing required vars
- list_templates(category=None) — filtered listing
- validate(template_id, context) — return list of missing required variables
- 15 built-in templates across all TemplateCategory values

Also retains full backward-compat with the original persona TemplateDefinition registry
(register, get, all, active, by_tag, enable, disable, to_dict_list).
"""
from __future__ import annotations

import logging
import pathlib
import re
from typing import Any

from sovereign.templates.types import (
    TemplateCategory,
    TemplateDefinition,
    TemplateEntry,
    TemplateStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex for {{variable}} substitution
# ---------------------------------------------------------------------------

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def _render_content(content: str, context: dict[str, Any]) -> str:
    """Replace all {{var}} occurrences using context dict."""
    def replacer(m: re.Match) -> str:
        key = m.group(1)
        val = context.get(key)
        return str(val) if val is not None else ""
    return _VAR_RE.sub(replacer, content)


def _extract_vars(content: str) -> list[str]:
    """Return sorted unique list of variable names found in content."""
    return sorted(set(_VAR_RE.findall(content)))


# ---------------------------------------------------------------------------
# Built-in templates (15)
# ---------------------------------------------------------------------------

_BUILTIN_ENTRIES: list[dict[str, Any]] = [
    # ── SYSTEM ──────────────────────────────────────────────────────────────
    {
        "template_id": "system_prompt_base",
        "name": "Base System Prompt",
        "category": TemplateCategory.SYSTEM,
        "content": (
            "You are SOVEREIGN, an advanced AI operating system built on Claude.\n"
            "Current mode: {{mode}}\n"
            "Date: {{current_date}}\n"
            "User: {{user_name}}\n\n"
            "Your role: {{role_description}}\n\n"
            "Guidelines:\n"
            "- Be precise, structured, and actionable.\n"
            "- Escalate anything requiring human approval.\n"
            "- Always respect the user's privacy and data sovereignty.\n"
            "- Operating context: {{context_notes}}"
        ),
        "required_vars": ["mode", "current_date", "user_name", "role_description"],
        "optional_vars": ["context_notes"],
        "description": "Base system prompt injected at session start.",
        "tags": ["core", "system"],
    },
    {
        "template_id": "agent_persona",
        "name": "Agent Persona",
        "category": TemplateCategory.AGENT,
        "content": (
            "You are {{agent_name}}, a specialized AI agent.\n"
            "Specialty: {{specialty}}\n"
            "Instructions: {{instructions}}\n\n"
            "Available tools: {{tools_list}}\n"
            "Confidence threshold: {{confidence}}\n"
            "Requires human review: {{requires_review}}"
        ),
        "required_vars": ["agent_name", "specialty", "instructions"],
        "optional_vars": ["tools_list", "confidence", "requires_review"],
        "description": "Generic agent persona template.",
        "tags": ["agent", "persona"],
    },
    # ── REPORT ──────────────────────────────────────────────────────────────
    {
        "template_id": "report_header",
        "name": "Report Header",
        "category": TemplateCategory.REPORT,
        "content": (
            "# {{report_title}}\n\n"
            "**Period:** {{period_start}} — {{period_end}}\n"
            "**Generated:** {{generated_at}}\n"
            "**Author:** {{author}}\n"
            "**Status:** {{status}}\n\n"
            "---"
        ),
        "required_vars": ["report_title", "period_start", "period_end", "generated_at"],
        "optional_vars": ["author", "status"],
        "description": "Standard report header block.",
        "tags": ["report", "header"],
    },
    {
        "template_id": "weekly_summary",
        "name": "Weekly Summary",
        "category": TemplateCategory.REPORT,
        "content": (
            "# Weekly Summary — {{week_label}}\n\n"
            "## Executive Snapshot\n"
            "{{executive_summary}}\n\n"
            "## Key Wins\n"
            "{{key_wins}}\n\n"
            "## Goals Progress\n"
            "{{goals_progress}}\n\n"
            "## Action Items for Next Week\n"
            "{{action_items}}\n\n"
            "## Risks & Blockers\n"
            "{{risks_blockers}}\n\n"
            "---\n"
            "_SOVEREIGN AI OS — {{generated_at}}_"
        ),
        "required_vars": ["week_label", "executive_summary"],
        "optional_vars": [
            "key_wins", "goals_progress", "action_items",
            "risks_blockers", "generated_at",
        ],
        "description": "Full weekly summary report template.",
        "tags": ["report", "weekly"],
    },
    {
        "template_id": "okr_review",
        "name": "OKR Review",
        "category": TemplateCategory.REPORT,
        "content": (
            "# OKR Review — {{quarter}}\n\n"
            "**Objective:** {{objective}}\n\n"
            "| Key Result | Target | Actual | Status |\n"
            "|---|---|---|---|\n"
            "{{kr_table_rows}}\n\n"
            "## Commentary\n"
            "{{commentary}}\n\n"
            "## Next Quarter Focus\n"
            "{{next_quarter_focus}}"
        ),
        "required_vars": ["quarter", "objective", "kr_table_rows"],
        "optional_vars": ["commentary", "next_quarter_focus"],
        "description": "OKR quarterly review template.",
        "tags": ["report", "okr", "strategy"],
    },
    {
        "template_id": "sprint_retrospective",
        "name": "Sprint Retrospective",
        "category": TemplateCategory.REPORT,
        "content": (
            "# Sprint {{sprint_number}} Retrospective\n\n"
            "**Period:** {{sprint_start}} — {{sprint_end}}\n"
            "**Team:** {{team_name}}\n\n"
            "## What Went Well\n"
            "{{went_well}}\n\n"
            "## What Could Improve\n"
            "{{could_improve}}\n\n"
            "## Action Items\n"
            "{{action_items}}\n\n"
            "## Velocity\n"
            "Planned: {{points_planned}} pts | Completed: {{points_completed}} pts"
        ),
        "required_vars": ["sprint_number", "sprint_start", "sprint_end"],
        "optional_vars": [
            "team_name", "went_well", "could_improve",
            "action_items", "points_planned", "points_completed",
        ],
        "description": "Agile sprint retrospective report.",
        "tags": ["report", "sprint", "agile"],
    },
    {
        "template_id": "investor_update",
        "name": "Investor Update",
        "category": TemplateCategory.REPORT,
        "content": (
            "# Investor Update — {{month_year}}\n\n"
            "Dear {{investor_name}},\n\n"
            "## Highlights\n"
            "{{highlights}}\n\n"
            "## Key Metrics\n"
            "- MRR: {{mrr}}\n"
            "- Growth: {{growth_rate}}%\n"
            "- Burn Rate: {{burn_rate}}\n"
            "- Runway: {{runway_months}} months\n\n"
            "## Progress vs. Milestones\n"
            "{{milestone_progress}}\n\n"
            "## Asks\n"
            "{{asks}}\n\n"
            "Best,\n{{founder_name}}"
        ),
        "required_vars": ["month_year", "highlights", "mrr"],
        "optional_vars": [
            "investor_name", "growth_rate", "burn_rate", "runway_months",
            "milestone_progress", "asks", "founder_name",
        ],
        "description": "Monthly investor update email template.",
        "tags": ["report", "investor", "finance"],
    },
    {
        "template_id": "board_summary",
        "name": "Board Summary",
        "category": TemplateCategory.REPORT,
        "content": (
            "# Board Summary — {{meeting_date}}\n\n"
            "**Attendees:** {{attendees}}\n\n"
            "## Agenda\n"
            "{{agenda}}\n\n"
            "## Decisions Made\n"
            "{{decisions}}\n\n"
            "## Action Items\n"
            "{{action_items}}\n\n"
            "## Next Meeting\n"
            "{{next_meeting_date}}"
        ),
        "required_vars": ["meeting_date", "decisions"],
        "optional_vars": ["attendees", "agenda", "action_items", "next_meeting_date"],
        "description": "Board meeting summary document.",
        "tags": ["report", "board", "governance"],
    },
    # ── EMAIL ────────────────────────────────────────────────────────────────
    {
        "template_id": "email_signature",
        "name": "Email Signature",
        "category": TemplateCategory.EMAIL,
        "content": (
            "---\n"
            "**{{full_name}}**\n"
            "{{title}} | {{company}}\n"
            "{{email}} | {{phone}}\n"
            "{{website}}"
        ),
        "required_vars": ["full_name"],
        "optional_vars": ["title", "company", "email", "phone", "website"],
        "description": "Professional email signature block.",
        "tags": ["email", "signature"],
    },
    # ── DECISION ─────────────────────────────────────────────────────────────
    {
        "template_id": "decision_brief",
        "name": "Decision Brief",
        "category": TemplateCategory.DECISION,
        "content": (
            "# Decision Brief\n\n"
            "**Title:** {{decision_title}}\n"
            "**Date:** {{decision_date}}\n"
            "**Owner:** {{decision_owner}}\n"
            "**Deadline:** {{deadline}}\n\n"
            "## Context\n"
            "{{context}}\n\n"
            "## Options Considered\n"
            "{{options}}\n\n"
            "## Recommendation\n"
            "{{recommendation}}\n\n"
            "## Rationale\n"
            "{{rationale}}\n\n"
            "## Risks\n"
            "{{risks}}\n\n"
            "## Next Steps\n"
            "{{next_steps}}"
        ),
        "required_vars": ["decision_title", "context", "recommendation"],
        "optional_vars": [
            "decision_date", "decision_owner", "deadline",
            "options", "rationale", "risks", "next_steps",
        ],
        "description": "Structured decision brief for high-stakes choices.",
        "tags": ["decision", "strategy"],
    },
    {
        "template_id": "task_decomposition",
        "name": "Task Decomposition",
        "category": TemplateCategory.DECISION,
        "content": (
            "# Task: {{task_title}}\n\n"
            "**Goal:** {{goal}}\n"
            "**Assigned to:** {{assignee}}\n"
            "**Due:** {{due_date}}\n\n"
            "## Sub-tasks\n"
            "{{subtasks}}\n\n"
            "## Dependencies\n"
            "{{dependencies}}\n\n"
            "## Success Criteria\n"
            "{{success_criteria}}"
        ),
        "required_vars": ["task_title", "goal", "subtasks"],
        "optional_vars": ["assignee", "due_date", "dependencies", "success_criteria"],
        "description": "Structured task decomposition template.",
        "tags": ["task", "planning"],
    },
    # ── NOTIFICATION ─────────────────────────────────────────────────────────
    {
        "template_id": "error_notification",
        "name": "Error Notification",
        "category": TemplateCategory.NOTIFICATION,
        "content": (
            "ALERT: {{alert_level}}\n\n"
            "Component: {{component}}\n"
            "Error: {{error_message}}\n"
            "Time: {{timestamp}}\n"
            "Session: {{session_id}}\n\n"
            "Context:\n{{error_context}}\n\n"
            "Suggested Action: {{suggested_action}}"
        ),
        "required_vars": ["alert_level", "error_message", "timestamp"],
        "optional_vars": [
            "component", "session_id", "error_context", "suggested_action",
        ],
        "description": "System error notification template.",
        "tags": ["notification", "error", "alert"],
    },
    {
        "template_id": "health_check_summary",
        "name": "Health Check Summary",
        "category": TemplateCategory.NOTIFICATION,
        "content": (
            "# System Health Check — {{timestamp}}\n\n"
            "**Overall Status:** {{overall_status}}\n\n"
            "| Component | Status | Latency | Notes |\n"
            "|---|---|---|---|\n"
            "{{component_rows}}\n\n"
            "**Active Alerts:** {{alert_count}}\n"
            "{{alerts_detail}}"
        ),
        "required_vars": ["timestamp", "overall_status"],
        "optional_vars": ["component_rows", "alert_count", "alerts_detail"],
        "description": "System health check summary notification.",
        "tags": ["notification", "health", "monitoring"],
    },
    {
        "template_id": "crisis_comms",
        "name": "Crisis Communication",
        "category": TemplateCategory.NOTIFICATION,
        "content": (
            "INCIDENT REPORT — {{severity}}\n\n"
            "**Incident:** {{incident_title}}\n"
            "**Started:** {{incident_start}}\n"
            "**Status:** {{incident_status}}\n\n"
            "## What Happened\n"
            "{{what_happened}}\n\n"
            "## Impact\n"
            "{{impact}}\n\n"
            "## Current Actions\n"
            "{{current_actions}}\n\n"
            "## Next Update\n"
            "{{next_update_time}}"
        ),
        "required_vars": ["severity", "incident_title", "what_happened"],
        "optional_vars": [
            "incident_start", "incident_status", "impact",
            "current_actions", "next_update_time",
        ],
        "description": "Crisis communications template for incidents.",
        "tags": ["notification", "crisis", "incident"],
    },
    # ── ONBOARDING ───────────────────────────────────────────────────────────
    {
        "template_id": "user_onboarding",
        "name": "User Onboarding",
        "category": TemplateCategory.ONBOARDING,
        "content": (
            "# Welcome to SOVEREIGN, {{user_name}}!\n\n"
            "Your AI operating system is ready.\n\n"
            "## Your Setup\n"
            "- **Tier:** {{tier}}\n"
            "- **Mode:** {{default_mode}}\n"
            "- **Agents active:** {{agent_count}}\n\n"
            "## Getting Started\n"
            "1. Run `python main.py run --interactive` to start a session.\n"
            "2. Try `python main.py agent list` to see your agents.\n"
            "3. Visit the web UI at {{web_ui_url}}.\n\n"
            "## Your First Steps\n"
            "{{suggested_first_steps}}\n\n"
            "Questions? Run `python main.py --help` or ask your CEO agent."
        ),
        "required_vars": ["user_name"],
        "optional_vars": [
            "tier", "default_mode", "agent_count",
            "web_ui_url", "suggested_first_steps",
        ],
        "description": "Welcome message for new SOVEREIGN users.",
        "tags": ["onboarding", "welcome"],
    },
]

# ---------------------------------------------------------------------------
# Legacy built-in persona templates (preserved for backward compatibility)
# ---------------------------------------------------------------------------

_BUILTIN_PERSONAS: list[dict[str, Any]] = [
    {
        "template_id": "architect",
        "name": "Architect",
        "description": "Systems architect focused on design, trade-offs, scalability, and technical decision records.",
        "system_prompt": (
            "You are a senior systems architect. Your role is to design systems, evaluate trade-offs, "
            "identify scalability risks, and produce clear technical decision records (TDRs). "
            "Think in layers: data, logic, API, infra. Always consider: consistency, availability, "
            "partition-tolerance. Prefer diagrams and structured output. Flag assumptions explicitly."
        ),
        "preferred_model": "claude-opus-4-7",
        "preferred_tools": ["code_exec", "memory_tool", "web_search"],
        "temperature_hint": 0.3,
        "tags": ["technical", "architecture", "design"],
        "output_format": "markdown",
    },
    {
        "template_id": "assistant",
        "name": "General Assistant",
        "description": "Balanced general-purpose assistant for diverse tasks.",
        "system_prompt": (
            "You are a highly capable general assistant. Be concise, accurate, and helpful. "
            "Adapt your tone to the context. Ask for clarification when the request is ambiguous. "
            "Prefer structured output when the content is complex."
        ),
        "preferred_model": "claude-sonnet-4-6",
        "preferred_tools": ["memory_tool", "web_search"],
        "temperature_hint": 0.7,
        "tags": ["general", "assistant"],
        "output_format": "markdown",
    },
    {
        "template_id": "code-reviewer",
        "name": "Code Reviewer",
        "description": "Senior engineer performing structured code reviews: correctness, security, maintainability.",
        "system_prompt": (
            "You are a senior software engineer performing a code review. "
            "Check for: correctness, edge cases, security vulnerabilities (OWASP top 10), "
            "performance, readability, and test coverage. "
            "Format: Summary → Critical Issues → Minor Issues → Suggestions → Verdict. "
            "Be specific: reference line numbers and suggest concrete fixes."
        ),
        "preferred_model": "claude-sonnet-4-6",
        "preferred_tools": ["code_exec", "file_ops"],
        "temperature_hint": 0.2,
        "tags": ["code", "review", "security", "technical"],
        "output_format": "markdown",
    },
    {
        "template_id": "data-analyst",
        "name": "Data Analyst",
        "description": "Quantitative analyst: data interpretation, statistics, visualization recommendations.",
        "system_prompt": (
            "You are a quantitative data analyst. Interpret data rigorously: describe distributions, "
            "identify trends, flag outliers and biases, compute relevant statistics, and recommend "
            "visualization types. Always note sample size, confidence intervals, and limitations. "
            "Output: summary → analysis → key findings → visualization recommendation → caveats."
        ),
        "preferred_model": "claude-sonnet-4-6",
        "preferred_tools": ["code_exec", "memory_tool"],
        "temperature_hint": 0.2,
        "tags": ["data", "analysis", "statistics", "technical"],
        "output_format": "markdown",
    },
    {
        "template_id": "summarizer",
        "name": "Summarizer",
        "description": "Produces concise, structured summaries preserving key information and removing noise.",
        "system_prompt": (
            "You are an expert summarizer. Condense content to its essential information. "
            "Use progressive summarization: TL;DR → key points → detail. "
            "Preserve: facts, decisions, action items, key quotes. Remove: filler, repetition, obvious context. "
            "Match output length to input complexity."
        ),
        "preferred_model": "claude-haiku-4-5-20251001",
        "preferred_tools": [],
        "temperature_hint": 0.3,
        "tags": ["writing", "summarize", "productivity"],
        "output_format": "markdown",
    },
    {
        "template_id": "writer",
        "name": "Writer",
        "description": "Professional writer for articles, reports, narratives, and polished long-form content.",
        "system_prompt": (
            "You are a professional writer with strong command of structure, style, and clarity. "
            "Match tone to context: technical, journalistic, narrative, or persuasive. "
            "Produce well-organized content with clear sections, strong openings, and actionable conclusions. "
            "Always ask: is this sentence necessary? Is this the right word?"
        ),
        "preferred_model": "claude-sonnet-4-6",
        "preferred_tools": ["memory_tool"],
        "temperature_hint": 0.8,
        "tags": ["writing", "content", "creative"],
        "output_format": "markdown",
    },
    {
        "template_id": "fact-checker",
        "name": "Fact Checker",
        "description": "Verifies claims, identifies unsupported assertions, and flags potential misinformation.",
        "system_prompt": (
            "You are a rigorous fact-checker. For each claim: identify the assertion, "
            "assess verifiability, note the evidence standard required, flag what cannot be verified, "
            "and suggest authoritative sources. "
            "Output: Claim → Status (verified/unverified/false/needs-source) → Evidence → Note."
        ),
        "preferred_model": "claude-sonnet-4-6",
        "preferred_tools": ["web_search", "memory_tool"],
        "temperature_hint": 0.1,
        "tags": ["research", "verification", "analysis"],
        "output_format": "markdown",
    },
    {
        "template_id": "translator",
        "name": "Translator",
        "description": "Professional translator preserving meaning, tone, and cultural nuance.",
        "system_prompt": (
            "You are a professional translator. Preserve: meaning, tone, register, idioms adapted to target culture. "
            "Avoid literal translation when idiomatic translation is better. "
            "Flag ambiguities or culturally-specific content. "
            "Output only the translated text unless asked for notes."
        ),
        "preferred_model": "claude-sonnet-4-6",
        "preferred_tools": [],
        "temperature_hint": 0.4,
        "tags": ["language", "translation"],
        "output_format": "plain",
    },
    {
        "template_id": "debugger",
        "name": "Debugger",
        "description": "Systematic debugger: root cause analysis, reproduction steps, fix proposals.",
        "system_prompt": (
            "You are a senior debugging engineer. Approach bugs systematically: "
            "1) Reproduce the issue. 2) Isolate the cause. 3) Form hypothesis. 4) Test hypothesis. "
            "5) Propose fix. 6) Verify fix doesn't introduce regressions. "
            "Be methodical. Show your reasoning. Prefer minimal, targeted fixes."
        ),
        "preferred_model": "claude-sonnet-4-6",
        "preferred_tools": ["code_exec", "file_ops"],
        "temperature_hint": 0.2,
        "tags": ["code", "debug", "technical"],
        "output_format": "markdown",
    },
    {
        "template_id": "deep-researcher",
        "name": "Deep Researcher",
        "description": "Multi-step deep researcher: comprehensive literature review, source triangulation, structured briefs.",
        "system_prompt": (
            "You are a rigorous deep researcher. Process: "
            "1) Define research question. 2) Identify source types. 3) Search broadly. "
            "4) Synthesize across sources. 5) Note consensus vs controversy. "
            "6) Produce structured research brief with confidence levels. "
            "Always cite. Always note limitations. Never extrapolate beyond evidence."
        ),
        "preferred_model": "claude-opus-4-7",
        "preferred_tools": ["web_search", "memory_tool"],
        "temperature_hint": 0.3,
        "tags": ["research", "analysis", "knowledge"],
        "output_format": "markdown",
    },
    {
        "template_id": "tutor",
        "name": "Tutor",
        "description": "Patient, adaptive tutor for learning complex topics through explanation and questioning.",
        "system_prompt": (
            "You are an expert tutor with deep pedagogical skill. Adapt to the learner's level. "
            "Use: analogies, examples, Socratic questions, progressive complexity. "
            "Check comprehension. Identify and address misconceptions. "
            "Celebrate correct reasoning. Never just give answers — help them understand."
        ),
        "preferred_model": "claude-sonnet-4-6",
        "preferred_tools": ["memory_tool"],
        "temperature_hint": 0.6,
        "tags": ["learning", "education", "tutoring"],
        "output_format": "markdown",
    },
    {
        "template_id": "note-taker",
        "name": "Note Taker",
        "description": "Captures and structures information into clean, retrievable notes.",
        "system_prompt": (
            "You are a precise note-taker. Capture key information clearly and structurally. "
            "Use: bullet points, headers, tags. Preserve: decisions, facts, open questions, action items. "
            "Be atomic: one idea per note. Always add: date context, source reference, relevance tag."
        ),
        "preferred_model": "claude-haiku-4-5-20251001",
        "preferred_tools": ["memory_tool"],
        "temperature_hint": 0.3,
        "tags": ["productivity", "notes", "second-brain"],
        "output_format": "markdown",
    },
]


# ---------------------------------------------------------------------------
# Main registry
# ---------------------------------------------------------------------------

class TemplateRegistry:
    """
    Full template engine and persona registry.

    Maintains two independent stores:
      _entries  — TemplateEntry objects for content rendering ({{var}} substitution)
      _personas — TemplateDefinition objects for agent persona presets (legacy)
    """

    def __init__(self) -> None:
        self._entries: dict[str, TemplateEntry] = {}
        self._personas: dict[str, TemplateDefinition] = {}
        self._load_builtin_entries()
        self._load_builtin_personas()

    # ------------------------------------------------------------------
    # TemplateEntry API (new)
    # ------------------------------------------------------------------

    def _load_builtin_entries(self) -> None:
        for raw in _BUILTIN_ENTRIES:
            entry = TemplateEntry(
                template_id=raw["template_id"],
                name=raw["name"],
                category=raw["category"],
                content=raw["content"],
                required_vars=raw.get("required_vars", []),
                optional_vars=raw.get("optional_vars", []),
                description=raw.get("description", ""),
                tags=raw.get("tags", []),
            )
            self._entries[entry.template_id] = entry
        logger.info("TemplateRegistry: loaded %d built-in content templates", len(self._entries))

    def load_directory(self, path: str | pathlib.Path) -> int:
        """
        Load all .txt, .md, and .jinja files from a directory as TemplateEntry objects.

        File stem becomes the template_id. Variables are auto-detected.
        Returns the count of templates loaded.
        """
        base = pathlib.Path(path)
        if not base.is_dir():
            logger.warning("TemplateRegistry.load_directory: %s is not a directory", path)
            return 0

        loaded = 0
        for ext in ("*.txt", "*.md", "*.jinja", "*.j2"):
            for file in base.glob(ext):
                try:
                    content = file.read_text(encoding="utf-8")
                    detected_vars = _extract_vars(content)
                    entry = TemplateEntry(
                        template_id=file.stem,
                        name=file.stem.replace("_", " ").replace("-", " ").title(),
                        category=TemplateCategory.SYSTEM,
                        content=content,
                        required_vars=detected_vars,
                        optional_vars=[],
                        description=f"Loaded from {file.name}",
                    )
                    self._entries[entry.template_id] = entry
                    loaded += 1
                except OSError as exc:
                    logger.warning("TemplateRegistry: could not load %s: %s", file, exc)

        logger.info("TemplateRegistry.load_directory: loaded %d templates from %s", loaded, path)
        return loaded

    def register(self, template: "TemplateEntry | TemplateDefinition") -> None:
        """Register a TemplateEntry (new) or TemplateDefinition (legacy)."""
        if isinstance(template, TemplateEntry):
            self._entries[template.template_id] = template
        else:
            self._personas[template.template_id] = template

    def get(self, template_id: str) -> "TemplateEntry | TemplateDefinition | None":
        """Retrieve a template by ID — checks entries first, then personas."""
        return self._entries.get(template_id) or self._personas.get(template_id)

    def get_entry(self, template_id: str) -> TemplateEntry | None:
        return self._entries.get(template_id)

    def render(self, template_id: str, context: dict[str, Any]) -> str:
        """
        Render a TemplateEntry with the given context.

        Raises KeyError if template not found.
        Raises ValueError if any required variable is missing from context.
        """
        entry = self._entries.get(template_id)
        if entry is None:
            raise KeyError(f"Template '{template_id}' not found")

        missing = self.validate(template_id, context)
        if missing:
            raise ValueError(
                f"Template '{template_id}' missing required variables: {missing}"
            )

        return _render_content(entry.content, context)

    def render_safe(self, template_id: str, context: dict[str, Any]) -> str:
        """
        Like render() but replaces missing variables with empty string instead of raising.
        """
        entry = self._entries.get(template_id)
        if entry is None:
            raise KeyError(f"Template '{template_id}' not found")
        return _render_content(entry.content, context)

    def list_templates(
        self,
        category: "TemplateCategory | str | None" = None,
    ) -> list[TemplateEntry]:
        """
        Return a list of TemplateEntry objects, optionally filtered by category.
        """
        entries = list(self._entries.values())
        if category is None:
            return entries
        cat_str = category.value if isinstance(category, TemplateCategory) else str(category)
        return [e for e in entries if e.category.value == cat_str]

    def validate(self, template_id: str, context: dict[str, Any]) -> list[str]:
        """
        Return the list of required variables missing from context.

        Empty list means the context is valid for rendering.
        """
        entry = self._entries.get(template_id)
        if entry is None:
            return [f"<template '{template_id}' not found>"]
        return [v for v in entry.required_vars if v not in context]

    # ------------------------------------------------------------------
    # Legacy TemplateDefinition (persona) API — full backward compat
    # ------------------------------------------------------------------

    def _load_builtin_personas(self) -> None:
        for raw in _BUILTIN_PERSONAS:
            t = TemplateDefinition(
                template_id=raw["template_id"],
                name=raw["name"],
                description=raw["description"],
                system_prompt=raw.get("system_prompt", ""),
                preferred_model=raw.get("preferred_model", "claude-sonnet-4-6"),
                preferred_tools=raw.get("preferred_tools", []),
                temperature_hint=raw.get("temperature_hint", 0.7),
                tags=raw.get("tags", []),
                output_format=raw.get("output_format", "markdown"),
            )
            self._personas[t.template_id] = t
        logger.info("TemplateRegistry: loaded %d persona templates", len(self._personas))

    def all(self) -> list[TemplateDefinition]:
        return list(self._personas.values())

    def active(self) -> list[TemplateDefinition]:
        return [t for t in self._personas.values() if t.enabled]

    def by_tag(self, tag: str) -> list[TemplateDefinition]:
        return [t for t in self._personas.values() if tag in t.tags]

    def enable(self, template_id: str) -> bool:
        t = self._personas.get(template_id)
        if t:
            t.enabled = True
            t.status = TemplateStatus.ACTIVE
            return True
        return False

    def disable(self, template_id: str) -> bool:
        t = self._personas.get(template_id)
        if t:
            t.enabled = False
            t.status = TemplateStatus.DISABLED
            return True
        return False

    def to_dict_list(self) -> list[dict]:
        return [
            {
                "template_id": t.template_id,
                "name": t.name,
                "description": t.description,
                "version": t.version,
                "status": t.status.value,
                "enabled": t.enabled,
                "preferred_model": t.preferred_model,
                "tags": t.tags,
                "output_format": t.output_format,
            }
            for t in self._personas.values()
        ]


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_registry: TemplateRegistry | None = None


def get_template_registry() -> TemplateRegistry:
    global _registry
    if _registry is None:
        _registry = TemplateRegistry()
    return _registry
