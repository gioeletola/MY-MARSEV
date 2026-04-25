"""Integration layer — connectors to external services."""
from sovereign.integrations.base_integration import BaseIntegration, IntegrationStatus
from sovereign.integrations.integration_manager import IntegrationManager, IntegrationConfig
from sovereign.integrations.email_integration import EmailIntegration
from sovereign.integrations.calendar_integration import CalendarIntegration
from sovereign.integrations.slack_integration import SlackIntegration
from sovereign.integrations.notion_integration import NotionIntegration
from sovereign.integrations.telegram_integration import TelegramIntegration
from sovereign.integrations.telegram_bot import TelegramBot
from sovereign.integrations.crm_integration import CRMIntegration
from sovereign.integrations.analytics_integration import AnalyticsIntegration
from sovereign.integrations.webhook_integration import WebhookIntegration

__all__ = [
    "BaseIntegration", "IntegrationStatus",
    "IntegrationManager", "IntegrationConfig",
    "EmailIntegration", "CalendarIntegration",
    "SlackIntegration", "NotionIntegration",
    "TelegramIntegration", "TelegramBot",
    "CRMIntegration", "AnalyticsIntegration",
    "WebhookIntegration",
]
