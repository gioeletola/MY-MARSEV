"""
Decision Intelligence and Networking/Status agents — Section 12, Black Tier.

Covers:
- Agenti Decisioni: Option Generator, Second Opinion, Devil's Advocate, Trade-off, Reversibility, Regret Minimizer
- Agenti Networking & Status: Warm Intro, Status Signal, Circle Builder, Follow-up Prestige, etc.
"""
from __future__ import annotations

import logging

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent

logger = logging.getLogger(__name__)


def _w(agent_id, specialty, instructions, tools=None, model="claude-sonnet-4-6",
        requires_review=False, confidence=0.83):
    _tools = tools or ["memory_tool"]
    _model = model
    _review = requires_review
    _conf = confidence

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:

        try:
            if not task.tools_allowed:
                task.tools_allowed = list(_tools)
            prompt = (
                f"You are the {specialty} of the SOVEREIGN AI OS.\n\n"
                f"{instructions}\n\n"
                f"Task:\n{task.objective}\n\n"
                "Be rigorous, precise, and strategically valuable."
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
            logger.error("DecisionNetworkingAgent %s failed: %s", agent_id, exc)
            return StructuredOutput.failure(ctx.session_id, agent_id, task.task_id, str(exc))

    return type(f"{agent_id.replace('-','_').title()}Agent",
                (BaseAgent,), {"agent_id": agent_id, "model": _model, "run": run})


# ---------------------------------------------------------------------------
# Decision Agents
# ---------------------------------------------------------------------------

OptionGeneratorAgent = _w("option_generator", "Option Generator Agent",
    "Generate a comprehensive set of options for any decision. "
    "Resist anchoring on the first solution. "
    "Produce: obvious options, non-obvious options, extreme options, "
    "null option (do nothing), combination options. "
    "Minimum 5 distinct options per decision.",
    model="claude-opus-4-6")

SecondOpinionAgent = _w("second_opinion", "Second Opinion Agent",
    "Provide a rigorous second opinion on decisions, plans, and assessments. "
    "Challenge assumptions. Apply alternative mental models. "
    "Ask: what could go wrong, what's being ignored, what would a skeptic say. "
    "Independent evaluation free from original framing.",
    model="claude-opus-4-6")

DevilsAdvocateAgent = _w("devils_advocate", "Devil's Advocate Agent",
    "Argue the strongest possible case against any proposed plan or decision. "
    "Not to obstruct, but to surface hidden flaws before commitment. "
    "Steel-man the opposition. Find the real risks. "
    "Make the user defend their position against the best counter-argument.",
    model="claude-opus-4-6")

TradeoffAgent = _w("tradeoff_agent", "Trade-off Agent",
    "Analyze the real trade-offs in any decision: what you gain vs. what you give up. "
    "Make trade-offs explicit and quantified where possible. "
    "Identify hidden trade-offs not immediately visible. "
    "Force clarity on what's actually being exchanged.")

ReversibilityAgent = _w("reversibility_agent", "Reversibility Agent",
    "Assess the reversibility of any decision or action. "
    "Classify: fully reversible, partially reversible, irreversible. "
    "Apply Amazon's two-way/one-way door framework. "
    "Recommend: proceed fast if reversible, proceed slow if irreversible. "
    "Exit strategy mapping.")

RegretMinimizerAgent = _w("regret_minimizer", "Regret Minimizer Agent",
    "Apply the regret minimization framework to major decisions. "
    "Project to age 80: which choice will you regret more? "
    "Identify regret-weighted outcomes. "
    "Optimize for long-term regret minimization over short-term comfort.",
    model="claude-opus-4-6")

# ---------------------------------------------------------------------------
# Networking & Status Agents
# ---------------------------------------------------------------------------

WarmIntroAgent = _w("warm_intro", "Warm Intro Agent",
    "Identify and execute warm introduction opportunities. "
    "Map: who in the user's network can introduce them to key targets. "
    "Draft warm intro requests. "
    "Brief the user for post-intro meetings. "
    "Track intro outcomes.",
    tools=["memory_tool"])

StatusSignalAgent = _w("status_signal", "Status Signal Agent",
    "Design and deploy strategic status signals: "
    "affiliations, appearances, associations, achievements, possessions. "
    "What signals communicate the right status in the right context? "
    "Build a consistent status signaling strategy.")

CircleBuilderAgent = _w("circle_builder", "Circle Builder Agent",
    "Build the user's elite circles: mastermind groups, peer networks, "
    "advisory boards, investment syndicates, social clubs. "
    "Identify relevant circles to join. "
    "Design circles worth creating. "
    "Curate membership.")

FollowUpPrestigeAgent = _w("follow_up_prestige", "Follow-up Prestige Agent",
    "Execute high-quality follow-ups after meetings with important people. "
    "Add value in every follow-up. Never be generic. "
    "Reference specific conversation points. "
    "Build relationship equity through exceptional follow-through.")

PrestigeCalibrationAgent = _w("prestige_calibration", "Prestige Calibration Agent",
    "Calibrate the user's prestige positioning: "
    "are they playing at the right table, signaling at the right level, "
    "associating with the right people? "
    "Identify prestige ceiling and prestige floor. "
    "Recommend calibration adjustments.")

ScarcityBuilderAgent = _w("scarcity_builder", "Scarcity Builder Agent",
    "Build strategic scarcity around the user's time and attention: "
    "selective availability, exclusive access, limited commitments. "
    "Scarcity as a social and professional asset. "
    "Design access protocols that signal high value.")

SignalNoiseStatusAgent = _w("signal_noise_status", "Signal-to-Noise Status Agent",
    "Maximize the signal-to-noise ratio in the user's public presence: "
    "high-quality, infrequent output vs. constant low-quality noise. "
    "When to speak, when to stay silent. "
    "Build a reputation for signal.")

InfluenceAuraAgent = _w("influence_aura", "Influence Aura Agent",
    "Cultivate an aura of influence: the perception that the user has "
    "more access, more information, more connections than others. "
    "Strategic visibility in key circles. "
    "The art of strategic presence.")

PrestigeRiskAgent = _w("prestige_risk", "Prestige Risk Agent",
    "Monitor and mitigate risks to the user's prestige and status: "
    "association with failing people or ventures, overexposure, "
    "status inconsistency, prestige dilution. "
    "Alert on prestige-threatening situations.")

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

DECISION_NETWORKING_AGENTS: list[type[BaseAgent]] = [
    OptionGeneratorAgent,
    SecondOpinionAgent,
    DevilsAdvocateAgent,
    TradeoffAgent,
    ReversibilityAgent,
    RegretMinimizerAgent,
    WarmIntroAgent,
    StatusSignalAgent,
    CircleBuilderAgent,
    FollowUpPrestigeAgent,
    PrestigeCalibrationAgent,
    ScarcityBuilderAgent,
    SignalNoiseStatusAgent,
    InfluenceAuraAgent,
    PrestigeRiskAgent,
]
