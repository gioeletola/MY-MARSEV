"""
Tests for email, calendar, and CRM integrations (local JSON backend).
No external services or credentials required.
"""
from __future__ import annotations

import json
import pathlib
import pytest

from sovereign.integrations.base_integration import IntegrationConfig, IntegrationStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(integration_id: str = "test", credentials: dict | None = None) -> IntegrationConfig:
    return IntegrationConfig(
        integration_id=integration_id,
        name=integration_id,
        enabled=True,
        credentials=credentials or {},
    )


# ---------------------------------------------------------------------------
# EmailIntegration
# ---------------------------------------------------------------------------

class TestEmailIntegration:
    def test_connect_without_credentials(self):
        from sovereign.integrations.email_integration import EmailIntegration
        ei = EmailIntegration()
        ok = ei.connect(_cfg("email"))
        assert ok
        assert ei.status == IntegrationStatus.CONNECTED

    def test_disconnect(self):
        from sovereign.integrations.email_integration import EmailIntegration
        ei = EmailIntegration()
        ei.connect(_cfg())
        assert ei.disconnect() is True
        assert ei.status == IntegrationStatus.DISCONNECTED

    def test_send_queues_locally(self, tmp_path, monkeypatch):
        from sovereign.integrations import email_integration as mod
        monkeypatch.setattr(mod, "_OUTBOX_FILE", tmp_path / "outbox.json")
        monkeypatch.setattr(mod, "_INBOX_FILE",  tmp_path / "inbox.json")
        from sovereign.integrations.email_integration import EmailIntegration
        ei = EmailIntegration()
        ei.connect(_cfg())
        result = ei.send_email("bob@example.com", "Hello", "World")
        assert result is True
        outbox = json.loads((tmp_path / "outbox.json").read_text())
        assert len(outbox) == 1
        assert outbox[0]["to"] == "bob@example.com"
        assert outbox[0]["status"] == "queued"

    def test_add_message_and_fetch_inbox(self, tmp_path, monkeypatch):
        from sovereign.integrations import email_integration as mod
        monkeypatch.setattr(mod, "_OUTBOX_FILE", tmp_path / "outbox.json")
        monkeypatch.setattr(mod, "_INBOX_FILE",  tmp_path / "inbox.json")
        from sovereign.integrations.email_integration import EmailIntegration
        ei = EmailIntegration()
        ei.add_message("alice@example.com", "Hi", "Hey there")
        inbox = ei.fetch_inbox()
        assert len(inbox) == 1
        assert inbox[0]["from"] == "alice@example.com"

    def test_search_emails(self, tmp_path, monkeypatch):
        from sovereign.integrations import email_integration as mod
        monkeypatch.setattr(mod, "_OUTBOX_FILE", tmp_path / "outbox.json")
        monkeypatch.setattr(mod, "_INBOX_FILE",  tmp_path / "inbox.json")
        from sovereign.integrations.email_integration import EmailIntegration
        ei = EmailIntegration()
        ei.add_message("a@b.com", "Invoice Q1", "See attached")
        ei.add_message("c@d.com", "Meeting notes", "Call recap")
        results = ei.search_emails("invoice")
        assert len(results) == 1
        assert "Invoice" in results[0]["subject"]

    def test_mark_read(self, tmp_path, monkeypatch):
        from sovereign.integrations import email_integration as mod
        monkeypatch.setattr(mod, "_OUTBOX_FILE", tmp_path / "outbox.json")
        monkeypatch.setattr(mod, "_INBOX_FILE",  tmp_path / "inbox.json")
        from sovereign.integrations.email_integration import EmailIntegration
        ei = EmailIntegration()
        msg = ei.add_message("x@y.com", "Test", "Body")
        result = ei.mark_read(msg["id"])
        assert result is True
        inbox = ei.fetch_inbox()
        assert inbox[0]["read"] is True

    def test_fetch_dispatch(self, tmp_path, monkeypatch):
        from sovereign.integrations import email_integration as mod
        monkeypatch.setattr(mod, "_OUTBOX_FILE", tmp_path / "outbox.json")
        monkeypatch.setattr(mod, "_INBOX_FILE",  tmp_path / "inbox.json")
        from sovereign.integrations.email_integration import EmailIntegration
        ei = EmailIntegration()
        ei.add_message("x@y.com", "Hello", "Body")
        result = ei.fetch("inbox", {"limit": 5})
        assert "messages" in result


# ---------------------------------------------------------------------------
# CalendarIntegration
# ---------------------------------------------------------------------------

class TestCalendarIntegration:
    def test_connect(self):
        from sovereign.integrations.calendar_integration import CalendarIntegration
        ci = CalendarIntegration()
        ok = ci.connect(_cfg("calendar"))
        assert ok
        assert ci.status == IntegrationStatus.CONNECTED

    def test_create_and_get_event(self, tmp_path, monkeypatch):
        from sovereign.integrations import calendar_integration as mod
        monkeypatch.setattr(mod, "_CALENDAR_FILE", tmp_path / "cal.json")
        from sovereign.integrations.calendar_integration import CalendarIntegration
        ci = CalendarIntegration()
        event = ci.create_event("Team standup", "2026-04-17T09:00", "2026-04-17T09:30")
        assert event["id"]
        assert event["title"] == "Team standup"
        ev = ci.get_event(event["id"])
        assert ev is not None
        assert ev["title"] == "Team standup"

    def test_get_events_date_filter(self, tmp_path, monkeypatch):
        from sovereign.integrations import calendar_integration as mod
        monkeypatch.setattr(mod, "_CALENDAR_FILE", tmp_path / "cal.json")
        from sovereign.integrations.calendar_integration import CalendarIntegration
        ci = CalendarIntegration()
        ci.create_event("Past event", "2026-01-01T10:00", "2026-01-01T11:00")
        ci.create_event("Future event", "2026-12-01T10:00", "2026-12-01T11:00")
        results = ci.get_events("2026-04-01", "2026-06-30")
        assert all("Past" not in ev["title"] and "Future" not in ev["title"] for ev in results)

    def test_update_event(self, tmp_path, monkeypatch):
        from sovereign.integrations import calendar_integration as mod
        monkeypatch.setattr(mod, "_CALENDAR_FILE", tmp_path / "cal.json")
        from sovereign.integrations.calendar_integration import CalendarIntegration
        ci = CalendarIntegration()
        event = ci.create_event("Old title", "2026-05-01T09:00", "2026-05-01T10:00")
        ok = ci.update_event(event["id"], {"title": "New title"})
        assert ok is True
        updated = ci.get_event(event["id"])
        assert updated["title"] == "New title"

    def test_delete_event(self, tmp_path, monkeypatch):
        from sovereign.integrations import calendar_integration as mod
        monkeypatch.setattr(mod, "_CALENDAR_FILE", tmp_path / "cal.json")
        from sovereign.integrations.calendar_integration import CalendarIntegration
        ci = CalendarIntegration()
        event = ci.create_event("Delete me", "2026-05-01T09:00", "2026-05-01T10:00")
        ok = ci.delete_event(event["id"])
        assert ok is True
        assert ci.get_event(event["id"]) is None

    def test_delete_nonexistent_returns_false(self, tmp_path, monkeypatch):
        from sovereign.integrations import calendar_integration as mod
        monkeypatch.setattr(mod, "_CALENDAR_FILE", tmp_path / "cal.json")
        from sovereign.integrations.calendar_integration import CalendarIntegration
        ci = CalendarIntegration()
        assert ci.delete_event("nonexistent") is False

    def test_fetch_dispatch(self, tmp_path, monkeypatch):
        from sovereign.integrations import calendar_integration as mod
        monkeypatch.setattr(mod, "_CALENDAR_FILE", tmp_path / "cal.json")
        from sovereign.integrations.calendar_integration import CalendarIntegration
        ci = CalendarIntegration()
        ci.create_event("Ev", "2026-05-01", "2026-05-01")
        result = ci.fetch("events", {"date_from": "2026-01-01", "date_to": "2026-12-31"})
        assert "events" in result


# ---------------------------------------------------------------------------
# CRMIntegration
# ---------------------------------------------------------------------------

class TestCRMIntegration:
    def test_connect(self):
        from sovereign.integrations.crm_integration import CRMIntegration
        crm = CRMIntegration()
        ok = crm.connect(_cfg("crm"))
        assert ok
        assert crm.status == IntegrationStatus.CONNECTED

    def test_create_and_get_contact(self, tmp_path, monkeypatch):
        from sovereign.integrations import crm_integration as mod
        monkeypatch.setattr(mod, "_CONTACTS_FILE", tmp_path / "contacts.json")
        monkeypatch.setattr(mod, "_DEALS_FILE",    tmp_path / "deals.json")
        monkeypatch.setattr(mod, "_ACTIVITY_FILE", tmp_path / "activity.json")
        from sovereign.integrations.crm_integration import CRMIntegration
        crm = CRMIntegration()
        c = crm.create_contact({"name": "Alice", "email": "alice@acme.com", "company": "Acme"})
        assert c["id"]
        assert c["name"] == "Alice"
        fetched = crm.get_contact(c["id"])
        assert fetched is not None

    def test_search_contacts(self, tmp_path, monkeypatch):
        from sovereign.integrations import crm_integration as mod
        monkeypatch.setattr(mod, "_CONTACTS_FILE", tmp_path / "contacts.json")
        monkeypatch.setattr(mod, "_DEALS_FILE",    tmp_path / "deals.json")
        monkeypatch.setattr(mod, "_ACTIVITY_FILE", tmp_path / "activity.json")
        from sovereign.integrations.crm_integration import CRMIntegration
        crm = CRMIntegration()
        crm.create_contact({"name": "Alice Smith", "email": "alice@x.com"})
        crm.create_contact({"name": "Bob Jones", "email": "bob@y.com"})
        results = crm.search_contacts("alice")
        assert len(results) == 1
        assert results[0]["name"] == "Alice Smith"

    def test_update_contact(self, tmp_path, monkeypatch):
        from sovereign.integrations import crm_integration as mod
        monkeypatch.setattr(mod, "_CONTACTS_FILE", tmp_path / "contacts.json")
        monkeypatch.setattr(mod, "_DEALS_FILE",    tmp_path / "deals.json")
        monkeypatch.setattr(mod, "_ACTIVITY_FILE", tmp_path / "activity.json")
        from sovereign.integrations.crm_integration import CRMIntegration
        crm = CRMIntegration()
        c = crm.create_contact({"name": "Old Name", "email": "old@x.com"})
        ok = crm.update_contact(c["id"], {"name": "New Name"})
        assert ok is True
        assert crm.get_contact(c["id"])["name"] == "New Name"

    def test_create_deal_and_pipeline(self, tmp_path, monkeypatch):
        from sovereign.integrations import crm_integration as mod
        monkeypatch.setattr(mod, "_CONTACTS_FILE", tmp_path / "contacts.json")
        monkeypatch.setattr(mod, "_DEALS_FILE",    tmp_path / "deals.json")
        monkeypatch.setattr(mod, "_ACTIVITY_FILE", tmp_path / "activity.json")
        from sovereign.integrations.crm_integration import CRMIntegration
        crm = CRMIntegration()
        deal = crm.create_deal({"title": "Acme SaaS", "value": 50000, "stage": "qualified"})
        assert deal["stage"] == "qualified"
        pipeline = crm.get_pipeline()
        qualified_stage = next(s for s in pipeline if s["stage"] == "qualified")
        assert any(d["id"] == deal["id"] for d in qualified_stage["deals"])

    def test_advance_deal(self, tmp_path, monkeypatch):
        from sovereign.integrations import crm_integration as mod
        monkeypatch.setattr(mod, "_CONTACTS_FILE", tmp_path / "contacts.json")
        monkeypatch.setattr(mod, "_DEALS_FILE",    tmp_path / "deals.json")
        monkeypatch.setattr(mod, "_ACTIVITY_FILE", tmp_path / "activity.json")
        from sovereign.integrations.crm_integration import CRMIntegration
        crm = CRMIntegration()
        deal = crm.create_deal({"title": "Prospects Inc", "value": 1000, "stage": "lead"})
        ok = crm.advance_deal(deal["id"])
        assert ok is True
        # After advance, should be at "qualified"
        from sovereign.integrations import crm_integration as fresh_mod
        monkeypatch.setattr(fresh_mod, "_DEALS_FILE", tmp_path / "deals.json")
        from sovereign.integrations.crm_integration import CRMIntegration as C2
        crm2 = C2()
        pipeline = crm2.get_pipeline()
        qualified = next(s for s in pipeline if s["stage"] == "qualified")
        assert any(d["id"] == deal["id"] for d in qualified["deals"])

    def test_log_and_get_activity(self, tmp_path, monkeypatch):
        from sovereign.integrations import crm_integration as mod
        monkeypatch.setattr(mod, "_CONTACTS_FILE", tmp_path / "contacts.json")
        monkeypatch.setattr(mod, "_DEALS_FILE",    tmp_path / "deals.json")
        monkeypatch.setattr(mod, "_ACTIVITY_FILE", tmp_path / "activity.json")
        from sovereign.integrations.crm_integration import CRMIntegration
        crm = CRMIntegration()
        ok = crm.log_activity("contact-1", {"type": "call", "note": "Discussed pricing"})
        assert ok is True
        log = crm.get_activity("contact-1")
        assert len(log) == 1
        assert log[0]["note"] == "Discussed pricing"
