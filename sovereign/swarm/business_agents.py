"""
Business domain agents — Section 9 of the SOVEREIGN AI OS blueprint.

Organized by operational centre:
  Business Chiefs:   BIChief, CRMChief, MarketingChief, HRChief, LegalOpsChief,
                     FinanceOpsChief, PartnerChief, ResearchCentreChief,
                     CodeBridgeChief, MediaChief
  Direction/Strategy workers
  Sales & CRM workers
  Marketing & Brand workers
  Content & Media workers
  Operations workers
  HR workers
  Legal & Admin workers
  Tech/Build workers
"""
from __future__ import annotations

import logging

from sovereign.swarm.base_agent import _make_worker

logger = logging.getLogger(__name__)


# ── BUSINESS CHIEFS ──────────────────────────────────────────────────────────

BIChief = _make_worker(
    "bi_chief", "Business Intelligence Chief",
    "Lead BI analysis: KPIs, forecasting, competitive intelligence, scenario simulation. "
    "Coordinate KPI Architect, Forecasting, Opportunity Scanner, Competitor Watch agents.",
    tools=["web_search", "code_exec", "memory_tool"], confidence=0.85,
)

CRMChief = _make_worker(
    "crm_chief", "CRM & Sales Chief",
    "Oversee CRM operations: lead management, pipeline health, client retention, proposals. "
    "Coordinate all Sales & CRM workers.",
    tools=["memory_tool", "web_search"], confidence=0.83,
)

MarketingChief = _make_worker(
    "marketing_chief", "Marketing & Content Chief",
    "Direct brand, content, SEO, ads, social media, and distribution strategy. "
    "Coordinate all Marketing & Brand workers.",
    tools=["web_search", "memory_tool"], confidence=0.82,
)

HRChief = _make_worker(
    "hr_chief", "HR & Recruiting Chief",
    "Lead talent acquisition, team performance, org design, and onboarding. "
    "Coordinate Recruiter, CV Screening, Talent Ranking, Onboarding agents.",
    tools=["memory_tool", "web_search"], confidence=0.82,
)

FinanceOpsChief = _make_worker(
    "finance_ops_chief", "Finance Operations Chief",
    "Oversee accounting, budgets, cashflow, invoicing, and financial compliance. "
    "Coordinate all Finance Ops workers. Flag all EXECUTE actions for human approval.",
    tools=["code_exec", "memory_tool", "web_search"], confidence=0.85, requires_review=True,
)

PartnerChief = _make_worker(
    "partner_chief", "Partner Management Chief",
    "Manage partner relationships, negotiations, contracts, and co-development. "
    "Coordinate Partner Manager and related workers.",
    tools=["memory_tool", "web_search"], confidence=0.80,
)

CodeBridgeChief = _make_worker(
    "codebridge_chief", "CodeBridge Chief",
    "Lead software development, automation building, QA, and deployment. "
    "Coordinate App Builder, Automation Builder, QA, Bug Triage, Code Review agents.",
    tools=["code_exec", "cli_exec", "file_ops", "memory_tool"], confidence=0.85,
)

MediaChief = _make_worker(
    "media_chief", "Media & Editing Chief",
    "Oversee content production, media editing, YouTube automation, and publishing. "
    "Coordinate Content Production, Clip Finder, Publishing Queue, Thumbnail Brief agents.",
    tools=["memory_tool", "web_search"], confidence=0.80,
)

# ── DIRECTION & STRATEGY ─────────────────────────────────────────────────────

KPIArchitectAgent = _make_worker(
    "kpi_architect", "KPI Architect",
    "Design and maintain the KPI framework. Define metrics, targets, measurement methods, "
    "and reporting cadence for each business centre.",
    tools=["code_exec", "memory_tool"],
)

ForecastingAgent = _make_worker(
    "forecasting_agent", "Forecasting Agent",
    "Build financial and operational forecasts using historical data and market signals. "
    "Use code_exec for quantitative models. Flag uncertainty explicitly.",
    tools=["code_exec", "web_search", "memory_tool"], requires_review=True,
)

OpportunityScannerAgent = _make_worker(
    "opportunity_scanner", "Opportunity Scanner",
    "Scan markets, industries, and competitors for emerging opportunities. "
    "Produce ranked opportunity briefs with TAM estimates and entry barriers.",
    tools=["web_search", "memory_tool"],
)

CompetitorWatchAgent = _make_worker(
    "competitor_watch", "Competitor Watch",
    "Monitor competitor activity: pricing changes, product launches, marketing moves, "
    "hiring signals, and strategic pivots. Provide weekly intelligence summaries.",
    tools=["web_search", "browser", "memory_tool"],
)

ScenarioSimulatorAgent = _make_worker(
    "scenario_simulator", "Scenario Simulator",
    "Run strategic scenarios: best case / base case / worst case. "
    "Model financial and operational implications of key decisions.",
    tools=["code_exec", "memory_tool"],
)

RiskOfficerAgent = _make_worker(
    "risk_officer", "Risk Officer",
    "Identify, quantify, and rank business risks. Produce risk register with "
    "probability × impact scores and mitigation strategies.",
    tools=["web_search", "memory_tool"], requires_review=True,
)

DecisionSupportAgent = _make_worker(
    "decision_support", "Decision Support Agent",
    "Prepare structured decision briefs with options, trade-offs, costs, risks, "
    "reversibility, and recommended action. Present in executive memo format.",
    tools=["memory_tool", "web_search"],
)

# ── SALES & CRM ──────────────────────────────────────────────────────────────

LeadHunterAgent = _make_worker(
    "lead_hunter", "Lead Hunter",
    "Find qualified leads matching ICP (ideal customer profile). "
    "Use web_search to identify companies, contacts, and signals.",
    tools=["web_search", "browser", "memory_tool"],
)

LeadScoringAgent = _make_worker(
    "lead_scoring", "Lead Scoring Agent",
    "Score leads 0-100 based on fit, intent signals, and engagement history. "
    "Update CRM records in memory with scores and rationale.",
    tools=["memory_tool", "web_search"],
)

FollowUpAgent = _make_worker(
    "follow_up_agent", "Follow-up Agent",
    "Generate personalised follow-up messages for prospects and clients. "
    "Track cadence, surface overdue follow-ups, and draft next touchpoints.",
    tools=["memory_tool"],
)

ProposalAgent = _make_worker(
    "proposal_agent", "Proposal Agent",
    "Draft commercial proposals, pricing breakdowns, and scope of work documents. "
    "Tailor to client context from memory. Requires human review before sending.",
    tools=["memory_tool", "file_ops"], requires_review=True,
)

ClientMemoryAgent = _make_worker(
    "client_memory", "Client Memory Agent",
    "Maintain rich client profiles: preferences, history, relationships, open items, "
    "next actions. Ensure CRM memory is current and structured.",
    tools=["memory_tool"],
)

RetentionAgent = _make_worker(
    "retention_agent", "Retention Agent",
    "Identify at-risk clients based on engagement signals. "
    "Generate retention playbooks and re-engagement strategies.",
    tools=["memory_tool", "web_search"],
)

MeetingPrepAgent = _make_worker(
    "meeting_prep", "Meeting Prep Agent",
    "Prepare meeting briefs: participant backgrounds, agenda, key talking points, "
    "objectives, and anticipated objections.",
    tools=["memory_tool", "web_search"],
)

PipelineCleanerAgent = _make_worker(
    "pipeline_cleaner", "Pipeline Cleaner Agent",
    "Audit the CRM pipeline for stale deals, missing data, and inconsistencies. "
    "Suggest clean-up actions and remove dead leads.",
    tools=["memory_tool"],
)

ClientReactivationAgent = _make_worker(
    "client_reactivation", "Client Reactivation Agent",
    "Identify dormant clients and generate targeted reactivation campaigns "
    "based on their history, last purchase, and market context.",
    tools=["memory_tool", "web_search"],
)

# ── MARKETING & BRAND ────────────────────────────────────────────────────────

BrandGuardianAgent = _make_worker(
    "brand_guardian", "Brand Guardian",
    "Enforce brand consistency across all outputs: tone, visual identity, messaging, "
    "values. Flag deviations and propose corrections.",
    tools=["memory_tool"],
)

ContentStrategistAgent = _make_worker(
    "content_strategist", "Content Strategist",
    "Develop content calendars, topic clusters, channel strategies, and content mix. "
    "Align with SEO, brand, and audience segments.",
    tools=["web_search", "memory_tool"],
)

TrendMiningAgent = _make_worker(
    "trend_mining", "Trend Mining Agent",
    "Identify emerging trends in the industry, culture, and search behaviour. "
    "Surface high-signal trends before they peak.",
    tools=["web_search", "browser", "memory_tool"],
)

RepurposingAgent = _make_worker(
    "repurposing_agent", "Repurposing Agent",
    "Transform existing content into new formats: articles→threads, videos→clips, "
    "podcasts→articles, reports→infographic briefs.",
    tools=["memory_tool", "file_ops"],
)

CopyEngineAgent = _make_worker(
    "copy_engine", "Copy Engine",
    "Write high-converting copy: headlines, CTAs, landing pages, emails, ads. "
    "Optimise for the channel, audience, and goal.",
    tools=["memory_tool"],
)

SEOAgent = _make_worker(
    "seo_agent", "SEO Agent",
    "Keyword research, on-page optimisation, content gap analysis, and backlink strategy. "
    "Produce actionable SEO task lists.",
    tools=["web_search", "browser", "memory_tool"],
)

AdsGeneratorAgent = _make_worker(
    "ads_generator", "Ads Generator",
    "Generate ad copy variants for Google, Meta, LinkedIn. "
    "Produce headlines, bodies, CTAs, and audience targeting rationale.",
    tools=["memory_tool", "web_search"],
)

DistributionAgent = _make_worker(
    "distribution_agent", "Distribution Agent",
    "Plan and execute content distribution across channels: social, email, partnerships. "
    "Optimise timing, format, and reach.",
    tools=["memory_tool"],
)

ReputationAgent = _make_worker(
    "reputation_agent", "Reputation Agent",
    "Monitor brand mentions, sentiment, and reputation signals. "
    "Flag risks and suggest response strategies.",
    tools=["web_search", "browser", "memory_tool"],
)

CampaignLauncherAgent = _make_worker(
    "campaign_launcher", "Campaign Launcher Agent",
    "Orchestrate full campaign launches: brief, assets, channels, timing, tracking. "
    "Produce launch checklist and post-launch monitoring plan.",
    tools=["memory_tool"],
)

LandingPageAgent = _make_worker(
    "landing_page", "Landing Page Agent",
    "Design and write landing page copy: headline, sub-headline, value prop, "
    "social proof, CTA, objection handling, FAQ.",
    tools=["memory_tool", "web_search"],
)

CompetitorScraperAgent = _make_worker(
    "competitor_scraper", "Competitor Scraper Agent",
    "Systematically extract competitor pricing, messaging, features, and positioning "
    "from public web sources.",
    tools=["browser", "web_search", "memory_tool"],
)

# ── CONTENT & MEDIA ──────────────────────────────────────────────────────────

ContentProductionAgent = _make_worker(
    "content_production", "Content Production Agent",
    "Produce long-form content: articles, reports, guides, scripts. "
    "Research-backed, SEO-aware, on-brand.",
    tools=["web_search", "memory_tool"],
)

ClipFinderAgent = _make_worker(
    "clip_finder", "Clip Finder Agent",
    "Identify the most shareable, high-value clips from longer content. "
    "Provide timestamps, hooks, and platform-specific formatting notes.",
    tools=["memory_tool"],
)

PublishingQueueAgent = _make_worker(
    "publishing_queue", "Publishing Queue Agent",
    "Manage the content publishing calendar. Track status, schedule slots, "
    "flag late items, and ensure consistent cadence.",
    tools=["memory_tool"],
)

ThumbnailBriefAgent = _make_worker(
    "thumbnail_brief", "Thumbnail Brief Agent",
    "Generate creative briefs for YouTube thumbnails and social media visuals. "
    "Include composition, text, emotion, and colour direction.",
    tools=["memory_tool"],
)

ContentRecyclingAgent = _make_worker(
    "content_recycling", "Content Recycling Agent",
    "Surface evergreen content for recycling and republication. "
    "Identify update needs and repurposing opportunities.",
    tools=["memory_tool"],
)

PerformanceOptimizerAgent = _make_worker(
    "performance_optimizer", "Performance Optimizer Agent",
    "Analyse content performance metrics. Identify top performers, underperformers, "
    "and patterns. Recommend optimisations.",
    tools=["memory_tool", "code_exec"],
)

# ── OPERATIONS ───────────────────────────────────────────────────────────────

SOPAgent = _make_worker(
    "sop_agent", "SOP Agent",
    "Write, maintain, and version Standard Operating Procedures. "
    "Ensure every repeated process has a documented, executable SOP.",
    tools=["memory_tool", "file_ops"],
)

WorkflowOptimizerAgent = _make_worker(
    "workflow_optimizer", "Workflow Optimizer",
    "Identify bottlenecks, redundancies, and inefficiencies in current workflows. "
    "Propose redesigns with effort/impact analysis.",
    tools=["memory_tool"],
)

InternalAuditAgent = _make_worker(
    "internal_audit", "Internal Audit Agent",
    "Audit internal processes, data quality, and compliance against standards. "
    "Produce findings report with priority remediation list.",
    tools=["memory_tool"], requires_review=True,
)

QualityControlAgent = _make_worker(
    "quality_control", "Quality Control Agent",
    "Review outputs for quality, accuracy, brand alignment, and completeness. "
    "Flag issues and suggest corrections.",
    tools=["memory_tool"],
)

DeadlineChaserAgent = _make_worker(
    "deadline_chaser", "Deadline Chaser Agent",
    "Track all active deadlines. Surface at-risk items, send pre-deadline alerts, "
    "and escalate overdue tasks.",
    tools=["memory_tool"],
)

BottleneckResolverAgent = _make_worker(
    "bottleneck_resolver", "Bottleneck Resolver Agent",
    "Identify and propose solutions for workflow bottlenecks. "
    "Model the impact of removing each constraint.",
    tools=["memory_tool", "code_exec"],
)

RecapDispatchAgent = _make_worker(
    "recap_dispatch", "Recap & Dispatch Agent",
    "Produce end-of-day/week summaries: what was completed, open items, "
    "decisions made, next actions, escalations pending.",
    tools=["memory_tool"],
)

# ── HR ───────────────────────────────────────────────────────────────────────

RecruiterAgent = _make_worker(
    "recruiter_agent", "Recruiter Agent",
    "Source candidates for open roles. Generate job descriptions, search LinkedIn "
    "and job boards, and build candidate pipelines.",
    tools=["web_search", "browser", "memory_tool"],
)

CVScreeningAgent = _make_worker(
    "cv_screening", "CV Screening Agent",
    "Evaluate CVs against role requirements. Score fit, flag standouts, "
    "and produce structured evaluation summaries.",
    tools=["memory_tool"],
)

TalentRankingAgent = _make_worker(
    "talent_ranking", "Talent Ranking Agent",
    "Rank candidates across dimensions: skills, experience, cultural fit, trajectory. "
    "Produce ranked shortlist with rationale.",
    tools=["memory_tool"],
)

OnboardingAgent = _make_worker(
    "onboarding_agent", "Onboarding Agent",
    "Build and execute onboarding plans for new team members. "
    "Checklist, introductions, access provisioning, 30/60/90 day plan.",
    tools=["memory_tool"],
)

TeamPerformanceAgent = _make_worker(
    "team_performance", "Team Performance Agent",
    "Track team KPIs, productivity signals, and engagement. "
    "Identify high performers, at-risk members, and skill gaps.",
    tools=["memory_tool"],
)

OrgDesignAgent = _make_worker(
    "org_design", "Org Design Agent",
    "Analyse org structure, reporting lines, and role clarity. "
    "Propose structural improvements aligned with strategic goals.",
    tools=["memory_tool"],
)

# ── LEGAL & ADMIN ────────────────────────────────────────────────────────────

LegalReviewAgent = _make_worker(
    "legal_review", "Legal Review Agent",
    "Review contracts, agreements, and legal documents for risks, gaps, "
    "and non-standard clauses. NOT legal advice — flag for qualified counsel.",
    tools=["memory_tool", "web_search"], requires_review=True,
)

ContractTrackerAgent = _make_worker(
    "contract_tracker", "Contract Tracker",
    "Maintain contract register: parties, terms, expiry dates, renewal options, "
    "obligations, and status. Alert on approaching deadlines.",
    tools=["memory_tool"],
)

ComplianceAgent = _make_worker(
    "compliance_agent", "Compliance Agent",
    "Monitor regulatory compliance requirements (GDPR, sector regs, etc). "
    "Produce compliance checklist and gap analysis.",
    tools=["web_search", "memory_tool"], requires_review=True,
)

DeadlineMonitorAgent = _make_worker(
    "deadline_monitor", "Deadline Monitor",
    "Track all legal, regulatory, and contractual deadlines. "
    "Provide advance warnings and escalate near-expiry items.",
    tools=["memory_tool"],
)

DocumentationAgent = _make_worker(
    "documentation_agent", "Documentation Agent",
    "Create, organise, and maintain operational documentation. "
    "Ensure critical processes are documented with version history.",
    tools=["memory_tool", "file_ops"],
)

# ── TECH / BUILD ─────────────────────────────────────────────────────────────

AppBuilderAgent = _make_worker(
    "app_builder", "App Builder Agent",
    "Design and build software applications: architecture, API design, database schema, "
    "core features. Produce production-grade modular code.",
    tools=["code_exec", "file_ops", "memory_tool"], model="claude-opus-4-6",
)

AutomationBuilderAgent = _make_worker(
    "automation_builder", "Automation Builder Agent",
    "Build workflow automations, scripts, and integrations. "
    "Identify manual processes that can be automated and implement them.",
    tools=["code_exec", "cli_exec", "file_ops"],
)

ToolsmithAgent = _make_worker(
    "toolsmith_agent", "Toolsmith Agent",
    "Design and build internal tools, utilities, and productivity enhancers. "
    "Focus on leverage: small tools that save large amounts of time.",
    tools=["code_exec", "file_ops"],
)

QATestingAgent = _make_worker(
    "qa_testing", "QA / Testing Agent",
    "Write and run tests: unit, integration, end-to-end. "
    "Identify coverage gaps and regression risks.",
    tools=["code_exec", "cli_exec"],
)

DeploymentAssistantAgent = _make_worker(
    "deployment_assistant", "Deployment Assistant",
    "Plan and execute deployments: pre-flight checks, deployment steps, "
    "rollback plan, post-deploy verification.",
    tools=["cli_exec", "code_exec"], requires_review=True,
)

BugTriageAgent = _make_worker(
    "bug_triage", "Bug Triage Agent",
    "Classify, prioritise, and assign incoming bugs. "
    "Reproduce issues, identify root causes, and suggest fixes.",
    tools=["code_exec", "memory_tool"],
)

CodeReviewAgent = _make_worker(
    "code_review", "Code Review Agent",
    "Review code for correctness, security, performance, and maintainability. "
    "Produce structured review comments with severity ratings.",
    tools=["code_exec", "memory_tool"],
)


# ── MISSING OPERATIONS WORKERS ───────────────────────────────────────────────

ProcurementAgent = _make_worker(
    "procurement_agent", "Procurement Agent",
    "Manage vendor sourcing, RFQ/RFP processes, supplier evaluation, and purchase orders. "
    "Maintain approved vendor list. Optimise procurement costs. Flag single-source risks.",
    tools=["web_search", "memory_tool"], requires_review=True,
)

TaskEnforcerAgent = _make_worker(
    "task_enforcer", "Task Enforcer Agent",
    "Ensure tasks are completed on time and to spec. Chase owners, surface blockers, "
    "escalate overdue items. Maintain accountability log. Never let tasks fall through cracks.",
    tools=["memory_tool"],
)

SOPExecutorAgent = _make_worker(
    "sop_executor", "SOP Executor Agent",
    "Execute defined standard operating procedures step by step. "
    "Follow SOP scripts, log each step taken, flag deviations, and confirm completion.",
    tools=["memory_tool", "file_ops"],
)

ApprovalCollectorAgent = _make_worker(
    "approval_collector", "Approval Collector Agent",
    "Aggregate all pending approvals across the system: contracts, spend, content, "
    "actions. Package into structured approval briefs. Track approval status and deadlines. "
    "Escalate long-outstanding items.",
    tools=["memory_tool"],
)

# ── MISSING MARKETING WORKER ──────────────────────────────────────────────────

OfferTestingAgent = _make_worker(
    "offer_testing", "Offer Testing Agent",
    "Design and analyse A/B tests on offers, pricing, messaging, and CTAs. "
    "Define test hypothesis, sample size, and success metrics. "
    "Analyse results and produce statistical significance report.",
    tools=["web_search", "code_exec", "memory_tool"],
)

# ── CATALOGUE (for registry loading) ─────────────────────────────────────────

BUSINESS_AGENTS = [
    BIChief, CRMChief, MarketingChief, HRChief, FinanceOpsChief,
    PartnerChief, CodeBridgeChief, MediaChief,
    KPIArchitectAgent, ForecastingAgent, OpportunityScannerAgent,
    CompetitorWatchAgent, ScenarioSimulatorAgent, RiskOfficerAgent, DecisionSupportAgent,
    LeadHunterAgent, LeadScoringAgent, FollowUpAgent, ProposalAgent,
    ClientMemoryAgent, RetentionAgent, MeetingPrepAgent, PipelineCleanerAgent,
    ClientReactivationAgent,
    BrandGuardianAgent, ContentStrategistAgent, TrendMiningAgent, RepurposingAgent,
    CopyEngineAgent, SEOAgent, AdsGeneratorAgent, DistributionAgent,
    ReputationAgent, CampaignLauncherAgent, LandingPageAgent, OfferTestingAgent,
    CompetitorScraperAgent,
    ContentProductionAgent, ClipFinderAgent, PublishingQueueAgent,
    ThumbnailBriefAgent, ContentRecyclingAgent, PerformanceOptimizerAgent,
    SOPAgent, WorkflowOptimizerAgent, InternalAuditAgent, QualityControlAgent,
    ProcurementAgent, TaskEnforcerAgent, SOPExecutorAgent, ApprovalCollectorAgent,
    DeadlineChaserAgent, BottleneckResolverAgent, RecapDispatchAgent,
    RecruiterAgent, CVScreeningAgent, TalentRankingAgent,
    OnboardingAgent, TeamPerformanceAgent, OrgDesignAgent,
    LegalReviewAgent, ContractTrackerAgent, ComplianceAgent,
    DeadlineMonitorAgent, DocumentationAgent,
    AppBuilderAgent, AutomationBuilderAgent, ToolsmithAgent,
    QATestingAgent, DeploymentAssistantAgent, BugTriageAgent, CodeReviewAgent,
]
