"""LifeOs Center — life operating system."""
from sovereign.centers.simple_center import SimpleCenter

class LifeOSCenter(SimpleCenter):
    CENTER_ID = 'life_os_centre'
    DESCRIPTION = 'Life Operating System'
    PRIMARY_MODE = 'personal'
    AGENTS = ['life_os_chief', 'life_admin', 'routine_agent', 'energy_manager', 'habit_engineer', 'reminder_intelligence', 'smart_calendar', 'smart_alarm', 'errand_coordinator', 'admin_cleaner', 'renewal_agent', 'subscription_manager']
    DOMAIN_MAP = {'habit': 'habit_engineer', 'routine': 'routine_agent', 'calendar': 'smart_calendar', 'reminder': 'reminder_intelligence', 'energy': 'energy_manager', 'subscription': 'subscription_manager', 'errand': 'errand_coordinator', 'admin': 'admin_cleaner'}
    DEFAULT_AGENT = 'life_os_chief'

center = LifeOSCenter()
