"""
Dedicated Cybersecurity Agents — Section 16 of the SOVEREIGN AI OS spec.

Five dedicated security agents:
- Security Sentinel
- Permission Auditor
- Data Leak Monitor
- Incident Response Agent
- Backup Integrity Agent
"""
from __future__ import annotations

import logging

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent

logger = logging.getLogger(__name__)


def _w(agent_id, specialty, instructions, tools=None, model="claude-sonnet-4-6",
        requires_review=True, confidence=0.88):
    _tools = tools or ["memory_tool"]
    _model = model
    _review = requires_review
    _conf = confidence

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            if not task.tools_allowed:
                task.tools_allowed = list(_tools)
            prompt = (
                f"You are the {specialty} of the SOVEREIGN AI OS Security Layer.\n\n"
                f"{instructions}\n\n"
                f"Security Task:\n{task.objective}\n\n"
                "Respond with specific findings, severity ratings, and remediation steps. "
                "Flag anything requiring immediate human attention."
            )
            result, history = await self._call_with_tools(
                [{"role": "user", "content": prompt}], ctx, task, max_tokens=2048
            )
            out = self._make_output(task=task, ctx=ctx, result=result,
                                    status=OutputStatus.SUCCESS, confidence=_conf,
                                    data={"specialty": specialty, "tool_turns": len(history)})
            out.requires_human_review = _review
            return out
        except Exception as exc:
            logger.error("SecurityAgent %s failed: %s", agent_id, exc)
            return StructuredOutput.failure(ctx.session_id, agent_id, task.task_id, str(exc))

    return type(f"{agent_id.replace('-','_').title()}Agent",
                (BaseAgent,), {"agent_id": agent_id, "model": _model, "run": run})


SecuritySentinelAgent = _w(
    "security_sentinel",
    "Security Sentinel",
    (
        "Continuous security monitoring for the SOVEREIGN AI OS. "
        "Responsibilities:\n"
        "1. Monitor all agent actions for policy violations\n"
        "2. Detect anomalous patterns: unusual tool use, unexpected data access, "
        "   off-hours activity, privilege escalation attempts\n"
        "3. Run regular security posture assessments\n"
        "4. Enforce security policies across all system layers\n"
        "5. Generate hourly security status reports\n\n"
        "Output format: severity (CRITICAL/HIGH/MEDIUM/LOW), finding, affected component, "
        "immediate action required."
    ),
    tools=["memory_tool"],
    model="claude-opus-4-6",
    confidence=0.92,
)

PermissionAuditorAgent = _w(
    "permission_auditor",
    "Permission Auditor",
    (
        "Audit and enforce permission boundaries across the entire agent system. "
        "Responsibilities:\n"
        "1. Review agent action classes vs. constitutional limits\n"
        "2. Detect permission creep: agents attempting actions beyond their class\n"
        "3. Audit tool access: which agents use which tools\n"
        "4. Verify approval gate is invoked for all EXECUTE-class actions\n"
        "5. Generate monthly permission matrix report\n"
        "6. Recommend permission hardening\n\n"
        "Flag any permission violation immediately. "
        "Zero tolerance for unauthorized privilege escalation."
    ),
    tools=["memory_tool"],
    confidence=0.90,
)

DataLeakMonitorAgent = _w(
    "data_leak_monitor",
    "Data Leak Monitor",
    (
        "Monitor for data leakage across all system outputs and communications. "
        "Responsibilities:\n"
        "1. Scan all agent outputs for PII, financial data, credentials, secrets\n"
        "2. Detect unauthorized data exfiltration patterns\n"
        "3. Monitor cross-domain data flow (e.g., personal data reaching business agents)\n"
        "4. Alert on any sensitive data appearing in logs, outputs, or external calls\n"
        "5. Maintain data flow audit trail\n"
        "6. Generate weekly data hygiene report\n\n"
        "Categories to monitor: passwords, API keys, SSN, financial account numbers, "
        "health records, private communications, location data."
    ),
    tools=["memory_tool"],
    confidence=0.91,
)

IncidentResponseAgent = _w(
    "incident_response",
    "Incident Response Agent",
    (
        "Lead incident response for all security events. "
        "Responsibilities:\n"
        "1. Triage incoming security incidents by severity and impact\n"
        "2. Execute incident response playbooks:\n"
        "   - Containment: isolate affected components\n"
        "   - Eradication: remove threat\n"
        "   - Recovery: restore normal operation\n"
        "   - Post-incident review: document and learn\n"
        "3. Coordinate with Security Sentinel and Permission Auditor\n"
        "4. Escalate CRITICAL incidents immediately for human review\n"
        "5. Maintain incident register and resolution times\n\n"
        "Response SLAs: CRITICAL < 5 min, HIGH < 1 hour, MEDIUM < 24 hours."
    ),
    tools=["memory_tool"],
    model="claude-opus-4-6",
    confidence=0.91,
    requires_review=True,
)

BackupIntegrityAgent = _w(
    "backup_integrity",
    "Backup Integrity Agent",
    (
        "Verify and maintain the integrity of all system backups. "
        "Responsibilities:\n"
        "1. Verify backup completeness: memory domains, ledgers, registries, configs\n"
        "2. Test backup restoration procedures periodically\n"
        "3. Monitor backup recency: flag stale backups\n"
        "4. Ensure offline backup copies exist for survival-critical data\n"
        "5. Maintain backup inventory and access procedures\n"
        "6. Generate weekly backup health report\n\n"
        "Critical backup targets: identity memory, financial data, decision ledger, "
        "offline queue, sovereign exit data, legacy layer."
    ),
    tools=["memory_tool", "file_ops"],
    confidence=0.89,
)

SECURITY_AGENTS: list[type[BaseAgent]] = [
    SecuritySentinelAgent,
    PermissionAuditorAgent,
    DataLeakMonitorAgent,
    IncidentResponseAgent,
    BackupIntegrityAgent,
]
