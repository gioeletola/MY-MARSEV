"""Superpower pack: growth strategy, acquisition, retention."""

PACK = {
    "title": "Growth Mastery",
    "version": "1.0",
    "sections": {
        "Growth Loops": [
            "Viral loop: product use generates new invitations (Slack, Dropbox referrals)",
            "Content loop: content drives SEO → signups → more content creation",
            "Paid loop: paid acquisition → revenue → reinvest in more paid acquisition",
            "Community loop: users create community → community attracts users",
            "Product-led loop: free tier converts to paid; paid users expand organically",
        ],
        "Acquisition Channels": {
            "SEO/Content": "Highest LTV, slowest to build, compounds forever — prioritise early",
            "Paid (SEM/Social)": "Fastest to test; stops immediately when spend stops",
            "Product-led (PLG)": "Free trial / freemium; CAC near zero; requires self-serve onboarding",
            "Outbound sales": "Direct for enterprise; expensive; needs ICP definition",
            "Partnerships": "Co-marketing, integrations, channel — leverage existing distribution",
            "Community": "Developer evangelism, Discord, Reddit — high trust, slow to build",
        },
        "Retention Framework": {
            "Onboarding": "Get users to the 'aha moment' in < 5 minutes",
            "Habit formation": "Design for daily/weekly use; build hooks into workflow",
            "Email/notifications": "Behaviour-triggered > scheduled; be useful not annoying",
            "NPS": "Net Promoter Score: Promoters - Detractors; > 50 is strong",
            "Cohort analysis": "Track retention by acquisition cohort; reveals true product-market fit",
            "Win-back campaigns": "Segment churned users by reason; personalise re-engagement",
        },
        "Unit Economics": {
            "CAC": "Total sales + marketing spend / new customers acquired",
            "LTV": "Average revenue per user × gross margin × average customer lifetime",
            "LTV:CAC": "> 3:1 for healthy growth; > 5:1 for efficient growth",
            "Payback period": "CAC / (MRR × gross margin) — should be < 12 months",
            "Contribution margin": "Revenue - variable costs per unit — must be positive to scale",
        },
        "Growth Experiments": [
            "Hypothesis-first: state expected effect before running test",
            "One variable at a time — otherwise you cannot attribute causality",
            "Minimum sample size calculator before starting — avoid underpowered tests",
            "Prioritise tests by expected lift × confidence × reversibility",
            "Run experiments in parallel with feature flags to maintain velocity",
            "Document all results including failures — institutional memory prevents repeats",
        ],
    },
}
