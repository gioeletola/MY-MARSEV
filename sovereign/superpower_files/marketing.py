"""Marketing superpower pack — brand, copy, funnels, and growth channels."""
from __future__ import annotations

MARKETING_PACK = {
    "id": "marketing",
    "name": "Marketing Operator",
    "version": "1.0",
    "description": "Brand positioning, copywriting formulas, funnel design, SEO, paid acquisition, retention.",
    "positioning": {
        "category_of_one": "Own a specific niche rather than competing head-on with larger players",
        "positioning_statement": "For [target] who [need], [product] is a [category] that [benefit]. Unlike [competitor], we [key differentiator].",
        "jobs_to_be_done": "People don't buy products; they hire them to do a job. Define the job.",
        "blue_ocean": "Create uncontested market space by redefining the competitive landscape",
    },
    "copywriting_formulas": {
        "AIDA": {
            "description": "Attention → Interest → Desire → Action",
            "steps": [
                "Attention: Bold headline that stops the scroll",
                "Interest: Agitate the pain or amplify the dream",
                "Desire: Stack benefits, social proof, specificity",
                "Action: Clear CTA with urgency or scarcity",
            ],
        },
        "PAS": {
            "description": "Problem → Agitate → Solution",
            "use_case": "Email subject lines, landing pages, ads",
        },
        "4Us": {
            "description": "Useful, Urgent, Unique, Ultra-specific",
            "use_case": "Headlines and subject lines",
        },
        "before_after_bridge": "Show the painful before, the beautiful after, then bridge with your product",
        "so_what_test": "After every benefit statement, ask 'So what?' until you hit an emotional core",
    },
    "funnel_stages": {
        "TOFU": {
            "name": "Top of Funnel — Awareness",
            "channels": ["SEO/Content", "Social media", "Paid reach", "PR/Influencer"],
            "goal": "Make strangers aware of the problem and your existence",
        },
        "MOFU": {
            "name": "Middle of Funnel — Consideration",
            "channels": ["Email sequences", "Webinars", "Case studies", "Retargeting"],
            "goal": "Educate and build trust with problem-aware prospects",
        },
        "BOFU": {
            "name": "Bottom of Funnel — Conversion",
            "channels": ["Free trial", "Demo", "Discount", "Risk reversal"],
            "goal": "Remove barriers and convert intent to purchase",
        },
        "retention": {
            "channels": ["Onboarding", "Success milestones", "Loyalty programs", "Community"],
            "goal": "Maximise LTV and turn customers into advocates",
        },
    },
    "growth_channels": {
        "content_seo": "High-intent search traffic with compounding returns — takes 6-12 months to pay off",
        "paid_social": "Fast feedback loops, precise targeting, but requires budget and creative refresh",
        "viral_loops": "Build sharing into the product (invite mechanism, public output, collaboration)",
        "partnerships": "Tap existing audiences through co-marketing, integrations, affiliate programs",
        "community": "Build the tribe before the product; community compounds like equity",
        "email": "Highest ROI channel — own the list, not rented attention",
        "cold_outbound": "Works at small scale for high-ticket B2B; personalisation is key",
    },
    "metrics": {
        "cac": "Customer Acquisition Cost — total spend / new customers",
        "ltv": "Lifetime Value — ARPU × average lifespan",
        "ltv_cac_ratio": "Target: 3:1 or higher for healthy unit economics",
        "cac_payback": "Months to recover CAC — target <12 months",
        "nps": "Net Promoter Score — promoters (9-10) minus detractors (0-6)",
        "activation_rate": "% new users hitting 'aha moment' in first session",
        "retention_d30": "% users still active 30 days after signup",
    },
    "ad_creative_rules": [
        "Hook in first 3 seconds (video) or 5 words (static)",
        "Show the product in use, not in isolation",
        "Specific numbers beat vague claims ('saves 2h/day' > 'saves time')",
        "Social proof in headline for retargeting audiences",
        "One CTA per creative — never two",
        "Test: hook A/B first, then body, then CTA",
    ],
}


def get_pack() -> dict:
    return MARKETING_PACK


def formula(name: str) -> dict | str | None:
    return MARKETING_PACK["copywriting_formulas"].get(name)


def channel_guide(stage: str) -> dict | None:
    return MARKETING_PACK["funnel_stages"].get(stage.upper())
