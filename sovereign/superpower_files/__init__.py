"""
Superpower Files — 8 sovereign knowledge packs.

Each pack is a structured knowledge base injected into agent system prompts
to give specialised domain expertise without runtime API calls.

Packs:
  negotiation     — negotiation tactics, BATNA, anchoring
  fundraising     — VC dynamics, pitch structure, term sheets
  product         — PM frameworks, PRDs, user research
  growth          — growth loops, acquisition channels, retention
  legal_basics    — contract red flags, IP protection, compliance checklist
  mental_models   — 50 core decision-making frameworks
  financial_iq    — financial literacy, ratios, valuation methods
  leadership      — leadership principles, hiring, team dynamics
"""
from sovereign.superpower_files.loader import SuperpowerLoader

__all__ = ["SuperpowerLoader"]
