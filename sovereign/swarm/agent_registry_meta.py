"""
Agent Registry Meta — SOVEREIGN AI OS.

Maintains the authoritative mapping of agent_id → AgentLevel and
agent_id → AgentSpec for every agent in the swarm.

Usage:
    from sovereign.swarm.agent_registry_meta import (
        register_agent_meta,
        get_agent_level,
        agents_by_level,
        classify_all_agents,
        AGENT_LEVELS,
        AGENT_SPECS,
    )

All executive core agents (LEVEL_4/LEVEL_3) and swarm worker agents (LEVEL_2/LEVEL_3)
are pre-populated on import.  Unknown agents default to LEVEL_2.
"""
from __future__ import annotations

from sovereign.swarm.leveled_agent import AgentLevel, AgentSpec

# ---------------------------------------------------------------------------
# Mutable registries (module-level singletons)
# ---------------------------------------------------------------------------

AGENT_LEVELS: dict[str, AgentLevel] = {}
AGENT_SPECS: dict[str, AgentSpec] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register_agent_meta(spec: AgentSpec) -> None:
    """
    Register an AgentSpec in both AGENT_SPECS and AGENT_LEVELS.

    Calling this more than once for the same agent_id overwrites the
    previous entry (last-write wins).
    """
    AGENT_SPECS[spec.agent_id] = spec
    AGENT_LEVELS[spec.agent_id] = spec.level


def get_agent_level(agent_id: str) -> AgentLevel:
    """
    Return the AgentLevel for the given agent_id.

    Falls back to LEVEL_2 for any unknown agent so callers never receive
    a KeyError.
    """
    return AGENT_LEVELS.get(agent_id, AgentLevel.LEVEL_2)


def agents_by_level(level: AgentLevel) -> list[AgentSpec]:
    """
    Return all registered AgentSpecs whose level equals *level*.

    For agents that are in AGENT_LEVELS but not in AGENT_SPECS (registered
    via the lightweight dict only), a minimal placeholder AgentSpec is
    synthesised on the fly so callers always receive AgentSpec instances.
    """
    results: list[AgentSpec] = []
    for agent_id, agent_level in AGENT_LEVELS.items():
        if agent_level == level:
            if agent_id in AGENT_SPECS:
                results.append(AGENT_SPECS[agent_id])
            else:
                # Synthesise a minimal placeholder spec
                results.append(
                    AgentSpec(
                        agent_id=agent_id,
                        level=agent_level,
                        mission=f"{agent_id} agent",
                        triggers=[],
                        tools_allowed=["memory_tool"],
                        escalate_to="",
                        requires_approval_for=[],
                        success_metric="Task completed successfully",
                        failure_condition="Exception raised or confidence below threshold",
                    )
                )
    return results


def classify_all_agents() -> dict[str, str]:
    """
    Return a flat mapping of {agent_id: "LEVEL_2" | "LEVEL_3" | "LEVEL_4"}
    for every registered agent.
    """
    return {
        agent_id: f"LEVEL_{level.value}"
        for agent_id, level in AGENT_LEVELS.items()
    }


# ---------------------------------------------------------------------------
# Pre-population: sovereign executive core (LEVEL_5)
# ---------------------------------------------------------------------------

_LEVEL_5_SOVEREIGN = [
    "ceo",
    "chief_of_staff",
    "guardian",
    "coordinator",
    "task_setter_executive",
]

for _aid in _LEVEL_5_SOVEREIGN:
    AGENT_LEVELS[_aid] = AgentLevel.LEVEL_5

# ---------------------------------------------------------------------------
# Pre-population: executive support (LEVEL_3)
# ---------------------------------------------------------------------------

_LEVEL_3_CORE = [
    "system",
    "orchestrator",
]

for _aid in _LEVEL_3_CORE:
    AGENT_LEVELS[_aid] = AgentLevel.LEVEL_3

# ---------------------------------------------------------------------------
# Pre-population: general worker agents (LEVEL_2)
# ---------------------------------------------------------------------------

_LEVEL_2_WORKERS = [
    # From worker_agent.py
    "worker",
    # From base_agent._make_worker factory — common swarm workers
    "approval_gate",
    "ephemeral",
    "special",
    "orchestrator_agent",
    # Finance agents (finance_agents.py)
    "portfolio_manager",
    "risk_analyst",
    "tax_optimizer",
    "cash_flow_analyst",
    "investment_researcher",
    "budget_analyst",
    "debt_strategist",
    "options_analyst",
    "crypto_analyst",
    "real_estate_analyst",
    "insurance_analyst",
    "retirement_planner",
    "estate_planner",
    "forensic_accountant",
    "financial_modeler",
    "venture_analyst",
    "private_equity_analyst",
    "hedge_fund_analyst",
    "commodity_trader",
    "fx_analyst",
    "quant_researcher",
    "algo_trader",
    "credit_analyst",
    "financial_compliance",
    "esg_analyst",
    "financial_educator",
    # Business agents (business_agents.py) — workflow-capable
    "strategy_advisor",
    "market_researcher",
    "competitive_analyst",
    "product_manager",
    "growth_hacker",
    "sales_strategist",
    "bd_manager",
    "partnership_analyst",
    "pricing_analyst",
    "revenue_optimizer",
    "customer_success",
    "brand_strategist",
    "marketing_director",
    "content_strategist",
    "seo_specialist",
    "social_media_manager",
    "pr_specialist",
    "event_planner",
    "ops_director",
    "supply_chain",
    "logistics_analyst",
    "quality_manager",
    "process_optimizer",
    "project_manager",
    "hr_director",
    "talent_acquirer",
    "culture_architect",
    "training_designer",
    "compensation_analyst",
    "legal_advisor",
    "compliance_manager",
    "ip_strategist",
    "contract_analyst",
    "regulatory_advisor",
    "data_scientist",
    "bi_analyst",
    "it_director",
    "security_architect",
    "devops_engineer",
    "cto_advisor",
    "innovation_director",
    "rd_manager",
    "transformation_lead",
    "digital_strategist",
    "esg_manager",
    "sustainability_advisor",
    "csr_director",
    "investor_relations",
    "board_advisor",
    "governance_specialist",
    "m_and_a_advisor",
    "due_diligence",
    "integration_manager",
    "turnaround_specialist",
    "bankruptcy_advisor",
    "exit_planner",
    "ipo_advisor",
    "spac_analyst",
    "cfo_advisor",
    "coo_advisor",
    "cmo_advisor",
    "cco_advisor",
    "chro_advisor",
    "clo_advisor",
    "cdo_advisor",
    "chief_risk_officer",
    # Security agents (security_agents.py)
    "threat_analyst",
    "penetration_tester",
    "compliance_auditor",
    "incident_responder",
    "security_trainer",
    # Offline agents (offline_agents.py)
    "offline_researcher",
    "offline_writer",
    "offline_analyst",
    "offline_coder",
    # Decision networking agents (decision_networking_agents.py)
    "network_mapper",
    "influence_analyst",
    "coalition_builder",
    "negotiation_advisor",
    "stakeholder_manager",
    "communication_strategist",
    "media_relations",
    "public_affairs",
    "lobbying_advisor",
    "crisis_communicator",
    "reputation_manager",
    "social_network_analyst",
    "power_broker",
    "alliance_strategist",
    "decision_facilitator",
    # Domain chiefs (domain_chiefs.py)
    "finance_chief",
    "business_chief",
    "personal_chief",
    "security_chief",
    "research_chief",
]

for _aid in _LEVEL_2_WORKERS:
    AGENT_LEVELS[_aid] = AgentLevel.LEVEL_2

# ---------------------------------------------------------------------------
# Pre-population: personal / advisory agents → LEVEL_2 (min tier, no LEVEL_1)
# ---------------------------------------------------------------------------

_LEVEL_1_PERSONA = [
    # personal_agents.py — lifestyle consultants
    "life_coach",
    "relationship_advisor",
    "health_advisor",
    "fitness_coach",
    "nutrition_advisor",
    "sleep_coach",
    "mindfulness_coach",
    "productivity_coach",
    "career_advisor",
    "education_advisor",
    "parenting_advisor",
    "pet_advisor",
    "travel_advisor",
    "entertainment_advisor",
    "fashion_advisor",
    "home_decorator",
    "event_personal_planner",
    "gift_advisor",
    "social_skills_coach",
    "communication_coach",
    "language_tutor",
    "creative_writing_coach",
    "reading_advisor",
    "philosophy_advisor",
    "spiritual_advisor",
    "grief_counselor",
    "stress_manager",
    "habit_coach",
    "goal_setter",
    "motivation_coach",
    "time_management_coach",
    "declutter_advisor",
    "minimalism_coach",
    "sustainability_personal",
    "financial_literacy_coach",
    "dating_coach",
    "friendship_advisor",
    "family_therapist",
    "conflict_resolver",
    "boundaries_coach",
    # imperial_agents.py — high-level advisory (consultation-only tier)
    "imperial_strategist",
    "empire_architect",
    "sovereign_advisor",
    "legacy_planner",
    "dynasty_builder",
    "power_analyst",
    "geopolitical_advisor",
    "macroeconomic_analyst",
    "civilisation_historian",
    "futurist",
    "systems_thinker",
    "first_principles_analyst",
    "contrarian_thinker",
    "scenario_planner",
    "black_swan_analyst",
    "antifragility_advisor",
    "stoic_counselor",
    "virtue_ethicist",
    "consequentialist_analyst",
    "deontological_advisor",
    "tribal_dynamics_analyst",
    "evolutionary_psychologist",
    "biohacker",
    "longevity_researcher",
    "consciousness_explorer",
    "nootropics_advisor",
    "peak_performance_coach",
    "flow_state_optimizer",
    "deep_work_strategist",
    "learning_accelerator",
    "memory_architect",
    "speed_reader",
    "creativity_catalyst",
    "lateral_thinker",
    "innovation_catalyst",
    "disruption_analyst",
    "paradigm_shifter",
    "narrative_strategist",
    "persuasion_architect",
    "influence_architect",
    "status_game_analyst",
    "social_capital_builder",
    "network_weaver",
    "mentorship_advisor",
    "board_of_directors_ai",
    "personal_philosopher",
    "ultimate_question_asker",
    "devils_advocate",
    "red_team_leader",
    "steelman_builder",
    "consensus_builder",
]

for _aid in _LEVEL_1_PERSONA:
    AGENT_LEVELS[_aid] = AgentLevel.LEVEL_2

# personal_workers.py agents are workflow-capable → LEVEL_2
_LEVEL_2_PERSONAL_WORKERS = [
    "calendar_manager",
    "task_prioritizer",
    "email_assistant",
    "note_taker",
    "reminder_manager",
    "journal_assistant",
    "budget_personal",
    "expense_tracker",
    "shopping_assistant",
    "research_assistant",
    "reading_list_manager",
    "contact_manager",
    "meeting_prep",
    "document_organizer",
    "password_advisor",
    "digital_declutter",
    "subscription_manager",
    "habit_tracker",
    "goal_tracker",
    "project_personal",
]

for _aid in _LEVEL_2_PERSONAL_WORKERS:
    AGENT_LEVELS[_aid] = AgentLevel.LEVEL_2
