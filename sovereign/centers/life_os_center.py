"""LifeOS Center — life operating system & personal administration."""
from sovereign.centers.simple_center import SimpleCenter


class LifeOSCenter(SimpleCenter):
    CENTER_ID = "life_os_centre"
    DESCRIPTION = "Life Operating System"
    PRIMARY_MODE = "personal"
    AGENTS = [
        "life_os_chief", "life_admin", "routine_agent", "energy_manager",
        "habit_engineer", "reminder_intelligence", "smart_calendar",
        "smart_alarm", "errand_coordinator", "admin_cleaner",
        "renewal_agent", "subscription_manager",
    ]
    DOMAIN_MAP = {
        "habit": "habit_engineer",
        "routine": "routine_agent",
        "calendar": "smart_calendar",
        "schedule": "smart_calendar",
        "reminder": "reminder_intelligence",
        "alarm": "smart_alarm",
        "energy": "energy_manager",
        "subscription": "subscription_manager",
        "errand": "errand_coordinator",
        "admin": "admin_cleaner",
        "renewal": "renewal_agent",
        "life": "life_os_chief",
    }
    DEFAULT_AGENT = "life_os_chief"
    CAPABILITIES = [
        "Daily routine design: morning/evening protocols optimised for energy",
        "Smart calendar: time-block scheduling and context-aware rescheduling",
        "Habit engineering: streak tracking, cue-routine-reward design",
        "Energy management: ultradian rhythm alignment and recovery scheduling",
        "Admin cleaner: triage inbox, cancel unused subscriptions, renew documents",
        "Reminder intelligence: priority-weighted, context-aware nudges",
        "Errand coordination: batching, routing, and delegation",
    ]


center = LifeOSCenter()
