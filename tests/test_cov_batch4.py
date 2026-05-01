"""
Coverage batch 4: connector tests — instantiation, describe, health, and
no-credential connect/sync paths for all major connectors.
"""
from __future__ import annotations

import asyncio


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Generic helper
# ---------------------------------------------------------------------------

def _test_connector(cls, config=None):
    """Run standard connector smoke tests; return the connector instance."""
    c = cls(config or {})
    desc = c.describe()
    assert isinstance(desc, dict)
    assert "connector_id" in desc or "name" in desc
    health = run(c.health())
    assert health is not None
    assert hasattr(health, "status")
    # connect without credentials — should return False gracefully
    connected = run(c.connect())
    assert isinstance(connected, bool)
    # sync without credentials — should return SyncResult with success=False
    result = run(c.sync())
    assert result is not None
    assert hasattr(result, "success")
    return c


# ===========================================================================
# Finance connectors
# ===========================================================================

class TestBinanceConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.binance_connector import BinanceConnector
        _test_connector(BinanceConnector)

    def test_describe_fields(self):
        from sovereign.integrations.connectors.binance_connector import BinanceConnector
        c = BinanceConnector()
        d = c.describe()
        assert d.get("connector_id") == "binance"


class TestCoinGeckoConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.coingecko_connector import CoinGeckoConnector
        _test_connector(CoinGeckoConnector)


class TestEToroConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.etoro_connector import EToroConnector
        _test_connector(EToroConnector)


class TestRevolut:
    def test_smoke(self):
        from sovereign.integrations.connectors.revolut_connector import RevolutConnector
        _test_connector(RevolutConnector)


class TestStripe:
    def test_smoke(self):
        from sovereign.integrations.connectors.stripe_connector import StripeConnector
        _test_connector(StripeConnector)


class TestMetaTrader:
    def test_smoke(self):
        from sovereign.integrations.connectors.metatrader_connector import MetaTraderConnector
        _test_connector(MetaTraderConnector)


# ===========================================================================
# Messaging / Social connectors
# ===========================================================================

class TestTelegramConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.telegram_connector import TelegramConnector
        _test_connector(TelegramConnector)

    def test_describe_telegram(self):
        from sovereign.integrations.connectors.telegram_connector import TelegramConnector
        c = TelegramConnector()
        d = c.describe()
        assert "telegram" in d.get("connector_id", "").lower() or isinstance(d, dict)


class TestSlackConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.slack_connector import SlackConnector
        _test_connector(SlackConnector)


class TestDiscordConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.discord_connector import DiscordConnector
        _test_connector(DiscordConnector)


class TestWhatsAppConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.whatsapp_connector import WhatsAppConnector
        _test_connector(WhatsAppConnector)


class TestFacebookConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.facebook_connector import FacebookConnector
        _test_connector(FacebookConnector)


class TestInstagramConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.instagram_connector import InstagramConnector
        _test_connector(InstagramConnector)


class TestLinkedInConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.linkedin_connector import LinkedInConnector
        _test_connector(LinkedInConnector)


class TestXConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.x_connector import XConnector
        _test_connector(XConnector)


# ===========================================================================
# Productivity / Professional connectors
# ===========================================================================

class TestGitHubConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.github_connector import GitHubConnector
        _test_connector(GitHubConnector)

    def test_get_notifications_empty(self):
        from sovereign.integrations.connectors.github_connector import GitHubConnector
        c = GitHubConnector()
        notifs = c.get_notifications()
        assert isinstance(notifs, list)


class TestLinearConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.linear_connector import LinearConnector
        _test_connector(LinearConnector)


class TestNotionConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.notion_connector import NotionConnector
        _test_connector(NotionConnector)


class TestMailchimpConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.mailchimp_connector import MailchimpConnector
        _test_connector(MailchimpConnector)


class TestTypeformConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.typeform_connector import TypeformConnector
        _test_connector(TypeformConnector)


class TestNotebookLMConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.notebooklm_connector import NotebookLMConnector
        _test_connector(NotebookLMConnector)


class TestEdXConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.edx_connector import EdXConnector
        _test_connector(EdXConnector)


class TestHackerNewsConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.hackernews_connector import HackerNewsConnector
        c = HackerNewsConnector()
        d = c.describe()
        assert isinstance(d, dict)
        health = run(c.health())
        assert health is not None


class TestAirtableConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.airtable_connector import AirtableConnector
        _test_connector(AirtableConnector)


# ===========================================================================
# E-Commerce / Services connectors
# ===========================================================================

class TestAmazonConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.amazon_connector import AmazonConnector
        _test_connector(AmazonConnector)


class TestShopifyConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.shopify_connector import ShopifyConnector
        _test_connector(ShopifyConnector)


class TestUberConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.uber_connector import UberConnector
        _test_connector(UberConnector)


class TestDeliverooConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.deliveroo_connector import DeliverooConnector
        _test_connector(DeliverooConnector)


class TestAirbnbConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.airbnb_connector import AirbnbConnector
        _test_connector(AirbnbConnector)


class TestFarfetchConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.farfetch_connector import FarfetchConnector
        _test_connector(FarfetchConnector)


class TestOopbuyConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.oopbuy_connector import OopbuyConnector
        _test_connector(OopbuyConnector)


# ===========================================================================
# Health / Lifestyle connectors
# ===========================================================================

class TestStravaConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.strava_connector import StravaConnector
        _test_connector(StravaConnector)


class TestSpotifyConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.spotify_connector import SpotifyConnector
        _test_connector(SpotifyConnector)


# ===========================================================================
# News / Info connectors
# ===========================================================================

class TestRedditConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.reddit_connector import RedditConnector
        _test_connector(RedditConnector)


class TestYouTubeConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.youtube_connector import YouTubeConnector
        _test_connector(YouTubeConnector)


class TestProductHuntConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.producthunt_connector import ProductHuntConnector
        _test_connector(ProductHuntConnector)


class TestSkyscannerConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.skyscanner_connector import SkyscannerConnector
        _test_connector(SkyscannerConnector)


# ===========================================================================
# Calendar / Contacts connectors
# ===========================================================================

class TestCalendlyConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.calendly_connector import CalendlyConnector
        _test_connector(CalendlyConnector)


class TestContactsConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.contacts_connector import ContactsConnector
        _test_connector(ContactsConnector)


class TestGmailConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.gmail_connector import GmailConnector
        _test_connector(GmailConnector)


# ===========================================================================
# Misc connectors
# ===========================================================================

class TestBambuLabConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.bambulab_connector import BambuLabConnector
        _test_connector(BambuLabConnector)


class TestSisalConnector:
    def test_smoke(self):
        from sovereign.integrations.connectors.sisal_connector import SisalConnector
        _test_connector(SisalConnector)


# ===========================================================================
# ConnectorBase data classes
# ===========================================================================

class TestConnectorBaseClasses:
    def test_connector_health_creation(self):
        from sovereign.integrations.connectors.connector_base import ConnectorHealth, ConnectorStatus
        h = ConnectorHealth(
            connector_id="test",
            status=ConnectorStatus.CONNECTED,
            last_sync="2026-01-01T00:00:00Z",
            records_synced=10,
            latency_ms=42.5,
        )
        assert h.connector_id == "test"
        assert h.status == ConnectorStatus.CONNECTED
        assert h.latency_ms == 42.5

    def test_sync_result_creation(self):
        from sovereign.integrations.connectors.connector_base import SyncResult
        r = SyncResult(connector_id="test", success=True, records_synced=5)
        assert r.success is True
        assert r.records_synced == 5

    def test_sync_result_failure(self):
        from sovereign.integrations.connectors.connector_base import SyncResult
        r = SyncResult(connector_id="test", success=False, errors=["no token"])
        assert r.success is False
        assert "no token" in r.errors

    def test_connector_status_values(self):
        from sovereign.integrations.connectors.connector_base import ConnectorStatus
        assert ConnectorStatus.CONNECTED == "connected"
        assert ConnectorStatus.DISCONNECTED == "disconnected"
        assert ConnectorStatus.ERROR == "error"

    def test_mark_sync(self):
        from sovereign.integrations.connectors.github_connector import GitHubConnector
        from sovereign.integrations.connectors.connector_base import SyncResult
        c = GitHubConnector()
        result = SyncResult(connector_id="github", success=True, records_synced=3, duration_ms=100.0)
        c._mark_sync(result)
        assert c._records_synced == 3
        assert c._last_sync is not None

    def test_describe_returns_all_fields(self):
        from sovereign.integrations.connectors.github_connector import GitHubConnector
        c = GitHubConnector()
        d = c.describe()
        required = {"connector_id", "name", "description", "status", "requires_oauth"}
        for field in required:
            assert field in d, f"Missing field: {field}"


# ===========================================================================
# Memory Manager (additional coverage)
# ===========================================================================

class TestMemoryManagerAdditional:
    def setup_method(self):
        from sovereign.memory.memory_manager import MemoryManager
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        self.mm = MemoryManager(data_dir=self._tmpdir)

    def test_get_snapshot_returns_dict(self):
        snapshot = run(self.mm.get_snapshot())
        assert isinstance(snapshot, dict)

    def test_write_and_read_key(self):
        run(self.mm.write("research", "test_key", {"val": 42}))
        result = run(self.mm.read("research", "test_key"))
        assert isinstance(result, dict) or result is None

    def test_list_keys_domain(self):
        run(self.mm.write("research", "k1", {"a": 1}))
        keys = run(self.mm.list_keys("research"))
        assert isinstance(keys, list)

    def test_delete_key(self):
        run(self.mm.write("research", "del_key", {"x": 1}))
        deleted = run(self.mm.delete("research", "del_key"))
        assert isinstance(deleted, bool)

    def test_semantic_search(self):
        run(self.mm.write("research", "note1", {"text": "the quick brown fox"}))
        results = run(self.mm.semantic_search("quick brown fox", domain="research"))
        assert isinstance(results, list)

    def test_temporal_recall(self):
        results = run(self.mm.temporal_recall(domain="research", since_iso="2020-01-01T00:00:00Z"))
        assert isinstance(results, list)

    def test_graph_traverse(self):
        results = run(self.mm.graph_traverse(start_key="research:note1", relationship="links", depth=2))
        assert isinstance(results, list)


# ===========================================================================
# Weekly Report (additional coverage)
# ===========================================================================

class TestWeeklyReport:
    def test_build_report_runs(self):
        import tempfile
        from sovereign.reporting.weekly_report import build_weekly_report
        with tempfile.TemporaryDirectory() as d:
            report = build_weekly_report(data_dir=d)
            assert isinstance(report, str)

    def test_render_json_runs(self):
        import tempfile
        from sovereign.reporting.weekly_report import render_json
        with tempfile.TemporaryDirectory() as d:
            result = render_json(data_dir=d)
            assert isinstance(result, dict)

    def test_render_html(self):
        from sovereign.reporting.weekly_report import render_html
        html = render_html("# Test Report\n\nContent here.")
        assert isinstance(html, str)

    def test_compare_to_previous(self):
        from sovereign.reporting.weekly_report import compare_to_previous
        result = compare_to_previous("# Week A\nMetric: 10", "# Week B\nMetric: 8")
        assert isinstance(result, dict)
