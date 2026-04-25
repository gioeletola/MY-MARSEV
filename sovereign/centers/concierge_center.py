"""Concierge Center — personal concierge and logistics."""
from sovereign.centers.simple_center import SimpleCenter


class ConciergeCenter(SimpleCenter):
    CENTER_ID = "concierge_centre"
    DESCRIPTION = "Personal Concierge & Logistics"
    PRIMARY_MODE = "personal"
    AGENTS = ["concierge_chief", "travel_planner", "event_prep", "home_asset_assistant", "emergency_contact"]
    DOMAIN_MAP = {"travel": "travel_planner", "event": "event_prep", "home": "home_asset_assistant", "emergency": "emergency_contact"}
    DEFAULT_AGENT = "concierge_chief"

center = ConciergeCenter()
