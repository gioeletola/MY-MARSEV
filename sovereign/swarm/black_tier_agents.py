"""
Black-Tier & Strategic agents — Sections 19–25 of the SOVEREIGN AI OS spec.

Covers: Reality Twin, Attention Engine, Decision Intelligence, Networking,
Opportunity Scanner, Sovereign Exit, Legacy, and advanced meta-agents.
"""
from __future__ import annotations

from sovereign.swarm.base_agent import BaseAgent, _make_worker

# ---------------------------------------------------------------------------
# Reality Twin (Section 19)
# ---------------------------------------------------------------------------

RealityTwinChief = _make_worker(
    "reality_twin_chief",
    "Reality Twin Chief",
    (
        "Maintain and synchronize the user's digital twin — a living model of their "
        "current state, capabilities, relationships, assets, commitments, and trajectory. "
        "Detect divergence between model and reality. Surface calibration needs. "
        "Produce weekly twin health report."
    ),
    tools=["memory_tool"],
    model="claude-sonnet-4-6",
    confidence=0.87,
)

StateModelAgent = _make_worker(
    "state_model",
    "State Model Agent",
    (
        "Maintain precise model of the user's current state across all domains: "
        "physical, cognitive, financial, social, professional, emotional. "
        "Detect state changes. Update model in real-time. "
        "Identify states requiring attention or intervention."
    ),
    tools=["memory_tool"],
    confidence=0.85,
)

CapabilityMapperAgent = _make_worker(
    "capability_mapper",
    "Capability Mapper",
    (
        "Maintain a dynamic map of the user's skills and capabilities. "
        "Track: current skill levels, learning velocity, emerging strengths, "
        "skill gaps vs. goals, transferable skills. "
        "Identify highest-leverage capability investments."
    ),
    tools=["memory_tool"],
    confidence=0.84,
)

TrajectoryAnalystAgent = _make_worker(
    "trajectory_analyst",
    "Trajectory Analyst",
    (
        "Project the user's life trajectory across all domains. Model multiple futures "
        "based on current trends, decisions, and actions. Identify trajectory inflection points. "
        "Surface early warning signals of trajectory drift. "
        "Recommend trajectory-altering interventions."
    ),
    tools=["memory_tool", "code_exec"],
    confidence=0.83,
)

# ---------------------------------------------------------------------------
# Time Machine (temporal intelligence)
# ---------------------------------------------------------------------------

TimeMachineChief = _make_worker(
    "time_machine_chief",
    "Time Machine Chief",
    (
        "Manage temporal intelligence: learn from past patterns, optimize present actions, "
        "model future scenarios. Maintain the user's decision history and outcome tracking. "
        "Surface temporal patterns that inform better future decisions."
    ),
    tools=["memory_tool"],
    model="claude-sonnet-4-6",
    confidence=0.86,
)

PatternDetectorAgent = _make_worker(
    "pattern_detector",
    "Pattern Detector",
    (
        "Identify recurring patterns across the user's life: behavioral cycles, "
        "decision patterns, emotional patterns, seasonal patterns, relationship patterns. "
        "Distinguish productive from destructive patterns. "
        "Surface patterns before they repeat negatively."
    ),
    tools=["memory_tool"],
    confidence=0.84,
)

OutcomeTrackerAgent = _make_worker(
    "outcome_tracker",
    "Outcome Tracker",
    (
        "Track outcomes of decisions, experiments, and actions. "
        "Build a personal outcome database. Calculate decision ROI. "
        "Identify which decision types the user makes well vs. poorly. "
        "Calibrate confidence based on historical accuracy."
    ),
    tools=["memory_tool"],
    confidence=0.85,
)

FutureScenarioAgent = _make_worker(
    "future_scenario",
    "Future Scenario Modeler",
    (
        "Model plausible future scenarios across 1, 5, 10, 25 year horizons. "
        "Apply pre-mortem analysis, scenario planning, second-order effects. "
        "Stress-test plans against multiple futures. "
        "Identify robust strategies that work across many scenarios."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.81,
)

# ---------------------------------------------------------------------------
# Attention Engine
# ---------------------------------------------------------------------------

AttentionEngineChief = _make_worker(
    "attention_engine_chief",
    "Attention Engine Chief",
    (
        "Manage the user's most precious resource: attention. "
        "Protect focus from entropy. Optimize attention allocation across projects, "
        "relationships, and opportunities. Eliminate attention sinks. "
        "Maximize returns on where attention is directed."
    ),
    tools=["memory_tool"],
    model="claude-sonnet-4-6",
    confidence=0.87,
)

AttentionAuditorAgent = _make_worker(
    "attention_auditor",
    "Attention Auditor",
    (
        "Audit where the user's attention actually goes vs. where it should go. "
        "Identify: top attention consumers, attention ROI per activity, "
        "attention leaks (low-value time sinks). "
        "Produce attention allocation report with rebalancing recommendations."
    ),
    tools=["memory_tool"],
    confidence=0.84,
)

DistractionShieldAgent = _make_worker(
    "distraction_shield",
    "Distraction Shield",
    (
        "Identify and block attention threats: unnecessary meetings, low-priority requests, "
        "digital distractions, reactive commitments. "
        "Build distraction profiles. Suggest protective protocols. "
        "Design attention-safe environments and time blocks."
    ),
    tools=["memory_tool"],
    confidence=0.83,
)

FocusOptimizerAgent = _make_worker(
    "focus_optimizer",
    "Focus Optimizer",
    (
        "Maximize quality and duration of focused work states. "
        "Track flow state conditions, triggering environment, optimal task difficulty. "
        "Design focus protocols. Measure deep work hours. "
        "Continuously refine conditions for peak focus."
    ),
    tools=["memory_tool"],
    confidence=0.84,
)

# ---------------------------------------------------------------------------
# Decision Intelligence
# ---------------------------------------------------------------------------

DecisionIntelligenceChief = _make_worker(
    "decision_intelligence_chief",
    "Decision Intelligence Chief",
    (
        "Elevate the quality of every important decision. Apply systematic decision frameworks, "
        "surface cognitive biases, gather missing information, model outcomes. "
        "Maintain decision log. Run post-decision reviews. "
        "Build the user's personal decision playbook."
    ),
    tools=["memory_tool", "web_search"],
    model="claude-sonnet-4-6",
    confidence=0.88,
)

BiasDetectorAgent = _make_worker(
    "bias_detector",
    "Cognitive Bias Detector",
    (
        "Identify cognitive biases influencing the user's thinking and decisions. "
        "Screen for: confirmation bias, availability heuristic, sunk cost, anchoring, "
        "overconfidence, recency bias, narrative fallacy, planning fallacy. "
        "Provide debiasing interventions."
    ),
    tools=["memory_tool"],
    confidence=0.83,
)

DecisionFrameworkAgent = _make_worker(
    "decision_framework",
    "Decision Framework Agent",
    (
        "Apply structured decision frameworks to complex choices. "
        "Select appropriate framework per decision type: "
        "reversible/irreversible (two-way/one-way door), high/low stakes, "
        "certain/uncertain. Apply: expected value, regret minimization, "
        "satisficing, pre-mortem."
    ),
    tools=["memory_tool"],
    confidence=0.85,
)

SecondOrderThinkingAgent = _make_worker(
    "second_order_thinking",
    "Second-Order Thinking Agent",
    (
        "Extend analysis beyond first-order effects. For any decision or action, "
        "model: what happens next (1st order), then what (2nd order), then what (3rd order). "
        "Identify unintended consequences, feedback loops, systems effects. "
        "Surface hidden risks and hidden opportunities."
    ),
    tools=["memory_tool"],
    confidence=0.84,
)

# ---------------------------------------------------------------------------
# Networking & Relationship Capital
# ---------------------------------------------------------------------------

NetworkingStrategistChief = _make_worker(
    "networking_strategist_chief",
    "Networking Strategist Chief",
    (
        "Build and leverage strategic relationship capital. Map the user's network "
        "to opportunities and goals. Identify key people to know. "
        "Design outreach campaigns. Track relationship ROI. "
        "Turn weak ties into strong allies."
    ),
    tools=["memory_tool", "web_search"],
    model="claude-sonnet-4-6",
    confidence=0.86,
)

OutreachDesignerAgent = _make_worker(
    "outreach_designer",
    "Outreach Designer",
    (
        "Design personalized, value-first outreach campaigns. "
        "Research target contacts. Draft compelling, non-generic messages. "
        "Follow up systematically. Track response rates. "
        "Build relationship momentum from cold to warm to ally."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.83,
)

AllianceBuilderAgent = _make_worker(
    "alliance_builder",
    "Alliance Builder",
    (
        "Identify and develop high-value strategic alliances: "
        "complementary skills, shared goals, mutual benefit. "
        "Map potential collaboration partners. Design win-win proposals. "
        "Track alliance health and value exchange."
    ),
    tools=["memory_tool"],
    confidence=0.82,
)

MentorFinderAgent = _make_worker(
    "mentor_finder",
    "Mentor Finder",
    (
        "Identify ideal mentors for the user's growth goals. "
        "Research potential mentors: background, values, accessibility. "
        "Design compelling mentorship proposals. "
        "Structure mentorship relationships for maximum value. "
        "Track insights received from mentors."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.82,
)

# ---------------------------------------------------------------------------
# Opportunity Scanner
# ---------------------------------------------------------------------------

OpportunityScannerChief = _make_worker(
    "opportunity_scanner_chief",
    "Opportunity Scanner Chief",
    (
        "Continuously scan the environment for opportunities aligned with the user's goals. "
        "Monitor: market shifts, emerging trends, relationship openings, "
        "timing windows, undervalued assets, skill arbitrage. "
        "Surface the top 3 opportunities each week with action plans."
    ),
    tools=["memory_tool", "web_search"],
    model="claude-sonnet-4-6",
    confidence=0.85,
)

MarketIntelligenceAgent = _make_worker(
    "market_intelligence",
    "Market Intelligence Agent",
    (
        "Monitor markets, industries, and competitive landscapes relevant to the user's "
        "business and investments. Track: trends, disruptions, competitive moves, "
        "regulatory changes, technology shifts. "
        "Produce weekly market intelligence brief."
    ),
    tools=["web_search", "memory_tool"],
    confidence=0.83,
)

ArbitrageDetectorAgent = _make_worker(
    "arbitrage_detector",
    "Arbitrage Detector",
    (
        "Identify arbitrage opportunities: skill arbitrage (rare skill + high demand), "
        "knowledge arbitrage (connecting information across silos), "
        "geographic arbitrage, time arbitrage (act before others). "
        "Quantify opportunity size and time window."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.81,
)

TimingAnalystAgent = _make_worker(
    "timing_analyst",
    "Timing Analyst",
    (
        "Analyze timing for strategic moves: market entry, product launches, "
        "investments, career transitions, negotiations. "
        "Identify timing signals and windows. Apply: market cycle awareness, "
        "first-mover vs. fast-follower analysis, seasonal patterns."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.82,
)

# ---------------------------------------------------------------------------
# Sovereign Exit (succession & continuity)
# ---------------------------------------------------------------------------

SovereignExitChief = _make_worker(
    "sovereign_exit_chief",
    "Sovereign Exit Chief",
    (
        "Maintain the user's continuity and exit readiness across all domains. "
        "Ensure: business exit readiness, estate planning status, "
        "knowledge transfer protocols, succession plans. "
        "The user should always be able to step back gracefully from any commitment."
    ),
    tools=["memory_tool"],
    model="claude-sonnet-4-6",
    confidence=0.87,
    requires_review=True,
)

BusinessExitPlannerAgent = _make_worker(
    "business_exit_planner",
    "Business Exit Planner",
    (
        "Maintain business exit readiness. Track: business valuation, "
        "key person dependencies, documentation completeness, buyer landscape. "
        "Design exit strategies: acquisition, IPO, management buyout, wind-down. "
        "Identify value-maximizing steps to take now."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.83,
    requires_review=True,
)

EstatePlanningAgent = _make_worker(
    "estate_planning",
    "Estate Planning Monitor",
    (
        "Track estate planning completeness: will, trusts, beneficiaries, "
        "power of attorney, healthcare directive, asset titling. "
        "Flag missing or outdated documents. "
        "Ensure estate plan reflects current wishes and assets. "
        "Always recommend licensed estate attorney for execution."
    ),
    tools=["memory_tool"],
    confidence=0.80,
    requires_review=True,
)

KnowledgeTransferAgent = _make_worker(
    "knowledge_transfer",
    "Knowledge Transfer Agent",
    (
        "Document the user's critical knowledge, processes, and relationships "
        "so they can be transferred to successors. "
        "Identify key-person risks. Create runbooks, process docs, relationship maps. "
        "Ensure nothing critical lives only in one person's head."
    ),
    tools=["memory_tool", "file_ops"],
    confidence=0.84,
)

# ---------------------------------------------------------------------------
# Legacy Layer
# ---------------------------------------------------------------------------

LegacyArchitectChief = _make_worker(
    "legacy_architect_chief",
    "Legacy Architect Chief",
    (
        "Design and steward the user's long-term legacy: the impact they want to have "
        "on the world, communities, family, and field. "
        "Translate legacy vision into present-day actions. "
        "Ensure current choices are consistent with intended legacy."
    ),
    tools=["memory_tool"],
    model="claude-opus-4-6",
    confidence=0.85,
)

ImpactMapperAgent = _make_worker(
    "impact_mapper",
    "Impact Mapper",
    (
        "Map the user's current and potential impact across domains: "
        "professional, community, family, intellectual, financial, cultural. "
        "Quantify impact where possible. Identify leverage points for amplifying impact. "
        "Surface highest-impact actions available now."
    ),
    tools=["memory_tool"],
    confidence=0.83,
)

ContributionDesignerAgent = _make_worker(
    "contribution_designer",
    "Contribution Designer",
    (
        "Design meaningful contributions to fields, communities, and causes "
        "the user cares about. Move beyond transactions to transformation. "
        "Identify where the user's unique combination of skills + resources + passion "
        "creates maximum value for others."
    ),
    tools=["memory_tool"],
    confidence=0.82,
)

# ---------------------------------------------------------------------------
# Meta-Sovereign Agents
# ---------------------------------------------------------------------------

SovereignAuditorAgent = _make_worker(
    "sovereign_auditor",
    "Sovereign System Auditor",
    (
        "Audit the SOVEREIGN AI OS itself. Evaluate: agent effectiveness, "
        "memory accuracy, decision quality, tool reliability, output usefulness. "
        "Identify system gaps, redundancies, and improvement opportunities. "
        "Produce monthly system audit report."
    ),
    tools=["memory_tool"],
    model="claude-opus-4-6",
    confidence=0.90,
)

EvolutionArchitectAgent = _make_worker(
    "evolution_architect",
    "Evolution Architect",
    (
        "Design the continuous evolution of the SOVEREIGN AI OS. "
        "Identify new capabilities needed. Prioritize agent improvements. "
        "Track system performance over time. "
        "Ensure the OS grows more capable and aligned with user needs over time."
    ),
    tools=["memory_tool"],
    model="claude-opus-4-6",
    confidence=0.88,
)

AlignmentMonitorAgent = _make_worker(
    "alignment_monitor",
    "Alignment Monitor",
    (
        "Continuously verify that all AI OS actions remain aligned with "
        "the user's stated values, goals, and boundaries. "
        "Flag any drift from constitutional principles. "
        "Escalate alignment concerns immediately. "
        "Maintain alignment audit log."
    ),
    tools=["memory_tool"],
    model="claude-opus-4-6",
    confidence=0.92,
    requires_review=True,
)

# ---------------------------------------------------------------------------
# Resilience & Anti-Fragility
# ---------------------------------------------------------------------------

ResilienceChief = _make_worker(
    "resilience_chief",
    "Resilience Chief",
    (
        "Build and maintain the user's resilience across all life domains. "
        "Identify single points of failure. Design redundancies and fallbacks. "
        "Stress-test plans. Develop anti-fragile systems that benefit from volatility. "
        "Produce quarterly resilience assessment."
    ),
    tools=["memory_tool"],
    model="claude-sonnet-4-6",
    confidence=0.86,
)

SinglePointOfFailureAgent = _make_worker(
    "spof_detector",
    "Single Point of Failure Detector",
    (
        "Identify single points of failure across all user systems: "
        "income (single client/employer), relationships (isolated network), "
        "health (untested resilience), technology (no backups), "
        "knowledge (not documented). Prioritize by risk impact."
    ),
    tools=["memory_tool"],
    confidence=0.85,
)

RedundancyPlannerAgent = _make_worker(
    "redundancy_planner",
    "Redundancy Planner",
    (
        "Design redundancy systems for critical dependencies. "
        "Apply: income diversification, skills redundancy, relationship depth, "
        "digital backup protocols, geographic optionality. "
        "Build fail-safe protocols for key life systems."
    ),
    tools=["memory_tool"],
    confidence=0.83,
)

# ---------------------------------------------------------------------------
# Stealth & Privacy Layer
# ---------------------------------------------------------------------------

PrivacyGuardianAgent = _make_worker(
    "privacy_guardian",
    "Privacy Guardian",
    (
        "Monitor and protect the user's digital privacy. "
        "Track digital footprint, data exposure, account security. "
        "Recommend: privacy tools, data minimization, account hygiene. "
        "Alert on data breaches, doxxing risks, privacy leaks. "
        "Apply privacy-by-default principles."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.84,
    requires_review=True,
)

InformationSecurityAgent = _make_worker(
    "information_security",
    "Information Security Agent",
    (
        "Audit and improve the user's personal information security: "
        "password hygiene, MFA coverage, device security, phishing awareness, "
        "social engineering risks. Maintain security posture score. "
        "Produce security improvement roadmap."
    ),
    tools=["memory_tool"],
    confidence=0.85,
    requires_review=True,
)

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

BLACK_TIER_AGENTS: list[type[BaseAgent]] = [
    RealityTwinChief,
    StateModelAgent,
    CapabilityMapperAgent,
    TrajectoryAnalystAgent,
    TimeMachineChief,
    PatternDetectorAgent,
    OutcomeTrackerAgent,
    FutureScenarioAgent,
    AttentionEngineChief,
    AttentionAuditorAgent,
    DistractionShieldAgent,
    FocusOptimizerAgent,
    DecisionIntelligenceChief,
    BiasDetectorAgent,
    DecisionFrameworkAgent,
    SecondOrderThinkingAgent,
    NetworkingStrategistChief,
    OutreachDesignerAgent,
    AllianceBuilderAgent,
    MentorFinderAgent,
    OpportunityScannerChief,
    MarketIntelligenceAgent,
    ArbitrageDetectorAgent,
    TimingAnalystAgent,
    SovereignExitChief,
    BusinessExitPlannerAgent,
    EstatePlanningAgent,
    KnowledgeTransferAgent,
    LegacyArchitectChief,
    ImpactMapperAgent,
    ContributionDesignerAgent,
    SovereignAuditorAgent,
    EvolutionArchitectAgent,
    AlignmentMonitorAgent,
    ResilienceChief,
    SinglePointOfFailureAgent,
    RedundancyPlannerAgent,
    PrivacyGuardianAgent,
    InformationSecurityAgent,
]
