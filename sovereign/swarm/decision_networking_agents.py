"""
Decision Intelligence and Networking/Status agents — Section 12, Black Tier.

Covers:
- Agenti Decisioni: Option Generator, Second Opinion, Devil's Advocate, Trade-off, Reversibility, Regret Minimizer
- Agenti Networking & Status: Warm Intro, Status Signal, Circle Builder, Follow-up Prestige, etc.
"""
from __future__ import annotations

import logging

from sovereign.swarm.base_agent import BaseAgent
from sovereign.swarm.leveled_agent import AgentLevel, _make_leveled_worker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Decision Agents
# ---------------------------------------------------------------------------

OptionGeneratorAgent = _make_leveled_worker(
    "option_generator",
    "Option Generator Agent",
    "Generate a comprehensive set of options for any decision. "
    "Resist anchoring on the first solution. "
    "Produce: obvious options, non-obvious options, extreme options, "
    "null option (do nothing), combination options. "
    "Minimum 5 distinct options per decision.",
    level=AgentLevel.LEVEL_4,
    model="claude-opus-4-7",
    triggers=["decision_event", "network_alert"],
    escalate_to="ceo",
    requires_approval_for=["EXECUTE"],
    mission="Option Generator Agent",
)

SecondOpinionAgent = _make_leveled_worker(
    "second_opinion",
    "Second Opinion Agent",
    "Provide a rigorous second opinion on decisions, plans, and assessments. "
    "Challenge assumptions. Apply alternative mental models. "
    "Ask: what could go wrong, what's being ignored, what would a skeptic say. "
    "Independent evaluation free from original framing.",
    level=AgentLevel.LEVEL_3,
    model="claude-opus-4-7",
    triggers=["decision_task"],
    escalate_to="chief_of_staff",
    mission="Second Opinion Agent",
)

DevilsAdvocateAgent = _make_leveled_worker(
    "devils_advocate",
    "Devil's Advocate Agent",
    "Argue the strongest possible case against any proposed plan or decision. "
    "Not to obstruct, but to surface hidden flaws before commitment. "
    "Steel-man the opposition. Find the real risks. "
    "Make the user defend their position against the best counter-argument.",
    level=AgentLevel.LEVEL_3,
    model="claude-opus-4-7",
    triggers=["decision_task"],
    escalate_to="chief_of_staff",
    mission="Devil's Advocate Agent",
)

TradeoffAgent = _make_leveled_worker(
    "tradeoff_agent",
    "Trade-off Agent",
    "Analyze the real trade-offs in any decision: what you gain vs. what you give up. "
    "Make trade-offs explicit and quantified where possible. "
    "Identify hidden trade-offs not immediately visible. "
    "Force clarity on what's actually being exchanged.",
    level=AgentLevel.LEVEL_3,
    triggers=["decision_task"],
    escalate_to="chief_of_staff",
    mission="Trade-off Agent",
)

ReversibilityAgent = _make_leveled_worker(
    "reversibility_agent",
    "Reversibility Agent",
    "Assess the reversibility of any decision or action. "
    "Classify: fully reversible, partially reversible, irreversible. "
    "Apply Amazon's two-way/one-way door framework. "
    "Recommend: proceed fast if reversible, proceed slow if irreversible. "
    "Exit strategy mapping.",
    level=AgentLevel.LEVEL_3,
    triggers=["decision_task"],
    escalate_to="chief_of_staff",
    mission="Reversibility Agent",
)

RegretMinimizerAgent = _make_leveled_worker(
    "regret_minimizer",
    "Regret Minimizer Agent",
    "Apply the regret minimization framework to major decisions. "
    "Project to age 80: which choice will you regret more? "
    "Identify regret-weighted outcomes. "
    "Optimize for long-term regret minimization over short-term comfort.",
    level=AgentLevel.LEVEL_3,
    model="claude-opus-4-7",
    triggers=["decision_task"],
    escalate_to="chief_of_staff",
    mission="Regret Minimizer Agent",
)

# ---------------------------------------------------------------------------
# Networking & Status Agents
# ---------------------------------------------------------------------------

WarmIntroAgent = _make_leveled_worker(
    "warm_intro",
    "Warm Intro Agent",
    "Identify and execute warm introduction opportunities. "
    "Map: who in the user's network can introduce them to key targets. "
    "Draft warm intro requests. "
    "Brief the user for post-intro meetings. "
    "Track intro outcomes.",
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool"],
    triggers=["decision_task"],
    escalate_to="chief_of_staff",
    mission="Warm Intro Agent",
)

StatusSignalAgent = _make_leveled_worker(
    "status_signal",
    "Status Signal Agent",
    "Design and deploy strategic status signals: "
    "affiliations, appearances, associations, achievements, possessions. "
    "What signals communicate the right status in the right context? "
    "Build a consistent status signaling strategy.",
    level=AgentLevel.LEVEL_3,
    triggers=["decision_task"],
    escalate_to="chief_of_staff",
    mission="Status Signal Agent",
)

CircleBuilderAgent = _make_leveled_worker(
    "circle_builder",
    "Circle Builder Agent",
    "Build the user's elite circles: mastermind groups, peer networks, "
    "advisory boards, investment syndicates, social clubs. "
    "Identify relevant circles to join. "
    "Design circles worth creating. "
    "Curate membership.",
    level=AgentLevel.LEVEL_3,
    triggers=["decision_task"],
    escalate_to="chief_of_staff",
    mission="Circle Builder Agent",
)

FollowUpPrestigeAgent = _make_leveled_worker(
    "follow_up_prestige",
    "Follow-up Prestige Agent",
    "Execute high-quality follow-ups after meetings with important people. "
    "Add value in every follow-up. Never be generic. "
    "Reference specific conversation points. "
    "Build relationship equity through exceptional follow-through.",
    level=AgentLevel.LEVEL_2,
    triggers=[],
    escalate_to="chief_of_staff",
    mission="Follow-up Prestige Agent",
)

PrestigeCalibrationAgent = _make_leveled_worker(
    "prestige_calibration",
    "Prestige Calibration Agent",
    "Calibrate the user's prestige positioning: "
    "are they playing at the right table, signaling at the right level, "
    "associating with the right people? "
    "Identify prestige ceiling and prestige floor. "
    "Recommend calibration adjustments.",
    level=AgentLevel.LEVEL_3,
    triggers=["decision_task"],
    escalate_to="chief_of_staff",
    mission="Prestige Calibration Agent",
)

ScarcityBuilderAgent = _make_leveled_worker(
    "scarcity_builder",
    "Scarcity Builder Agent",
    "Build strategic scarcity around the user's time and attention: "
    "selective availability, exclusive access, limited commitments. "
    "Scarcity as a social and professional asset. "
    "Design access protocols that signal high value.",
    level=AgentLevel.LEVEL_3,
    triggers=["decision_task"],
    escalate_to="chief_of_staff",
    mission="Scarcity Builder Agent",
)

SignalNoiseStatusAgent = _make_leveled_worker(
    "signal_noise_status",
    "Signal-to-Noise Status Agent",
    "Maximize the signal-to-noise ratio in the user's public presence: "
    "high-quality, infrequent output vs. constant low-quality noise. "
    "When to speak, when to stay silent. "
    "Build a reputation for signal.",
    level=AgentLevel.LEVEL_3,
    triggers=["decision_task"],
    escalate_to="chief_of_staff",
    mission="Signal-to-Noise Status Agent",
)

InfluenceAuraAgent = _make_leveled_worker(
    "influence_aura",
    "Influence Aura Agent",
    "Cultivate an aura of influence: the perception that the user has "
    "more access, more information, more connections than others. "
    "Strategic visibility in key circles. "
    "The art of strategic presence.",
    level=AgentLevel.LEVEL_3,
    triggers=["decision_task"],
    escalate_to="chief_of_staff",
    mission="Influence Aura Agent",
)

PrestigeRiskAgent = _make_leveled_worker(
    "prestige_risk",
    "Prestige Risk Agent",
    "Monitor and mitigate risks to the user's prestige and status: "
    "association with failing people or ventures, overexposure, "
    "status inconsistency, prestige dilution. "
    "Alert on prestige-threatening situations.",
    level=AgentLevel.LEVEL_2,
    triggers=[],
    escalate_to="chief_of_staff",
    mission="Prestige Risk Agent",
)

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
