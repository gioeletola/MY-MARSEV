"""SOVEREIGN Connector Fabric."""
from sovereign.integrations.connectors.airbnb_connector import AirbnbConnector
from sovereign.integrations.connectors.amazon_connector import AmazonConnector
from sovereign.integrations.connectors.calendar_connector import CalendarConnector
from sovereign.integrations.connectors.connector_base import (
    ConnectorBase,
    ConnectorStatus,
    SyncResult,
)
from sovereign.integrations.connectors.connector_store import ConnectorStore, get_connector_store
from sovereign.integrations.connectors.deliveroo_connector import DeliverooConnector
from sovereign.integrations.connectors.edx_connector import EdXConnector
from sovereign.integrations.connectors.etoro_connector import EToroConnector
from sovereign.integrations.connectors.github_connector import GitHubConnector
from sovereign.integrations.connectors.gmail_connector import GmailConnector
from sovereign.integrations.connectors.hackernews_connector import HackerNewsConnector
from sovereign.integrations.connectors.linear_connector import LinearConnector
from sovereign.integrations.connectors.linkedin_connector import LinkedInConnector
from sovereign.integrations.connectors.metatrader_connector import MetaTraderConnector
from sovereign.integrations.connectors.notebooklm_connector import NotebookLMConnector
from sovereign.integrations.connectors.notion_connector import NotionConnector
from sovereign.integrations.connectors.oauth_manager import OAuthManager, get_oauth_manager
from sovereign.integrations.connectors.oopbuy_connector import OopbuyConnector
from sovereign.integrations.connectors.revolut_connector import RevolutConnector
from sovereign.integrations.connectors.rss_connector import RSSConnector
from sovereign.integrations.connectors.slack_connector import SlackConnector
from sovereign.integrations.connectors.sync_engine import SyncEngine, get_sync_engine
from sovereign.integrations.connectors.telegram_connector import TelegramConnector
from sovereign.integrations.connectors.weather_connector import WeatherConnector
from sovereign.integrations.connectors.x_connector import XConnector

__all__ = [
    "ConnectorBase", "ConnectorStatus", "SyncResult",
    "ConnectorStore", "get_connector_store",
    "SyncEngine", "get_sync_engine",
    "OAuthManager", "get_oauth_manager",
    # Original connectors
    "GitHubConnector", "WeatherConnector", "NotionConnector", "GmailConnector",
    "SlackConnector", "LinearConnector", "RSSConnector",
    "HackerNewsConnector", "CalendarConnector", "TelegramConnector",
    # New connectors
    "AirbnbConnector", "LinkedInConnector", "XConnector", "NotebookLMConnector",
    "AmazonConnector", "DeliverooConnector", "MetaTraderConnector",
    "RevolutConnector", "EToroConnector", "EdXConnector", "OopbuyConnector",
]
