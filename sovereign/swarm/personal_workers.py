"""
Personal granular worker agents — Section 10 of the SOVEREIGN AI OS spec.

Covers all worker-level agents under every personal chief:
Life OS, Second Brain, Social, TigerFlow/Wellness, Lifestyle/Image,
Niche Aesthetics, Home/Environment, Culture & Intellect.
"""
from __future__ import annotations
import logging
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent
from sovereign.output.output_contract import OutputStatus, StructuredOutput

logger = logging.getLogger(__name__)


def _w(agent_id, specialty, instructions, tools=None, model="claude-sonnet-4-6",
        requires_review=False, confidence=0.82):
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
                "Provide a precise, actionable response."
            )
            result, history = await self._call_with_tools(
                [{"role": "user", "content": prompt}], ctx, task, max_tokens=1800
            )
            out = self._make_output(task=task, ctx=ctx, result=result,
                                    status=OutputStatus.SUCCESS, confidence=_conf,
                                    data={"specialty": specialty, "tool_turns": len(history)})
            out.requires_human_review = _review
            return out
        except Exception as exc:
            logger.error("PersonalWorker %s failed: %s", agent_id, exc)
            return StructuredOutput.failure(ctx.session_id, agent_id, task.task_id, str(exc))

    return type(f"{agent_id.replace('-','_').title()}Agent",
                (BaseAgent,), {"agent_id": agent_id, "model": _model, "run": run})


# ---------------------------------------------------------------------------
# Life OS Workers
# ---------------------------------------------------------------------------

LifeAdminAgent = _w("life_admin", "Life Admin Agent",
    "Handle administrative life tasks: document renewals, appointments, account maintenance, "
    "address changes, form submissions. Create clear action lists with deadlines and contacts.")

RoutineAgent = _w("routine_agent", "Routine Agent",
    "Design, track, and optimize daily/weekly routines. Build morning routines, evening routines, "
    "weekly rituals. Identify routine drift. Suggest improvements based on energy and goals. "
    "Output: routine scorecard with completion rate.")

ReminderIntelligenceAgent = _w("reminder_intelligence", "Reminder Intelligence Agent",
    "Manage smart reminders: time-based, location-based, context-based. "
    "Avoid reminder fatigue by batching and prioritizing. "
    "Distinguish urgency levels. Surface reminders at optimal timing. "
    "Track reminder response rate.")

SmartCalendarAgent = _w("smart_calendar", "Smart Calendar Agent",
    "Manage calendar intelligently: detect conflicts, protect focus blocks, "
    "batch meetings, suggest optimal scheduling windows per task type. "
    "Prepare 48-hour lookahead briefings. Flag over-commitment patterns.")

SmartAlarmAgent = _w("smart_alarm", "Smart Alarm Agent",
    "Optimize wake and alert timing based on sleep cycles, energy patterns, "
    "and schedule requirements. Design alarm protocols for different life contexts "
    "(workday, travel, recovery). Track sleep debt.")

AdminCleanerAgent = _w("admin_cleaner", "Admin Cleaner Agent",
    "Eliminate administrative backlog: outstanding emails, unanswered requests, "
    "pending forms, overdue responses. Batch process low-priority admin. "
    "Create zero-inbox protocols. Flag items requiring personal attention.")

RenewalAgent = _w("renewal_agent", "Renewal Agent",
    "Track all renewals: subscriptions, licenses, certifications, passports, insurance, "
    "contracts, warranties. Alert 30/14/7 days before expiry. "
    "Recommend: renew, upgrade, cancel, or replace. "
    "Output: renewal calendar.")

# ---------------------------------------------------------------------------
# Second Brain Workers
# ---------------------------------------------------------------------------

PersonalArchivistAgent = _w("personal_archivist", "Personal Archivist",
    "Systematically archive all important personal documents, decisions, projects, "
    "and experiences. Apply consistent tagging, categorization, and indexing. "
    "Ensure nothing important is lost. Maintain the historical record of the user's life.")

KnowledgeOrganizerAgent = _w("knowledge_organizer", "Knowledge Organizer",
    "Organize knowledge assets into coherent structures: folders, tags, MOCs, wikis. "
    "Apply PARA (Projects, Areas, Resources, Archive) methodology. "
    "Eliminate duplicates. Surface orphaned notes. "
    "Create navigation maps for large knowledge bases.")

KnowledgeSearchAgent = _w("knowledge_search", "Knowledge Search Agent",
    "Retrieve relevant knowledge from the user's second brain. "
    "Given a query, surface: exact matches, semantically related notes, "
    "connected concepts, past decisions on similar topics. "
    "Rank by relevance and recency.")

InsightAgent = _w("insight_agent", "Insight Agent",
    "Generate non-obvious insights from the user's accumulated knowledge. "
    "Connect dots across domains. Surface patterns invisible at note level. "
    "Generate 'insight reports': what you know about X, surprising connections, "
    "knowledge gaps. Weekly insight digest.")

# ---------------------------------------------------------------------------
# Social Workers
# ---------------------------------------------------------------------------

SocialAdvisorWorker = _w("social_advisor_worker", "Social Advisor Worker",
    "Provide tactical social intelligence advice for specific situations: "
    "navigating office politics, difficult conversations, social dynamics, "
    "impression management. Context-specific recommendations.")

FollowUpSocialeAgent = _w("follow_up_sociale", "Social Follow-up Agent",
    "Track and manage social follow-ups: people met, conversations to continue, "
    "promises made socially, introductions to make. "
    "Alert when follow-up windows are closing. Draft follow-up messages.")

OccasionReminderAgent = _w("occasion_reminder", "Occasion Reminder Agent",
    "Track all important occasions: birthdays, anniversaries, milestones, "
    "cultural events, professional recognitions. "
    "Alert in advance with context and suggestions. "
    "Never let an important occasion pass unacknowledged.")

AdmirationSignalAgent = _w("admiration_signal", "Admiration Signal Agent",
    "Identify and execute genuine gestures of appreciation and admiration. "
    "Track: who inspires the user, who helped them, who deserves recognition. "
    "Design personalized, authentic signals of respect and appreciation. "
    "Build goodwill systematically.")

SocialDebtAgent = _w("social_debt", "Social Debt Agent",
    "Track social debts and credits: favors received, help given, obligations created. "
    "Alert when social debts become overdue. "
    "Suggest repayment strategies. "
    "Maintain relationship reciprocity balance.")

ReconnectionAgent = _w("reconnection_agent", "Reconnection Agent",
    "Identify valuable relationships that have atrophied. "
    "Prioritize reconnection by relationship value and reachability. "
    "Draft warm, genuine reconnection messages. "
    "Track reconnection success rates.")

ConversationRecallAgent = _w("conversation_recall", "Conversation Recall Agent",
    "Maintain detailed memory of conversations: what was discussed, "
    "what was promised, what the other person cares about, their current situation. "
    "Brief the user before follow-up interactions. "
    "Never let someone feel forgotten.")

# ---------------------------------------------------------------------------
# TigerFlow / Wellness Workers
# ---------------------------------------------------------------------------

SleepAgent = _w("sleep_agent", "Sleep Agent",
    "Optimize sleep quality and quantity. Track sleep patterns, identify disruptions. "
    "Recommend: bedtime rituals, sleep environment optimization, sleep debt recovery. "
    "Design chronotype-aligned schedules. "
    "Alert on chronic sleep deprivation.")

FitnessPlannerAgent = _w("fitness_planner", "Fitness Planner",
    "Design and track fitness programs aligned with health goals and schedule. "
    "Balance: strength, cardio, mobility, recovery. "
    "Adapt program based on energy levels and life demands. "
    "Track progress metrics. Suggest workout modifications.")

NutritionOrganizerAgent = _w("nutrition_organizer", "Nutrition Organizer",
    "Structure nutrition for performance and health. Meal timing, macro guidance, "
    "pre/post workout nutrition, travel nutrition protocols. "
    "Track nutritional patterns. Identify dietary gaps. "
    "Suggest simple, sustainable nutrition improvements.")

RecoveryAgent = _w("recovery_agent", "Recovery Agent",
    "Manage active and passive recovery. Design recovery protocols: "
    "sleep, deload weeks, active recovery, stress management. "
    "Detect overtraining signals. Balance training load with recovery capacity. "
    "Prioritize recovery when performance dips.")

WorkoutExecutionAgent = _w("workout_execution", "Workout Execution Agent",
    "Generate specific workout sessions ready for execution: "
    "warm-up, main sets with reps/weights/rest, cool-down. "
    "Adapt in real-time based on available equipment and energy. "
    "Log completed workouts and track progressive overload.")

MealStructureAgent = _w("meal_structure", "Meal Structure Agent",
    "Plan daily/weekly meal structure: what to eat when. "
    "Batch cooking plans, simple meal templates, restaurant ordering strategies. "
    "Optimize for time efficiency and nutritional goals. "
    "Shopping list generation.")

# ---------------------------------------------------------------------------
# Image & Lifestyle Workers
# ---------------------------------------------------------------------------

StyleCuratorAgent = _w("style_curator", "Style Curator",
    "Curate and evolve the user's personal style. "
    "Analyze: current wardrobe, style gaps, occasion coverage, color palette. "
    "Define signature aesthetic. Recommend: key pieces, capsule wardrobe strategy. "
    "Ensure style consistency across contexts.")

PersonalShopperAgent = _w("personal_shopper", "Personal Shopper",
    "Research and recommend purchases: clothing, accessories, lifestyle items. "
    "Filter by: quality, value, aesthetic fit, brand alignment. "
    "Compare options. Track wishlists. "
    "Prevent impulse purchases that don't align with established taste.")

AestheticPlannerAgent = _w("aesthetic_planner", "Aesthetic Planner",
    "Design and maintain the user's overall aesthetic environment: "
    "home, workspace, digital presence, wardrobe. "
    "Ensure coherence across all aesthetic touchpoints. "
    "Develop a consistent visual language.")

GroomingManagerAgent = _w("grooming_manager", "Grooming Manager",
    "Maintain and optimize grooming routines and protocols. "
    "Track: haircut schedule, skincare routine, grooming products. "
    "Recommend upgrades based on goals. "
    "Build appointment calendar for grooming services.")

PresenceCoachAgent = _w("presence_coach", "Presence Coach",
    "Develop the user's physical and social presence. "
    "Coach on: posture, body language, voice, eye contact, energy projection. "
    "Analyze presence in different contexts: professional, social, intimate. "
    "Build commanding, authentic presence.")

MaximizerAgent = _w("maximizer_agent", "Maximizer Agent",
    "Identify and execute personal optimization opportunities across all domains. "
    "What's the single 1% improvement available right now? "
    "Track compound improvement over time. "
    "Prevent complacency by continuously raising the standard.")

AuraManagerAgent = _w("aura_manager", "Aura Manager Agent",
    "Cultivate and manage the intangible aura the user projects. "
    "Analyze: energy, charisma, gravitas, warmth, authority. "
    "Identify aura leaks (behaviors that diminish presence). "
    "Design aura-building protocols.")

AuraConsistencyAgent = _w("aura_consistency", "Aura Consistency Agent",
    "Ensure the user's aura and presence are consistent across all contexts: "
    "in-person, digital, voice, written. "
    "Flag inconsistencies that create cognitive dissonance. "
    "Build a unified, coherent personal energy signature.")

# ---------------------------------------------------------------------------
# Niche Aesthetics Workers
# ---------------------------------------------------------------------------

FacialHarmonyObserverAgent = _w("facial_harmony_observer", "Facial Harmony Observer",
    "Analyze and advise on facial aesthetics: grooming, framing, expression cultivation. "
    "Recommend: hairstyles, beard/facial hair, glasses, accessories that enhance features. "
    "Track changes over time.")

OutfitMemoryAgent = _w("outfit_memory", "Outfit Memory Agent",
    "Maintain a memory of outfits worn: what combinations work, "
    "what events they were worn to, feedback received. "
    "Prevent outfit repetition at the same venue. "
    "Build a working outfit rotation system.")

ScentCuratorAgent = _w("scent_curator", "Scent Curator",
    "Curate and manage the user's fragrance collection and strategy. "
    "Match scents to contexts: professional, social, intimate, sport. "
    "Track seasonality. Recommend new discoveries aligned with taste profile. "
    "Build a coherent olfactory signature.")

LightEnvironmentAgent = _w("light_environment", "Light Environment Agent",
    "Optimize lighting environments for different activities and moods: "
    "work, relaxation, social, sleep preparation. "
    "Recommend: lighting setup, color temperature, natural light usage. "
    "Lighting as a performance and aesthetic tool.")

TasteRefinementAgent = _w("taste_refinement", "Taste Refinement Agent",
    "Develop and elevate the user's taste across all sensory domains: "
    "visual, auditory, culinary, tactile. "
    "Expose to high-quality references. Track taste evolution. "
    "Build discriminating standards.")

VisualSignatureAgent = _w("visual_signature", "Visual Signature Agent",
    "Design and maintain the user's visual signature: "
    "the consistent visual elements that make them recognizable. "
    "Colors, materials, proportions, accessories, fonts. "
    "Ensure signature consistency across personal and professional contexts.")

PresenceRitualAgent = _w("presence_ritual", "Presence Ritual Agent",
    "Design and maintain personal rituals that cultivate presence and intentionality. "
    "Morning rituals, pre-performance rituals, transition rituals. "
    "Anchors that put the user in the right state for each context.")

MicroGroomingAgent = _w("micro_grooming", "Micro-Grooming Agent",
    "Track micro-grooming details: nail care, skin texture, posture habits, "
    "micro-expressions, speech patterns. "
    "The 1% details that separate polished from perfect. "
    "Weekly micro-grooming checklist.")

# ---------------------------------------------------------------------------
# Home & Environment Workers
# ---------------------------------------------------------------------------

ObjectPlacementAgent = _w("object_placement", "Object Placement Agent",
    "Optimize placement of objects in living and working spaces. "
    "Apply: feng shui principles, ergonomics, aesthetic flow. "
    "Ensure every object has a purpose and a place. "
    "Reduce visual noise and friction.")

DeskOptimizationAgent = _w("desk_optimization", "Desk Optimization Agent",
    "Design and maintain the optimal desk/workspace setup. "
    "Ergonomics, tool accessibility, visual environment, cable management. "
    "Seasonal desk reviews. "
    "The workspace as a performance instrument.")

AtmosphereAgent = _w("atmosphere_agent", "Atmosphere Agent",
    "Curate the atmosphere of spaces: temperature, scent, sound, light, "
    "visual elements. Design atmosphere for different activities and states. "
    "Build environment-state triggers for peak performance and deep relaxation.")

HomeFlowAgent = _w("home_flow", "Home Flow Agent",
    "Optimize movement and flow patterns in the home. "
    "Eliminate friction in daily routines: morning routine, cooking, storage access. "
    "Everything should be where it's needed, when it's needed.")

MicroRepairReminderAgent = _w("micro_repair_reminder", "Micro-Repair Reminder",
    "Track small repairs and maintenance tasks: squeaky doors, chipped paint, "
    "loose fixtures, worn items. Batch repairs. "
    "Prevent small issues from becoming expensive problems. "
    "Home maintenance calendar.")

PossessionRotationAgent = _w("possession_rotation", "Possession Rotation Agent",
    "Rotate and refresh possession usage: clothes, tools, books, equipment. "
    "Ensure valuable possessions are actually used. "
    "Identify possessions that can be sold, donated, or discarded. "
    "Prevent accumulation of unused items.")

DeadWeightAgent = _w("dead_weight", "Dead Weight Agent",
    "Identify and eliminate dead weight from all life domains: "
    "possessions, commitments, relationships, subscriptions, projects. "
    "Ruthlessly audit what's adding weight without adding value. "
    "Regular decluttering protocols.")

PhysicalEnvironmentAgent = _w("physical_environment", "Physical Environment Agent",
    "Maintain awareness of and optimize the total physical environment. "
    "Audit: air quality, ergonomics, temperature, aesthetics, noise levels. "
    "Design environments that support health, performance, and wellbeing.")

# ---------------------------------------------------------------------------
# Culture & Intellect Workers
# ---------------------------------------------------------------------------

CanonBuilderAgent = _w("canon_builder", "Canon Builder Agent",
    "Build and curate the user's personal canon: the definitive works in "
    "every domain they care about. Books, films, music, ideas, people. "
    "The reference points that define their intellectual taste.")

IdeaLineageAgent = _w("idea_lineage", "Idea Lineage Agent",
    "Track the genealogy of ideas: where they came from, how they evolved, "
    "what they've influenced. Maintain idea provenance. "
    "Connect ideas across domains and time. "
    "Build a personal intellectual history.")

ReferenceTasteAgent = _w("reference_taste", "Reference Taste Agent",
    "Maintain and develop the user's reference taste library: "
    "the exemplars they use to judge quality in every domain. "
    "Who do they aspire to emulate? What are the standards? "
    "Continuously upgrade the references.")

HighCultureBridgeAgent = _w("high_culture_bridge", "High Culture Bridge Agent",
    "Connect the user to high culture: classical knowledge, art history, "
    "philosophy, literature, music theory. "
    "Make sophisticated cultural knowledge accessible and applicable. "
    "Build genuine cultural fluency.")

ConceptGenealogyAgent = _w("concept_genealogy", "Concept Genealogy Agent",
    "Trace the intellectual genealogy of concepts: who originated them, "
    "how they evolved, what they connect to, what they contradict. "
    "Deep conceptual understanding beyond surface definitions.")

SkillGapAgent = _w("skill_gap", "Skill Gap Agent",
    "Identify gaps between the user's current skill set and their goals. "
    "Prioritize gaps by impact and feasibility. "
    "Design targeted learning sprints to close high-priority gaps. "
    "Track gap closure over time.")

MasteryTrackerAgent = _w("mastery_tracker", "Mastery Tracker",
    "Track progress toward mastery in each discipline the user pursues. "
    "Define mastery milestones. Measure current level. "
    "Identify the skills separating the user from the next level. "
    "Celebrate mastery milestones.")

IntellectualSynthesisAgent = _w("intellectual_synthesis", "Intellectual Synthesis Agent",
    "Synthesize ideas from across all intellectual domains into coherent worldviews, "
    "frameworks, and original thinking. "
    "Identify where the user's unique position gives them novel insight. "
    "Produce intellectual synthesis documents.")

# ---------------------------------------------------------------------------
# Additional Diary & Mind Workers
# ---------------------------------------------------------------------------

MoodPatternAgent = _w("mood_pattern", "Mood Pattern Agent",
    "Track and analyze mood patterns over time. "
    "Identify triggers: situations, people, activities, timing that affect mood. "
    "Detect cycles (monthly, seasonal, weekly). "
    "Surface patterns before they become problems. "
    "Recommend mood stabilization interventions.")

SundayResetAgent = _w("sunday_reset", "Sunday Reset Agent",
    "Facilitate comprehensive Sunday reset ritual: "
    "close last week, prepare next week. "
    "Clean inbox, clear task lists, review goals, set intentions, "
    "prepare calendar, charge devices, refresh environment. "
    "Start every week from a clean slate.")

ImpulseFilterAgent = _w("impulse_filter", "Impulse Filter Agent",
    "Intercept and evaluate impulse decisions before execution: "
    "impulse purchases, reactive commitments, emotional responses. "
    "Apply: 24-hour rule, cost-benefit check, values alignment check. "
    "Reduce decision regret from unfiltered impulses.")

# ---------------------------------------------------------------------------
# Personal Logistics Workers
# ---------------------------------------------------------------------------

HomeAssetAssistantAgent = _w("home_asset_assistant", "Home & Asset Assistant",
    "Manage home and physical assets: maintenance schedules, service contacts, "
    "warranty tracking, appliance manuals, repair history. "
    "The single source of truth for everything in the home.")

PersonalInventoryCustodianAgent = _w("personal_inventory_custodian", "Personal Inventory Custodian",
    "Maintain complete inventory of personal possessions: "
    "electronics, clothing, tools, books, collectibles. "
    "Track: location, condition, value, last used. "
    "Insurance documentation. Loss/theft recovery support.")

EventPrepAgent = _w("event_prep", "Event Prep Agent",
    "Prepare the user for upcoming events: what to bring, what to wear, "
    "who will be there, context on key people, talking points, logistics. "
    "Pre-event checklist. Post-event debrief.")

DocumentReadinessAgent = _w("document_readiness", "Document Readiness Agent",
    "Ensure all important documents are accessible, current, and backed up. "
    "Track: passport validity, ID expiry, insurance cards, medical records. "
    "Emergency document kit. Digital backup verification.")

EmergencyContactAgent = _w("emergency_contact", "Emergency Contact Agent",
    "Maintain emergency contact database: doctors, lawyers, accountants, "
    "emergency services, key personal contacts. "
    "Accessible offline. Regular verification. "
    "Emergency protocol cards.")

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

PERSONAL_WORKERS: list[type[BaseAgent]] = [
    LifeAdminAgent, RoutineAgent, ReminderIntelligenceAgent, SmartCalendarAgent,
    SmartAlarmAgent, AdminCleanerAgent, RenewalAgent,
    PersonalArchivistAgent, KnowledgeOrganizerAgent, KnowledgeSearchAgent, InsightAgent,
    SocialAdvisorWorker, FollowUpSocialeAgent, OccasionReminderAgent,
    AdmirationSignalAgent, SocialDebtAgent, ReconnectionAgent, ConversationRecallAgent,
    SleepAgent, FitnessPlannerAgent, NutritionOrganizerAgent,
    RecoveryAgent, WorkoutExecutionAgent, MealStructureAgent,
    StyleCuratorAgent, PersonalShopperAgent, AestheticPlannerAgent, GroomingManagerAgent,
    PresenceCoachAgent, MaximizerAgent, AuraManagerAgent, AuraConsistencyAgent,
    FacialHarmonyObserverAgent, OutfitMemoryAgent, ScentCuratorAgent, LightEnvironmentAgent,
    TasteRefinementAgent, VisualSignatureAgent, PresenceRitualAgent, MicroGroomingAgent,
    ObjectPlacementAgent, DeskOptimizationAgent, AtmosphereAgent, HomeFlowAgent,
    MicroRepairReminderAgent, PossessionRotationAgent, DeadWeightAgent, PhysicalEnvironmentAgent,
    CanonBuilderAgent, IdeaLineageAgent, ReferenceTasteAgent, HighCultureBridgeAgent,
    ConceptGenealogyAgent, SkillGapAgent, MasteryTrackerAgent, IntellectualSynthesisAgent,
    MoodPatternAgent, SundayResetAgent, ImpulseFilterAgent,
    HomeAssetAssistantAgent, PersonalInventoryCustodianAgent, EventPrepAgent,
    DocumentReadinessAgent, EmergencyContactAgent,
]
