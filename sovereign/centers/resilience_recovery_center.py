"""ResilienceRecovery Center — resilience & disaster recovery."""
from sovereign.centers.simple_center import SimpleCenter


class ResilienceRecoveryCenter(SimpleCenter):
    CENTER_ID = 'resilience_recovery_centre'
    DESCRIPTION = 'Resilience & Disaster Recovery'
    PRIMARY_MODE = 'command'
    AGENTS = ['resilience_chief', 'emergency_protocol', 'backup_integrity', 'offline_sync']
    DOMAIN_MAP = {'resilience': 'resilience_chief', 'emergency': 'emergency_protocol', 'backup': 'backup_integrity', 'offline': 'offline_sync', 'recovery': 'resilience_chief'}
    DEFAULT_AGENT = 'resilience_chief'

center = ResilienceRecoveryCenter()
