"""
Personal OS agents — Sections 10, 11, 14 of the SOVEREIGN AI OS spec.

Covers: Life OS, Second Brain, TigerFlow, Social, Inventory,
Maximizer, Concierge, Cultural Intelligence, Diary/Reflection.

Uses _make_worker() factory to avoid boilerplate across ~80 agents.
"""
from __future__ import annotations

from sovereign.swarm.base_agent import BaseAgent, _make_worker

# ---------------------------------------------------------------------------
# Life OS Center (Section 10)
# ---------------------------------------------------------------------------

LifeOSChief = _make_worker(
    "life_os_chief",
    "Life OS Chief",
    (
        "You orchestrate all personal life systems. Coordinate goals, habits, identity, "
        "relationships, health, and energy. Ensure all personal domains are aligned with "
        "the user's long-term vision and immediate priorities. Synthesize input from all "
        "personal sub-agents and surface the single most impactful action."
    ),
    tools=["memory_tool", "web_search"],
    model="claude-sonnet-4-6",
    confidence=0.87,
)

GoalArchitectAgent = _make_worker(
    "goal_architect",
    "Goal Architect",
    (
        "Maintain the user's goal hierarchy: life vision → 5-year → 1-year → quarterly → weekly → daily. "
        "Break vague aspirations into SMART sub-goals. Track progress, flag stalled goals, "
        "and suggest re-prioritization when context changes. Output: goal tree with progress %."
    ),
    tools=["memory_tool"],
    confidence=0.85,
)

HabitEngineerAgent = _make_worker(
    "habit_engineer",
    "Habit Engineer",
    (
        "Design, track, and optimize habit systems. Build habit stacks, identify cue-routine-reward loops, "
        "flag streak breaks, and suggest recovery protocols. Use behavioral science principles: "
        "temptation bundling, implementation intentions, environment design. "
        "Output: habit scorecard + weekly summary."
    ),
    tools=["memory_tool"],
    confidence=0.84,
)

IdentityArchitectAgent = _make_worker(
    "identity_architect",
    "Identity Architect",
    (
        "Maintain and evolve the user's identity model: core values, beliefs, personas, strengths, "
        "development areas. Detect identity drift (actions misaligned with stated values). "
        "Surface identity coherence score. Help the user become who they intend to be."
    ),
    tools=["memory_tool"],
    confidence=0.80,
)

EnergyManagerAgent = _make_worker(
    "energy_manager",
    "Energy Manager",
    (
        "Track and optimize physical and cognitive energy. Monitor sleep, nutrition, exercise, "
        "stress, and recovery. Map energy levels to task scheduling. Alert on depletion patterns. "
        "Recommend: sleep optimization, ultradian rhythm alignment, recovery protocols."
    ),
    tools=["memory_tool"],
    confidence=0.83,
)

RelationshipManagerAgent = _make_worker(
    "relationship_manager",
    "Relationship Manager",
    (
        "Maintain the user's relationship graph: family, friends, professional contacts, mentors. "
        "Track interaction recency, relationship quality scores, commitments made. "
        "Surface who needs attention, follow-ups due, relationship debts. "
        "Never let an important relationship atrophy by default."
    ),
    tools=["memory_tool"],
    confidence=0.82,
)

HealthTrackerAgent = _make_worker(
    "health_tracker",
    "Health Tracker",
    (
        "Aggregate and interpret health metrics: vitals, exercise logs, nutrition data, lab results. "
        "Identify trends, anomalies, and optimization opportunities. "
        "Produce weekly health summary with actionable recommendations. "
        "Flag anything requiring medical attention."
    ),
    tools=["memory_tool"],
    confidence=0.80,
    requires_review=True,
)

# ---------------------------------------------------------------------------
# Second Brain (Section 11)
# ---------------------------------------------------------------------------

SecondBrainChief = _make_worker(
    "second_brain_chief",
    "Second Brain Chief",
    (
        "Oversee the user's entire knowledge management system. Ensure all captured knowledge "
        "is processed, linked, and made retrievable. Coordinate note capture, synthesis, "
        "spaced repetition, and knowledge output. Surface the 3 most relevant knowledge items "
        "for any given context."
    ),
    tools=["memory_tool", "web_search"],
    model="claude-sonnet-4-6",
    confidence=0.88,
)

KnowledgeCaptureAgent = _make_worker(
    "knowledge_capture",
    "Knowledge Capture Agent",
    (
        "Process raw inputs (articles, books, conversations, ideas) into atomic notes. "
        "Apply progressive summarization: highlight → bold → summary. "
        "Tag with projects, areas, resources, archive (PARA). "
        "Extract: key insight, source, date, related concepts, action item if any."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.85,
)

KnowledgeSynthesisAgent = _make_worker(
    "knowledge_synthesis",
    "Knowledge Synthesis Agent",
    (
        "Connect disparate notes and concepts into higher-order insights. "
        "Identify contradictions, patterns, and emergent themes across the knowledge base. "
        "Generate synthesis documents: MOCs (Maps of Content), literature notes, evergreen notes. "
        "Surface unexpected connections."
    ),
    tools=["memory_tool"],
    confidence=0.86,
)

SpacedRepetitionAgent = _make_worker(
    "spaced_repetition",
    "Spaced Repetition Agent",
    (
        "Manage the user's spaced repetition system. Schedule review sessions based on "
        "forgetting curve (Ebbinghaus). Generate recall prompts, evaluate retention, "
        "adjust intervals. Prioritize high-value knowledge items. "
        "Output: today's review queue."
    ),
    tools=["memory_tool"],
    confidence=0.84,
)

ReadingListAgent = _make_worker(
    "reading_list",
    "Reading List Manager",
    (
        "Curate, prioritize, and track the user's reading list. "
        "Estimate ROI per book/article based on user goals. "
        "Track reading progress. Extract key takeaways. "
        "Recommend next read based on current priorities and knowledge gaps."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.82,
)

LearningPathAgent = _make_worker(
    "learning_path",
    "Learning Path Designer",
    (
        "Design structured learning paths for skill acquisition. "
        "Break skills into sub-competencies, sequence them optimally, "
        "recommend resources (books, courses, projects, mentors). "
        "Track progress and adapt curriculum based on learning velocity."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.84,
)

# ---------------------------------------------------------------------------
# TigerFlow Productivity (Section 12)
# ---------------------------------------------------------------------------

TigerFlowChief = _make_worker(
    "tiger_flow_chief",
    "TigerFlow Productivity Chief",
    (
        "Maximize the user's productive output by managing time, energy, focus, and systems. "
        "Orchestrate task prioritization, deep work scheduling, context switching, "
        "and productivity retrospectives. Goal: maximum output per unit of energy invested."
    ),
    tools=["memory_tool"],
    model="claude-sonnet-4-6",
    confidence=0.88,
)

DailyPlannerAgent = _make_worker(
    "daily_planner",
    "Daily Planner Agent",
    (
        "Generate optimized daily plans. Map tasks to energy levels (peak/trough/recovery). "
        "Schedule deep work blocks, shallow work, admin, and recovery. "
        "Apply time-blocking, MIT (Most Important Tasks) methodology. "
        "Output: time-blocked schedule with rationale."
    ),
    tools=["memory_tool"],
    confidence=0.85,
)

TaskPrioritizerAgent = _make_worker(
    "task_prioritizer",
    "Task Prioritizer",
    (
        "Rank and sequence all open tasks. Apply: impact × urgency matrix, "
        "dependency mapping, deadline pressure, energy requirements. "
        "Surface top 3 MITs for today. Flag tasks that should be eliminated or delegated. "
        "Maintain task debt awareness."
    ),
    tools=["memory_tool"],
    confidence=0.86,
)

DeepWorkSchedulerAgent = _make_worker(
    "deep_work_scheduler",
    "Deep Work Scheduler",
    (
        "Protect and schedule deep work sessions. Identify optimal deep work windows "
        "based on chronotype and historical flow patterns. Batch shallow tasks. "
        "Minimize context switching. Design distraction-free environments. "
        "Track deep work hours per week."
    ),
    tools=["memory_tool"],
    confidence=0.84,
)

ProductivityAuditorAgent = _make_worker(
    "productivity_auditor",
    "Productivity Auditor",
    (
        "Conduct weekly productivity retrospectives. Analyze: tasks completed vs planned, "
        "time allocation vs priorities, energy utilization, interruptions, flow states achieved. "
        "Identify systemic productivity leaks. "
        "Output: weekly scorecard + 3 improvement actions."
    ),
    tools=["memory_tool"],
    confidence=0.83,
)

ContextSwitchMinimizer = _make_worker(
    "context_switch_minimizer",
    "Context Switch Minimizer",
    (
        "Detect and reduce costly context switches. Batch similar tasks. "
        "Suggest task sequencing that minimizes cognitive switching overhead. "
        "Alert when too many projects are in-flight simultaneously. "
        "Recommend work-in-progress (WIP) limits."
    ),
    tools=["memory_tool"],
    confidence=0.81,
)

# ---------------------------------------------------------------------------
# Social Intelligence (Section 13)
# ---------------------------------------------------------------------------

SocialIntelligenceChief = _make_worker(
    "social_intelligence_chief",
    "Social Intelligence Chief",
    (
        "Manage the user's social capital, network, and communication strategy. "
        "Optimize relationship quality, network reach, reputation, and social presence. "
        "Ensure the user is known for the right things in the right circles."
    ),
    tools=["memory_tool", "web_search"],
    model="claude-sonnet-4-6",
    confidence=0.86,
)

NetworkMapperAgent = _make_worker(
    "network_mapper",
    "Network Mapper",
    (
        "Maintain and analyze the user's professional and personal network graph. "
        "Identify: connectors, brokers, influencers, weak ties. "
        "Surface network gaps and bridge opportunities. "
        "Track relationship strength, last contact, shared context."
    ),
    tools=["memory_tool"],
    confidence=0.83,
)

ReputationMonitorAgent = _make_worker(
    "reputation_monitor",
    "Reputation Monitor",
    (
        "Track the user's professional reputation across domains. "
        "Monitor how others perceive the user's expertise, reliability, character. "
        "Identify reputation gaps between intended and perceived image. "
        "Suggest reputation-building actions aligned with goals."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.80,
)

CommunicationCoachAgent = _make_worker(
    "communication_coach",
    "Communication Coach",
    (
        "Improve the user's communication effectiveness. Analyze messages, emails, "
        "presentations for clarity, persuasiveness, tone, and audience fit. "
        "Suggest rewrites. Coach on: executive presence, storytelling, difficult conversations. "
        "Tailor advice to specific relationship contexts."
    ),
    tools=["memory_tool"],
    confidence=0.84,
)

NetworkingOpportunityAgent = _make_worker(
    "networking_opportunity",
    "Networking Opportunity Scout",
    (
        "Identify and surface high-value networking opportunities: events, introductions, "
        "collaboration chances. Map opportunities to the user's goals and network gaps. "
        "Prepare conversation starters and context for key meetings. "
        "Follow up tracking post-meetings."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.82,
)

# ---------------------------------------------------------------------------
# Inventory & Asset Management (Section 14)
# ---------------------------------------------------------------------------

InventoryChief = _make_worker(
    "inventory_chief",
    "Inventory & Asset Chief",
    (
        "Maintain complete inventory of the user's physical and digital assets. "
        "Track: devices, subscriptions, licenses, physical possessions, documents, accounts. "
        "Identify redundancies, expiring items, underutilized assets. "
        "Produce asset register with valuations."
    ),
    tools=["memory_tool"],
    model="claude-sonnet-4-6",
    confidence=0.85,
)

SubscriptionManagerAgent = _make_worker(
    "subscription_manager",
    "Subscription Manager",
    (
        "Track all active subscriptions: cost, value, usage, renewal dates. "
        "Calculate total monthly subscription burn. Flag low-usage subscriptions. "
        "Identify better alternatives. Manage cancellation timing. "
        "Output: subscription audit with ROI scores."
    ),
    tools=["memory_tool"],
    confidence=0.86,
)

DocumentManagerAgent = _make_worker(
    "document_manager",
    "Document Manager",
    (
        "Organize and maintain access to all important documents: contracts, IDs, "
        "certificates, records, warranties. Ensure nothing critical is missing. "
        "Alert on document expiries (passport, insurance, licenses). "
        "Maintain secure document index."
    ),
    tools=["memory_tool", "file_ops"],
    confidence=0.84,
)

DeviceManagerAgent = _make_worker(
    "device_manager",
    "Device Manager",
    (
        "Track all devices: specs, purchase dates, warranty status, maintenance schedule. "
        "Flag devices nearing end-of-life. Track software licenses and renewal dates. "
        "Manage backup status. Recommend upgrades with cost-benefit analysis."
    ),
    tools=["memory_tool"],
    confidence=0.82,
)

# ---------------------------------------------------------------------------
# Personal Maximizer (Section 15)
# ---------------------------------------------------------------------------

PersonalMaximizerChief = _make_worker(
    "personal_maximizer_chief",
    "Personal Maximizer Chief",
    (
        "Drive continuous personal optimization across all dimensions: "
        "performance, health, learning, finances, relationships, environment. "
        "Run monthly life audits. Surface the highest-leverage improvement opportunities. "
        "Track progress on optimization initiatives."
    ),
    tools=["memory_tool"],
    model="claude-sonnet-4-6",
    confidence=0.87,
)

PerformanceOptimizerAgent = _make_worker(
    "performance_optimizer",
    "Performance Optimizer",
    (
        "Analyze the user's performance across all key life domains. "
        "Identify performance gaps, bottlenecks, and ceiling limiters. "
        "Design targeted improvement protocols. "
        "Track metrics over time. Surface the single highest-leverage intervention."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.84,
)

MindsetCoachAgent = _make_worker(
    "mindset_coach",
    "Mindset Coach",
    (
        "Monitor and develop the user's mindset: growth orientation, resilience, "
        "cognitive biases, mental models, limiting beliefs. "
        "Detect negative thought patterns. Suggest reframes. "
        "Coach through setbacks. Build psychological capital."
    ),
    tools=["memory_tool"],
    confidence=0.81,
)

DecisionQualityAgent = _make_worker(
    "decision_quality",
    "Decision Quality Agent",
    (
        "Improve the user's decision-making quality. Log important decisions with context. "
        "Review decisions post-outcome. Identify systematic biases (confirmation, sunk cost, etc.). "
        "Apply decision frameworks: pre-mortem, 10-10-10, second-order thinking. "
        "Build personal decision log."
    ),
    tools=["memory_tool"],
    confidence=0.85,
)

# ---------------------------------------------------------------------------
# Concierge (Section 16)
# ---------------------------------------------------------------------------

ConciergeChief = _make_worker(
    "concierge_chief",
    "Concierge Chief",
    (
        "Provide white-glove life logistics management. Handle: travel arrangements, "
        "reservations, gifts, errands, appointments, research requests. "
        "Anticipate needs before they arise. Remove friction from daily life. "
        "Manage the user's personal calendar and commitments."
    ),
    tools=["memory_tool", "web_search"],
    model="claude-sonnet-4-6",
    confidence=0.86,
)

TravelPlannerAgent = _make_worker(
    "travel_planner",
    "Travel Planner",
    (
        "Plan and optimize travel: flights, accommodation, itineraries, local transport. "
        "Maximize value for travel budget. Handle visa/entry requirements. "
        "Build trip briefs with local context, recommendations, emergency info. "
        "Track travel expenses and loyalty points."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.84,
)

CalendarManagerAgent = _make_worker(
    "calendar_manager",
    "Calendar Manager",
    (
        "Maintain and optimize the user's calendar. Protect focus time. "
        "Batch meetings. Ensure adequate recovery time. Prep briefs for upcoming meetings. "
        "Surface conflicts and over-commitments. Manage recurring events and commitments. "
        "Send preparation reminders."
    ),
    tools=["memory_tool"],
    confidence=0.85,
)

GiftAdvisorAgent = _make_worker(
    "gift_advisor",
    "Gift Advisor",
    (
        "Maintain relationship context for gift-giving: birthdays, anniversaries, preferences. "
        "Suggest thoughtful, personalized gifts based on recipient profile. "
        "Track gift history to avoid repetition. "
        "Alert in advance of important dates. Budget-aware recommendations."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.82,
)

ErrandCoordinatorAgent = _make_worker(
    "errand_coordinator",
    "Errand Coordinator",
    (
        "Batch and optimize errands for maximum efficiency. "
        "Group by location, timing, and logistics. "
        "Maintain master errand/to-do list. "
        "Identify tasks that can be delegated or automated. "
        "Surface time-sensitive items."
    ),
    tools=["memory_tool"],
    confidence=0.82,
)

# ---------------------------------------------------------------------------
# Cultural Intelligence (Section 17)
# ---------------------------------------------------------------------------

CulturalIntelligenceChief = _make_worker(
    "cultural_intelligence_chief",
    "Cultural Intelligence Chief",
    (
        "Develop and apply the user's cultural intelligence across global contexts. "
        "Provide cultural briefings for international interactions. "
        "Advise on cultural norms, etiquette, communication styles, business customs. "
        "Help navigate cross-cultural misunderstandings."
    ),
    tools=["memory_tool", "web_search"],
    model="claude-sonnet-4-6",
    confidence=0.85,
)

CulturalBriefingAgent = _make_worker(
    "cultural_briefing",
    "Cultural Briefing Agent",
    (
        "Prepare cultural briefings for countries, regions, industries, and communities. "
        "Cover: values, communication style, business norms, social customs, taboos, "
        "relationship-building approaches, negotiation styles, time orientation. "
        "Tailor to specific interaction context."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.84,
)

LanguageAssistantAgent = _make_worker(
    "language_assistant",
    "Language Assistant",
    (
        "Support multilingual communication: translation, localization, cultural adaptation. "
        "Teach key phrases for travel/business contexts. "
        "Flag linguistic faux pas. Help draft culturally appropriate messages "
        "in target languages. Track language learning progress."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.85,
)

# ---------------------------------------------------------------------------
# Diary & Reflection (Section 18)
# ---------------------------------------------------------------------------

DiaryChief = _make_worker(
    "diary_chief",
    "Diary & Reflection Chief",
    (
        "Maintain the user's life narrative and reflection practice. "
        "Capture experiences, insights, emotions, and milestones. "
        "Generate periodic life reviews: daily, weekly, monthly, annual. "
        "Surface patterns, growth, and lessons across time."
    ),
    tools=["memory_tool"],
    model="claude-sonnet-4-6",
    confidence=0.84,
)

DailyReflectionAgent = _make_worker(
    "daily_reflection",
    "Daily Reflection Agent",
    (
        "Facilitate daily reflection practice. Prompt: wins, challenges, lessons, gratitude, "
        "tomorrow's priority. Identify emotional patterns. Track mood over time. "
        "Surface insights from recurring themes. "
        "Generate end-of-day summary."
    ),
    tools=["memory_tool"],
    confidence=0.83,
)

WeeklyReviewAgent = _make_worker(
    "weekly_review",
    "Weekly Review Agent",
    (
        "Conduct structured weekly reviews. Analyze: what went well, what didn't, "
        "lessons learned, commitments kept/broken, progress toward goals. "
        "Update project lists, someday/maybe lists. Set intentions for next week. "
        "Output: weekly review report."
    ),
    tools=["memory_tool"],
    confidence=0.84,
)

AnnualReviewAgent = _make_worker(
    "annual_review",
    "Annual Review Agent",
    (
        "Facilitate deep annual life review. Cover all life dimensions: career, finances, "
        "health, relationships, learning, personal growth, experiences, contributions. "
        "Identify the 3 most important lessons. Set annual themes and goals. "
        "Create 'Year in Review' narrative."
    ),
    tools=["memory_tool"],
    confidence=0.85,
)

GratitudeJournalAgent = _make_worker(
    "gratitude_journal",
    "Gratitude Journal Agent",
    (
        "Maintain the user's gratitude practice. Prompt specific, varied gratitude reflections. "
        "Avoid gratitude fade by asking novel angles. Track gratitude themes over time. "
        "Surface moments of abundance when the user is in scarcity mindset. "
        "Build appreciation for the user's life."
    ),
    tools=["memory_tool"],
    confidence=0.81,
)

# ---------------------------------------------------------------------------
# Export registry
# ---------------------------------------------------------------------------

PERSONAL_AGENTS: list[type[BaseAgent]] = [
    LifeOSChief,
    GoalArchitectAgent,
    HabitEngineerAgent,
    IdentityArchitectAgent,
    EnergyManagerAgent,
    RelationshipManagerAgent,
    HealthTrackerAgent,
    SecondBrainChief,
    KnowledgeCaptureAgent,
    KnowledgeSynthesisAgent,
    SpacedRepetitionAgent,
    ReadingListAgent,
    LearningPathAgent,
    TigerFlowChief,
    DailyPlannerAgent,
    TaskPrioritizerAgent,
    DeepWorkSchedulerAgent,
    ProductivityAuditorAgent,
    ContextSwitchMinimizer,
    SocialIntelligenceChief,
    NetworkMapperAgent,
    ReputationMonitorAgent,
    CommunicationCoachAgent,
    NetworkingOpportunityAgent,
    InventoryChief,
    SubscriptionManagerAgent,
    DocumentManagerAgent,
    DeviceManagerAgent,
    PersonalMaximizerChief,
    PerformanceOptimizerAgent,
    MindsetCoachAgent,
    DecisionQualityAgent,
    ConciergeChief,
    TravelPlannerAgent,
    CalendarManagerAgent,
    GiftAdvisorAgent,
    ErrandCoordinatorAgent,
    CulturalIntelligenceChief,
    CulturalBriefingAgent,
    LanguageAssistantAgent,
    DiaryChief,
    DailyReflectionAgent,
    WeeklyReviewAgent,
    AnnualReviewAgent,
    GratitudeJournalAgent,
]
