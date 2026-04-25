"""
Offline / Local Mode agents — Section 22 of the SOVEREIGN AI OS spec.

Four dedicated offline agents:
- Offline Sync Agent
- Knowledge Pack Agent
- Emergency Protocol Agent
- Survival Library Agent
"""
from __future__ import annotations

import logging

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent

logger = logging.getLogger(__name__)


def _w(agent_id, specialty, instructions, tools=None,
        model="claude-haiku-4-5-20251001", requires_review=False, confidence=0.85):
    """Offline agents default to Haiku (cheapest, runs locally)."""
    _tools = tools or ["memory_tool", "file_ops"]
    _model = model
    _review = requires_review
    _conf = confidence

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            if not task.tools_allowed:
                task.tools_allowed = list(_tools)
            prompt = (
                f"You are the {specialty} of the SOVEREIGN AI OS — Offline Mode.\n\n"
                f"{instructions}\n\n"
                f"Task:\n{task.objective}\n\n"
                "Operate with minimal external dependencies. "
                "Prioritize local resources, cached data, and offline-capable operations."
            )
            result, history = await self._call_with_tools(
                [{"role": "user", "content": prompt}], ctx, task, max_tokens=1500
            )
            out = self._make_output(task=task, ctx=ctx, result=result,
                                    status=OutputStatus.SUCCESS, confidence=_conf,
                                    data={"specialty": specialty, "tool_turns": len(history)})
            out.requires_human_review = _review
            return out
        except Exception as exc:
            logger.error("OfflineAgent %s failed: %s", agent_id, exc)
            return StructuredOutput.failure(ctx.session_id, agent_id, task.task_id, str(exc))

    return type(f"{agent_id.replace('-','_').title()}Agent",
                (BaseAgent,), {"agent_id": agent_id, "model": _model, "run": run})


OfflineSyncAgent = _w(
    "offline_sync",
    "Offline Sync Agent",
    (
        "Manage the transition between offline and online modes. "
        "Responsibilities:\n"
        "1. Detect connectivity restoration after offline period\n"
        "2. Inventory the deferred operations queue\n"
        "3. Prioritize sync order: critical data first, then operational, then archival\n"
        "4. Execute sync operations safely (conflict detection, idempotency)\n"
        "5. Verify sync completion and data integrity\n"
        "6. Report sync results: what synced, what failed, what needs review\n\n"
        "Conflict resolution policy: local changes win for personal data, "
        "server wins for shared/business data unless explicitly overridden."
    ),
    tools=["memory_tool", "file_ops"],
)

KnowledgePackAgent = _w(
    "knowledge_pack",
    "Knowledge Pack Agent",
    (
        "Maintain and serve offline knowledge packs — curated bundles of knowledge "
        "that remain accessible without internet connectivity. "
        "Responsibilities:\n"
        "1. Curate domain knowledge packs: business, personal, finance, health, survival\n"
        "2. Keep packs updated when online (incremental updates)\n"
        "3. Serve knowledge queries from local cache when offline\n"
        "4. Compress and optimize packs for minimal storage\n"
        "5. Track pack freshness and flag stale content\n"
        "6. Priority packs: emergency procedures, medical basics, legal rights, "
        "   local maps, key contacts, financial account info."
    ),
    tools=["memory_tool", "file_ops"],
)

EmergencyProtocolAgent = _w(
    "emergency_protocol",
    "Emergency Protocol Agent",
    (
        "Maintain and execute emergency protocols for crisis situations. "
        "Responsibilities:\n"
        "1. Maintain emergency protocol library (always offline-available)\n"
        "2. Classify emergency type: medical, security, financial, natural disaster, tech failure\n"
        "3. Serve step-by-step protocol for identified emergency\n"
        "4. Surface emergency contacts for the situation\n"
        "5. Activate appropriate offline resources\n"
        "6. Log emergency activation for post-incident review\n\n"
        "Protocol library includes:\n"
        "- Medical: first aid, emergency contact numbers, blood type, allergies\n"
        "- Security: lockdown, evacuation, data wipe procedures\n"
        "- Financial: emergency access, backup payment methods\n"
        "- Tech failure: manual fallbacks, paper backups, recovery keys\n"
        "- Natural disaster: shelter, communication, resource protocols"
    ),
    tools=["memory_tool", "file_ops"],
    requires_review=True,
)

SurvivalLibraryAgent = _w(
    "survival_library",
    "Survival Library Agent",
    (
        "Maintain and serve the offline survival library — comprehensive knowledge "
        "for operating when all normal systems fail. "
        "Library contents:\n"
        "1. Emergency medical procedures (informational — not medical advice)\n"
        "2. Water/food procurement and purification basics\n"
        "3. Communication methods when internet is down\n"
        "4. Physical security and shelter basics\n"
        "5. Financial backup: cash, crypto access, barter knowledge\n"
        "6. Identity recovery: document reconstruction steps\n"
        "7. Evacuation routes and rally points\n"
        "8. Power alternatives: solar, battery, manual\n"
        "9. Community coordination: who to contact, trust protocols\n"
        "10. Psychological resilience under extreme stress\n\n"
        "Always available offline. Updated quarterly. Never depends on external APIs."
    ),
    tools=["memory_tool", "file_ops"],
)

OFFLINE_AGENTS: list[type[BaseAgent]] = [
    OfflineSyncAgent,
    KnowledgePackAgent,
    EmergencyProtocolAgent,
    SurvivalLibraryAgent,
]
