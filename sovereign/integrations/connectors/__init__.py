"""SOVEREIGN Connector Fabric."""
from sovereign.integrations.connectors.calendar_connector import CalendarConnector
from sovereign.integrations.connectors.connector_base import (
    ConnectorBase,
    ConnectorStatus,
    SyncResult,
)
from sovereign.integrations.connectors.connector_store import ConnectorStore, get_connector_store
from sovereign.integrations.connectors.github_connector import GitHubConnector
from sovereign.integrations.connectors.gmail_connector import GmailConnector
from sovereign.integrations.connectors.hackernews_connector import HackerNewsConnector
from sovereign.integrations.connectors.linear_connector import LinearConnector
from sovereign.integrations.connectors.notion_connector import NotionConnector
from sovereign.integrations.connectors.oauth_manager import OAuthManager, get_oauth_manager
from sovereign.integrations.connectors.rss_connector import RSSConnector
from sovereign.integrations.connectors.slack_connector import SlackConnector
from sovereign.integrations.connectors.sync_engine import SyncEngine, get_sync_engine
from sovereign.integrations.connectors.telegram_connector import TelegramConnector
from sovereign.integrations.connectors.weather_connector import WeatherConnector

__all__ = [
    "ConnectorBase", "ConnectorStatus", "SyncResult",
    "ConnectorStore", "get_connector_store",
    "SyncEngine", "get_sync_engine",
    "OAuthManager", "get_oauth_manager",
    "GitHubConnector", "WeatherConnector", "NotionConnector", "GmailConnector",
    "SlackConnector", "LinearConnector", "RSSConnector",
    "HackerNewsConnector", "CalendarConnector", "TelegramConnector",
]
