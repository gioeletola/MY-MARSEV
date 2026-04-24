"""SOVEREIGN Connector Fabric."""
from sovereign.integrations.connectors.connector_base import ConnectorBase, ConnectorStatus, SyncResult
from sovereign.integrations.connectors.connector_store import ConnectorStore, get_connector_store
from sovereign.integrations.connectors.sync_engine import SyncEngine, get_sync_engine
from sovereign.integrations.connectors.oauth_manager import OAuthManager, get_oauth_manager
from sovereign.integrations.connectors.github_connector import GitHubConnector
from sovereign.integrations.connectors.weather_connector import WeatherConnector
from sovereign.integrations.connectors.notion_connector import NotionConnector
from sovereign.integrations.connectors.gmail_connector import GmailConnector

__all__ = [
    "ConnectorBase", "ConnectorStatus", "SyncResult",
    "ConnectorStore", "get_connector_store",
    "SyncEngine", "get_sync_engine",
    "OAuthManager", "get_oauth_manager",
    "GitHubConnector", "WeatherConnector", "NotionConnector", "GmailConnector",
]
