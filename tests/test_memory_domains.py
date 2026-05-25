"""Tests for the 12 implemented memory domain schemas."""
from __future__ import annotations

import pytest


class TestDiaryDomain:
    def test_entry_creation(self):
        from sovereign.memory.domains.diary import DiaryEntry
        e = DiaryEntry(entry_id="d1", date="2026-04-25", mood="happy", mood_score=8.0)
        assert e.entry_id == "d1"
        assert e.mood_score == 8.0

    def test_store_add_get(self, tmp_path):
        from sovereign.memory.domains.diary import DiaryEntry, DiaryMemoryStore
        store = DiaryMemoryStore(tmp_path / "diary.json")
        entry = DiaryEntry(entry_id="e1", date="2026-04-25", content="Good day")
        store.add_entry(entry)
        fetched = store.get_entry("e1")
        assert fetched is not None
        assert fetched.content == "Good day"

    def test_recent(self, tmp_path):
        from sovereign.memory.domains.diary import DiaryEntry, DiaryMemoryStore
        store = DiaryMemoryStore(tmp_path / "diary.json")
        for i in range(5):
            store.add_entry(DiaryEntry(entry_id=f"e{i}", date=f"2026-04-{20+i}"))
        assert len(store.recent(3)) == 3

    def test_average_mood(self, tmp_path):
        from datetime import date, timedelta
        from sovereign.memory.domains.diary import DiaryEntry, DiaryMemoryStore
        store = DiaryMemoryStore(tmp_path / "diary.json")
        today = date.today()
        d1 = (today - timedelta(days=1)).isoformat()
        d2 = (today - timedelta(days=2)).isoformat()
        store.add_entry(DiaryEntry(entry_id="e1", date=d1, mood_score=6.0))
        store.add_entry(DiaryEntry(entry_id="e2", date=d2, mood_score=8.0))
        avg = store.average_mood()
        assert avg == pytest.approx(7.0)

    def test_context_string(self, tmp_path):
        from sovereign.memory.domains.diary import DiaryEntry, DiaryMemoryStore
        store = DiaryMemoryStore(tmp_path / "diary.json")
        assert "No diary" in store.to_context_string()
        store.add_entry(DiaryEntry(entry_id="e1", date="2026-04-25", mood="happy"))
        assert "2026-04-25" in store.to_context_string()


class TestBrandDomain:
    def test_identity(self, tmp_path):
        from sovereign.memory.domains.brand import BrandMemoryStore
        store = BrandMemoryStore(tmp_path / "brand.json")
        store.update_identity(name="Acme", tagline="Quality first")
        ident = store.get_identity()
        assert ident.name == "Acme"
        assert ident.tagline == "Quality first"

    def test_add_asset(self, tmp_path):
        from sovereign.memory.domains.brand import BrandAsset, BrandMemoryStore
        store = BrandMemoryStore(tmp_path / "brand.json")
        asset = BrandAsset(asset_id="a1", asset_type="logo", name="Main Logo")
        store.add_asset(asset)
        logos = store.get_assets("logo")
        assert len(logos) == 1
        assert logos[0].name == "Main Logo"

    def test_context_returns_string(self, tmp_path):
        from sovereign.memory.domains.brand import BrandMemoryStore
        store = BrandMemoryStore(tmp_path / "brand.json")
        ctx = store.to_context_string()
        assert isinstance(ctx, str)


class TestDecisionDomain:
    def test_add_and_get(self, tmp_path):
        from sovereign.memory.domains.decision import DecisionRecord, DecisionMemoryStore
        store = DecisionMemoryStore(tmp_path / "decision.json")
        rec = DecisionRecord(decision_id="d1", title="Launch product")
        store.add_decision(rec)
        fetched = store.get_decision("d1")
        assert fetched is not None
        assert fetched.title == "Launch product"

    def test_by_status(self, tmp_path):
        from sovereign.memory.domains.decision import DecisionRecord, DecisionMemoryStore
        store = DecisionMemoryStore(tmp_path / "decision.json")
        store.add_decision(DecisionRecord(decision_id="d1", title="A", status="open"))
        store.add_decision(DecisionRecord(decision_id="d2", title="B", status="decided"))
        assert len(store.by_status("open")) == 1
        assert len(store.by_status("decided")) == 1

    def test_update_decision(self, tmp_path):
        from sovereign.memory.domains.decision import DecisionRecord, DecisionMemoryStore
        store = DecisionMemoryStore(tmp_path / "decision.json")
        store.add_decision(DecisionRecord(decision_id="d1", title="A"))
        store.update_decision("d1", status="decided", chosen_option="Option B")
        fetched = store.get_decision("d1")
        assert fetched.status == "decided"


class TestHealthRoutineDomain:
    def test_profile_update(self, tmp_path):
        from sovereign.memory.domains.health_routine import HealthRoutineMemoryStore
        store = HealthRoutineMemoryStore(tmp_path / "health.json")
        store.update_profile(age=30, fitness_level="active")
        p = store.get_profile()
        assert p.age == 30
        assert p.fitness_level == "active"

    def test_log_metric(self, tmp_path):
        from sovereign.memory.domains.health_routine import HealthMetric, HealthRoutineMemoryStore
        store = HealthRoutineMemoryStore(tmp_path / "health.json")
        m = HealthMetric(metric_id="m1", metric_type="weight", value=75.5, unit="kg")
        store.log_metric(m)
        recent = store.recent_metrics("weight")
        assert len(recent) == 1
        assert recent[0].value == 75.5

    def test_active_routines(self, tmp_path):
        from sovereign.memory.domains.health_routine import Routine, HealthRoutineMemoryStore
        store = HealthRoutineMemoryStore(tmp_path / "health.json")
        r = Routine(routine_id="r1", name="Morning Run", active=True)
        store.add_routine(r)
        assert len(store.active_routines()) == 1


class TestInventoryDomain:
    def test_add_and_get(self, tmp_path):
        from sovereign.memory.domains.inventory import InventoryItem, InventoryMemoryStore
        store = InventoryMemoryStore(tmp_path / "inventory.json")
        item = InventoryItem(item_id="i1", name="Laptop", category="electronics", current_value=1000.0)
        store.add_item(item)
        fetched = store.get_item("i1")
        assert fetched is not None
        assert fetched.name == "Laptop"

    def test_total_value(self, tmp_path):
        from sovereign.memory.domains.inventory import InventoryItem, InventoryMemoryStore
        store = InventoryMemoryStore(tmp_path / "inventory.json")
        store.add_item(InventoryItem(item_id="i1", name="A", quantity=2.0, current_value=500.0))
        store.add_item(InventoryItem(item_id="i2", name="B", quantity=1.0, current_value=200.0))
        assert store.total_value() == pytest.approx(1200.0)

    def test_by_category(self, tmp_path):
        from sovereign.memory.domains.inventory import InventoryItem, InventoryMemoryStore
        store = InventoryMemoryStore(tmp_path / "inventory.json")
        store.add_item(InventoryItem(item_id="i1", name="Phone", category="electronics"))
        store.add_item(InventoryItem(item_id="i2", name="Desk", category="furniture"))
        assert len(store.by_category("electronics")) == 1


class TestLearningDomain:
    def test_add_item_and_progress(self, tmp_path):
        from sovereign.memory.domains.learning import LearningItem, LearningMemoryStore
        store = LearningMemoryStore(tmp_path / "learning.json")
        item = LearningItem(item_id="l1", title="Python", status="in_progress")
        store.add_item(item)
        store.update_progress("l1", 50.0)
        in_progress = store.by_status("in_progress")
        assert len(in_progress) == 1

    def test_complete_marks_done(self, tmp_path):
        from sovereign.memory.domains.learning import LearningItem, LearningMemoryStore
        store = LearningMemoryStore(tmp_path / "learning.json")
        store.add_item(LearningItem(item_id="l1", title="Course", status="in_progress"))
        store.update_progress("l1", 100.0)
        done = store.by_status("completed")
        assert len(done) == 1

    def test_skill_tracking(self, tmp_path):
        from sovereign.memory.domains.learning import SkillProgress, LearningMemoryStore
        store = LearningMemoryStore(tmp_path / "learning.json")
        skill = SkillProgress(skill_id="s1", skill_name="Python", level="advanced")
        store.update_skill(skill)
        fetched = store.get_skill("s1")
        assert fetched is not None
        assert fetched.skill_name == "Python"


class TestLegalComplianceDomain:
    def test_add_contract(self, tmp_path):
        from sovereign.memory.domains.legal_compliance import Contract, LegalComplianceMemoryStore
        store = LegalComplianceMemoryStore(tmp_path / "legal.json")
        c = Contract(contract_id="c1", title="NDA", status="active", end_date="2027-01-01")
        store.add_contract(c)
        assert len(store.active_contracts()) == 1

    def test_expiring_contracts(self, tmp_path):
        from sovereign.memory.domains.legal_compliance import Contract, LegalComplianceMemoryStore
        store = LegalComplianceMemoryStore(tmp_path / "legal.json")
        store.add_contract(Contract(contract_id="c1", title="Old", status="active", end_date="2026-05-01"))
        store.add_contract(Contract(contract_id="c2", title="New", status="active", end_date="2027-12-31"))
        expiring = store.expiring_contracts(days=60)
        assert len(expiring) == 1
        assert expiring[0].title == "Old"


class TestOperationalDomain:
    def test_add_sop(self, tmp_path):
        from sovereign.memory.domains.operational import SOP, OperationalMemoryStore
        store = OperationalMemoryStore(tmp_path / "ops.json")
        sop = SOP(sop_id="s1", title="Onboarding", category="hr")
        store.add_sop(sop)
        active = store.active_sops()
        assert len(active) == 1

    def test_active_sops_by_category(self, tmp_path):
        from sovereign.memory.domains.operational import SOP, OperationalMemoryStore
        store = OperationalMemoryStore(tmp_path / "ops.json")
        store.add_sop(SOP(sop_id="s1", title="A", category="hr"))
        store.add_sop(SOP(sop_id="s2", title="B", category="tech"))
        assert len(store.active_sops("hr")) == 1

    def test_checklist(self, tmp_path):
        from sovereign.memory.domains.operational import Checklist, OperationalMemoryStore
        store = OperationalMemoryStore(tmp_path / "ops.json")
        cl = Checklist(checklist_id="cl1", title="Deploy checklist")
        store.add_checklist(cl)
        store.complete_checklist("cl1")
        assert store._data["checklists"]["cl1"]["completed"] is True


class TestContentDomain:
    def test_add_piece(self, tmp_path):
        from sovereign.memory.domains.content import ContentPiece, ContentMemoryStore
        store = ContentMemoryStore(tmp_path / "content.json")
        p = ContentPiece(content_id="p1", title="Post 1", status="draft")
        store.add_piece(p)
        drafts = store.by_status("draft")
        assert len(drafts) == 1

    def test_by_platform(self, tmp_path):
        from sovereign.memory.domains.content import ContentPiece, ContentMemoryStore
        store = ContentMemoryStore(tmp_path / "content.json")
        store.add_piece(ContentPiece(content_id="p1", title="A", platform="linkedin"))
        store.add_piece(ContentPiece(content_id="p2", title="B", platform="twitter"))
        assert len(store.by_platform("linkedin")) == 1

    def test_context_string(self, tmp_path):
        from sovereign.memory.domains.content import ContentMemoryStore
        store = ContentMemoryStore(tmp_path / "content.json")
        ctx = store.to_context_string()
        assert "draft" in ctx


class TestRelationshipDomain:
    def test_add_contact(self, tmp_path):
        from sovereign.memory.domains.relationship import Contact, RelationshipMemoryStore
        store = RelationshipMemoryStore(tmp_path / "rel.json")
        c = Contact(contact_id="c1", full_name="Alice", relationship_type="professional")
        store.add_contact(c)
        fetched = store.get_contact("c1")
        assert fetched is not None
        assert fetched.full_name == "Alice"

    def test_log_interaction(self, tmp_path):
        from sovereign.memory.domains.relationship import Contact, Interaction, RelationshipMemoryStore
        store = RelationshipMemoryStore(tmp_path / "rel.json")
        store.add_contact(Contact(contact_id="c1", full_name="Bob"))
        interaction = Interaction(
            interaction_id="i1", contact_id="c1",
            interaction_type="call", follow_up_needed=True,
            occurred_at="2026-04-25T10:00:00Z",
        )
        store.log_interaction(interaction)
        assert len(store.pending_follow_ups()) == 1

    def test_by_type(self, tmp_path):
        from sovereign.memory.domains.relationship import Contact, RelationshipMemoryStore
        store = RelationshipMemoryStore(tmp_path / "rel.json")
        store.add_contact(Contact(contact_id="c1", full_name="A", relationship_type="personal"))
        store.add_contact(Contact(contact_id="c2", full_name="B", relationship_type="professional"))
        assert len(store.by_type("personal")) == 1


class TestResearchDomain:
    def test_add_project(self, tmp_path):
        from sovereign.memory.domains.research import ResearchProject, ResearchMemoryStore
        store = ResearchMemoryStore(tmp_path / "research.json")
        p = ResearchProject(project_id="p1", title="AI Survey", status="active")
        store.add_project(p)
        assert len(store.active_projects()) == 1

    def test_add_finding(self, tmp_path):
        from sovereign.memory.domains.research import ResearchFinding, ResearchMemoryStore
        store = ResearchMemoryStore(tmp_path / "research.json")
        f = ResearchFinding(finding_id="f1", project_id="p1", title="Key insight")
        store.add_finding(f)
        findings = store.findings_for_project("p1")
        assert len(findings) == 1
        assert findings[0].title == "Key insight"

    def test_high_credibility_sources(self, tmp_path):
        from sovereign.memory.domains.research import ResearchSource, ResearchMemoryStore
        store = ResearchMemoryStore(tmp_path / "research.json")
        store.add_source(ResearchSource(source_id="s1", title="Nature Paper", credibility=0.95))
        store.add_source(ResearchSource(source_id="s2", title="Blog Post", credibility=0.5))
        high = store.high_credibility_sources(0.8)
        assert len(high) == 1
        assert high[0].title == "Nature Paper"

    def test_context_string(self, tmp_path):
        from sovereign.memory.domains.research import ResearchMemoryStore
        store = ResearchMemoryStore(tmp_path / "research.json")
        ctx = store.to_context_string()
        assert "Research" in ctx
