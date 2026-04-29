"""SOVEREIGN Connector Fabric."""
from sovereign.integrations.connectors.airtable_connector import AirtableConnector
from sovereign.integrations.connectors.airbnb_connector import AirbnbConnector
from sovereign.integrations.connectors.amazon_connector import AmazonConnector
from sovereign.integrations.connectors.bambulab_connector import BambuLabConnector
from sovereign.integrations.connectors.binance_connector import BinanceConnector
from sovereign.integrations.connectors.calendar_connector import CalendarConnector
from sovereign.integrations.connectors.calendly_connector import CalendlyConnector
from sovereign.integrations.connectors.coingecko_connector import CoinGeckoConnector
from sovereign.integrations.connectors.connector_base import (
    ConnectorBase,
    ConnectorStatus,
    SyncResult,
)
from sovereign.integrations.connectors.connector_store import ConnectorStore, get_connector_store
from sovereign.integrations.connectors.contacts_connector import ContactsConnector
from sovereign.integrations.connectors.deliveroo_connector import DeliverooConnector
from sovereign.integrations.connectors.discord_connector import DiscordConnector
from sovereign.integrations.connectors.edx_connector import EdXConnector
from sovereign.integrations.connectors.etoro_connector import EToroConnector
from sovereign.integrations.connectors.facebook_connector import FacebookConnector
from sovereign.integrations.connectors.farfetch_connector import FarfetchConnector
from sovereign.integrations.connectors.github_connector import GitHubConnector
from sovereign.integrations.connectors.gmail_connector import GmailConnector
from sovereign.integrations.connectors.hackernews_connector import HackerNewsConnector
from sovereign.integrations.connectors.instagram_connector import InstagramConnector
from sovereign.integrations.connectors.linear_connector import LinearConnector
from sovereign.integrations.connectors.linkedin_connector import LinkedInConnector
from sovereign.integrations.connectors.mailchimp_connector import MailchimpConnector
from sovereign.integrations.connectors.metatrader_connector import MetaTraderConnector
from sovereign.integrations.connectors.notebooklm_connector import NotebookLMConnector
from sovereign.integrations.connectors.notion_connector import NotionConnector
from sovereign.integrations.connectors.oauth_manager import OAuthManager, get_oauth_manager
from sovereign.integrations.connectors.oopbuy_connector import OopbuyConnector
from sovereign.integrations.connectors.revolut_connector import RevolutConnector
from sovereign.integrations.connectors.rss_connector import RSSConnector
from sovereign.integrations.connectors.shopify_connector import ShopifyConnector
from sovereign.integrations.connectors.sisal_connector import SisalConnector
from sovereign.integrations.connectors.skyscanner_connector import SkyscannerConnector
from sovereign.integrations.connectors.slack_connector import SlackConnector
from sovereign.integrations.connectors.spotify_connector import SpotifyConnector
from sovereign.integrations.connectors.strava_connector import StravaConnector
from sovereign.integrations.connectors.stripe_connector import StripeConnector
from sovereign.integrations.connectors.sync_engine import SyncEngine, get_sync_engine
from sovereign.integrations.connectors.telegram_connector import TelegramConnector
from sovereign.integrations.connectors.typeform_connector import TypeformConnector
from sovereign.integrations.connectors.uber_connector import UberConnector
from sovereign.integrations.connectors.weather_connector import WeatherConnector
from sovereign.integrations.connectors.whatsapp_connector import WhatsAppConnector
from sovereign.integrations.connectors.x_connector import XConnector
from sovereign.integrations.connectors.youtube_connector import YouTubeConnector
from sovereign.integrations.connectors.reddit_connector import RedditConnector
from sovereign.integrations.connectors.producthunt_connector import ProductHuntConnector

__all__ = [
    "ConnectorBase", "ConnectorStatus", "SyncResult",
    "ConnectorStore", "get_connector_store",
    "SyncEngine", "get_sync_engine",
    "OAuthManager", "get_oauth_manager",
    # Originals
    "GitHubConnector", "WeatherConnector", "NotionConnector", "GmailConnector",
    "SlackConnector", "LinearConnector", "RSSConnector",
    "HackerNewsConnector", "CalendarConnector", "TelegramConnector",
    # Phase-2 connectors
    "AirbnbConnector", "LinkedInConnector", "XConnector", "NotebookLMConnector",
    "AmazonConnector", "DeliverooConnector", "MetaTraderConnector",
    "RevolutConnector", "EToroConnector", "EdXConnector", "OopbuyConnector",
    # Phase-3 connectors
    "InstagramConnector", "FacebookConnector", "FarfetchConnector",
    "ContactsConnector", "BambuLabConnector", "UberConnector", "SkyscannerConnector",
    "SisalConnector", "BinanceConnector", "MailchimpConnector",
    "StripeConnector", "DiscordConnector", "ShopifyConnector",
    "SpotifyConnector", "StravaConnector", "CoinGeckoConnector",
    "AirtableConnector", "TypeformConnector", "WhatsAppConnector", "CalendlyConnector",
    # Phase-4 connectors
    "YouTubeConnector", "RedditConnector", "ProductHuntConnector",
]
