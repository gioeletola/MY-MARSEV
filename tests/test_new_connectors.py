"""Tests for the 6 new connectors: Slack, Linear, RSS, HackerNews, Calendar, Telegram."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sovereign.integrations.connectors.connector_base import ConnectorStatus, SyncResult
from sovereign.integrations.connectors.slack_connector import SlackConnector
from sovereign.integrations.connectors.linear_connector import LinearConnector
from sovereign.integrations.connectors.rss_connector import RSSConnector
from sovereign.integrations.connectors.hackernews_connector import HackerNewsConnector
from sovereign.integrations.connectors.calendar_connector import CalendarConnector
from sovereign.integrations.connectors.telegram_connector import TelegramConnector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# SlackConnector
# ---------------------------------------------------------------------------

class TestSlackConnector:
    def test_no_token_connect_returns_false(self):
        c = SlackConnector()
        assert run(c.connect()) is False

    def test_describe_includes_connector_id(self):
        c = SlackConnector()
        d = c.describe()
        assert d["connector_id"] == "slack"
        assert d["requires_oauth"] is True

    def test_sync_without_token_returns_failure(self):
        c = SlackConnector()
        result = run(c.sync())
        assert isinstance(result, SyncResult)
        assert result.success is False

    def test_disconnect_clears_messages(self):
        c = SlackConnector()
        c._messages = [{"text": "hello"}]
        run(c.disconnect())
        assert c._messages == []
        assert c.connector_status == ConnectorStatus.DISCONNECTED

    def test_get_messages_empty_initially(self):
        c = SlackConnector()
        assert c.get_messages() == []


# ---------------------------------------------------------------------------
# LinearConnector
# ---------------------------------------------------------------------------

class TestLinearConnector:
    def test_no_key_connect_returns_false(self):
        c = LinearConnector()
        assert run(c.connect()) is False

    def test_describe(self):
        c = LinearConnector()
        d = c.describe()
        assert d["connector_id"] == "linear"
        assert "Linear" in d["name"]

    def test_sync_without_key_returns_failure(self):
        c = LinearConnector()
        result = run(c.sync())
        assert result.success is False
        assert "No API key" in result.errors[0]

    def test_get_issues_empty_initially(self):
        c = LinearConnector()
        assert c.get_issues() == []


# ---------------------------------------------------------------------------
# RSSConnector
# ---------------------------------------------------------------------------

class TestRSSConnector:
    def test_connect_no_urls_still_succeeds(self):
        c = RSSConnector()
        assert run(c.connect()) is True
        assert c.connector_status == ConnectorStatus.CONNECTED

    def test_sync_no_urls_returns_failure(self):
        c = RSSConnector()
        result = run(c.sync())
        assert result.success is False
        assert "No feed_urls" in result.errors[0]

    def test_add_feed(self):
        c = RSSConnector({"feed_urls": []})
        c.add_feed("https://example.com/feed.xml")
        assert "https://example.com/feed.xml" in c._feed_urls

    def test_add_feed_no_duplicate(self):
        c = RSSConnector({"feed_urls": ["https://example.com/feed.xml"]})
        c.add_feed("https://example.com/feed.xml")
        assert c._feed_urls.count("https://example.com/feed.xml") == 1

    def test_parse_rss_feed(self):
        xml = """<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>Test Story</title>
              <link>https://example.com/story</link>
              <pubDate>Fri, 25 Apr 2026 12:00:00 GMT</pubDate>
              <description>A test story.</description>
            </item>
          </channel>
        </rss>"""
        c = RSSConnector()
        entries = c._parse_feed(xml, "https://example.com/feed.xml")
        assert len(entries) == 1
        assert entries[0]["title"] == "Test Story"
        assert entries[0]["feed_type"] == "rss"

    def test_parse_atom_feed(self):
        xml = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Atom Entry</title>
            <link href="https://example.com/atom-entry"/>
            <published>2026-04-25T12:00:00Z</published>
            <summary>Summary text.</summary>
          </entry>
        </feed>"""
        c = RSSConnector()
        entries = c._parse_feed(xml, "https://example.com/atom.xml")
        assert len(entries) == 1
        assert entries[0]["title"] == "Atom Entry"
        assert entries[0]["feed_type"] == "atom"

    def test_parse_invalid_xml_returns_empty(self):
        c = RSSConnector()
        entries = c._parse_feed("not xml at all <<<", "http://bad.com")
        assert entries == []

    def test_health_reports_feed_count(self):
        c = RSSConnector({"feed_urls": ["a", "b", "c"]})
        h = run(c.health())
        assert h.metadata["feed_count"] == 3


# ---------------------------------------------------------------------------
# HackerNewsConnector
# ---------------------------------------------------------------------------

class TestHackerNewsConnector:
    def test_connect_always_true(self):
        c = HackerNewsConnector()
        assert run(c.connect()) is True

    def test_describe(self):
        c = HackerNewsConnector()
        d = c.describe()
        assert d["connector_id"] == "hackernews"

    def test_top_titles_empty_initially(self):
        c = HackerNewsConnector()
        assert c.top_titles() == []

    def test_config_story_count(self):
        c = HackerNewsConnector({"story_count": 10})
        assert c._story_count == 10

    def test_config_fetch_types(self):
        c = HackerNewsConnector({"fetch_types": ["topstories"]})
        assert c._fetch_types == ["topstories"]

    def test_health_metadata(self):
        c = HackerNewsConnector({"story_count": 20})
        h = run(c.health())
        assert h.metadata["story_count"] == 20

    def test_disconnect_clears_stories(self):
        c = HackerNewsConnector()
        c._stories = [{"id": 1, "title": "Test"}]
        run(c.disconnect())
        assert c._stories == []


# ---------------------------------------------------------------------------
# CalendarConnector
# ---------------------------------------------------------------------------

class TestCalendarConnector:
    def test_no_token_no_ics_connect_false(self):
        c = CalendarConnector()
        assert run(c.connect()) is False

    def test_describe(self):
        c = CalendarConnector()
        d = c.describe()
        assert d["connector_id"] == "calendar"
        assert d["requires_oauth"] is True

    def test_sync_no_token_returns_failure(self):
        c = CalendarConnector()
        result = run(c.sync())
        assert result.success is False

    def test_ics_connect_if_file_exists(self, tmp_path):
        ics = tmp_path / "test.ics"
        ics.write_text("BEGIN:VCALENDAR\nEND:VCALENDAR")
        c = CalendarConnector({"ics_path": str(ics)})
        assert run(c.connect()) is True

    def test_ics_sync(self, tmp_path):
        ics = tmp_path / "cal.ics"
        ics.write_text(
            "BEGIN:VCALENDAR\n"
            "BEGIN:VEVENT\n"
            "SUMMARY:Team Meeting\n"
            "DTSTART:20260425T100000Z\n"
            "DTEND:20260425T110000Z\n"
            "UID:abc123\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )
        c = CalendarConnector({"ics_path": str(ics)})
        result = run(c.sync())
        assert result.success is True
        assert result.records_synced == 1
        assert c.get_events()[0]["summary"] == "Team Meeting"

    def test_upcoming_titles_empty_initially(self):
        c = CalendarConnector()
        assert c.upcoming_titles() == []

    def test_health_metadata(self):
        c = CalendarConnector({"days_ahead": 14})
        h = run(c.health())
        assert h.metadata["days_ahead"] == 14


# ---------------------------------------------------------------------------
# TelegramConnector
# ---------------------------------------------------------------------------

class TestTelegramConnector:
    def test_no_token_connect_false(self):
        c = TelegramConnector()
        assert run(c.connect()) is False

    def test_describe(self):
        c = TelegramConnector()
        d = c.describe()
        assert d["connector_id"] == "telegram"
        assert d["requires_oauth"] is False

    def test_sync_no_token_failure(self):
        c = TelegramConnector()
        result = run(c.sync())
        assert result.success is False

    def test_get_messages_empty_initially(self):
        c = TelegramConnector()
        assert c.get_messages() == []

    def test_clear_messages(self):
        c = TelegramConnector()
        c._messages = [{"text": "hi"}]
        c.clear_messages()
        assert c._messages == []

    def test_disconnect_resets_offset(self):
        c = TelegramConnector()
        c._offset = 42
        run(c.disconnect())
        assert c._offset == 0

    def test_health_includes_offset(self):
        c = TelegramConnector()
        c._offset = 99
        h = run(c.health())
        assert h.metadata["offset"] == 99

    def test_allowed_chat_ids_config(self):
        c = TelegramConnector({"allowed_chat_ids": [12345, 67890]})
        assert 12345 in c._allowed_chat_ids


# ---------------------------------------------------------------------------
# Connector __init__ exports
# ---------------------------------------------------------------------------

class TestConnectorExports:
    def test_all_new_connectors_importable(self):
        from sovereign.integrations.connectors import (
            SlackConnector, LinearConnector, RSSConnector,
            HackerNewsConnector, CalendarConnector, TelegramConnector,
        )
        assert SlackConnector.connector_id == "slack"
        assert LinearConnector.connector_id == "linear"
        assert RSSConnector.connector_id == "rss"
        assert HackerNewsConnector.connector_id == "hackernews"
        assert CalendarConnector.connector_id == "calendar"
        assert TelegramConnector.connector_id == "telegram"
