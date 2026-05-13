"""Tests for connector write operations (Gmail send, Calendar write, Notion write)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGmailWrite:
    @pytest.mark.asyncio
    async def test_send_email_no_token(self):
        from sovereign.integrations.connectors.gmail_connector import GmailConnector

        c = GmailConnector({"access_token": ""})
        result = await c.send_email("test@example.com", "Subject", "Body")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_send_email_success(self):
        from sovereign.integrations.connectors.gmail_connector import GmailConnector

        c = GmailConnector({"access_token": "fake-token"})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "msg123", "threadId": "thr456"}
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=AsyncMock(return_value=mock_resp))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await c.send_email("to@example.com", "Hello", "World")
        assert result.get("message_id") == "msg123"

    @pytest.mark.asyncio
    async def test_create_draft_no_token(self):
        from sovereign.integrations.connectors.gmail_connector import GmailConnector

        c = GmailConnector({})
        result = await c.create_draft("x@x.com", "Draft", "Body")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_trash_message_no_token(self):
        from sovereign.integrations.connectors.gmail_connector import GmailConnector

        c = GmailConnector({})
        result = await c.trash_message("msg123")
        assert "error" in result

    def test_send_scope_present(self):
        from sovereign.integrations.connectors.gmail_connector import GmailConnector

        assert any("send" in s for s in GmailConnector.required_scopes)


class TestCalendarWrite:
    @pytest.mark.asyncio
    async def test_create_event_no_token(self):
        from sovereign.integrations.connectors.calendar_connector import CalendarConnector

        c = CalendarConnector({})
        result = await c.create_event("Meeting", "2026-05-14T10:00:00Z", "2026-05-14T11:00:00Z")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_event_success(self):
        from sovereign.integrations.connectors.calendar_connector import CalendarConnector

        c = CalendarConnector({"access_token": "tok"})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "ev1", "htmlLink": "https://cal.google.com/ev1"}
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=AsyncMock(return_value=mock_resp))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await c.create_event("Meeting", "2026-05-14T10:00:00Z", "2026-05-14T11:00:00Z")
        assert result.get("event_id") == "ev1"

    @pytest.mark.asyncio
    async def test_update_event_no_fields(self):
        from sovereign.integrations.connectors.calendar_connector import CalendarConnector

        c = CalendarConnector({"access_token": "tok"})
        result = await c.update_event("ev1")  # no fields
        assert "error" in result

    @pytest.mark.asyncio
    async def test_delete_event_no_token(self):
        from sovereign.integrations.connectors.calendar_connector import CalendarConnector

        c = CalendarConnector({})
        result = await c.delete_event("ev1")
        assert "error" in result

    def test_events_scope_present(self):
        from sovereign.integrations.connectors.calendar_connector import CalendarConnector

        assert any("events" in s for s in CalendarConnector.required_scopes)


class TestNotionWrite:
    @pytest.mark.asyncio
    async def test_create_page_no_token(self):
        from sovereign.integrations.connectors.notion_connector import NotionConnector

        c = NotionConnector({})
        result = await c.create_page(
            "db123", {"Name": {"title": [{"text": {"content": "Test"}}]}}
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_page_no_token(self):
        from sovereign.integrations.connectors.notion_connector import NotionConnector

        c = NotionConnector({})
        result = await c.update_page("page123", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_append_blocks_no_token(self):
        from sovereign.integrations.connectors.notion_connector import NotionConnector

        c = NotionConnector({})
        result = await c.append_blocks("block123", [])
        assert "error" in result
