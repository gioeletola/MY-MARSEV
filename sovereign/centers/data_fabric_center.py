"""DataFabric Center — data fabric & ingestion."""
from sovereign.centers.simple_center import SimpleCenter


class DataFabricCenter(SimpleCenter):
    CENTER_ID = 'data_fabric_centre'
    DESCRIPTION = 'Data Fabric & Ingestion'
    PRIMARY_MODE = 'command'
    AGENTS = ['freshness_agent', 'trust_scoring_agent', 'anti_chaos']
    DOMAIN_MAP = {'freshness': 'freshness_agent', 'trust': 'trust_scoring_agent', 'chaos': 'anti_chaos', 'data': 'freshness_agent', 'ingestion': 'freshness_agent'}
    DEFAULT_AGENT = 'freshness_agent'

center = DataFabricCenter()
