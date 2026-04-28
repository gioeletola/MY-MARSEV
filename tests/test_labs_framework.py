"""
Tests for sovereign/labs/labs_framework.py and all individual lab modules.
"""
from __future__ import annotations

import pytest


# ===========================================================================
# LabsFramework — full lifecycle
# ===========================================================================

class TestLabsFramework:
    @pytest.fixture
    def framework(self, tmp_path):
        from sovereign.labs.labs_framework import LabsFramework
        return LabsFramework(data_path=tmp_path / "experiments.json")

    @pytest.fixture
    def hyp(self):
        from sovereign.labs.labs_framework import Hypothesis
        return Hypothesis(
            statement="If we cache then speed improves",
            metric="cache_hit_rate",
            success_threshold=0.70,
            baseline=0.40,
        )

    def test_create_experiment(self, framework, hyp):
        exp = framework.create_experiment("Test Exp", "desc", hyp)
        assert exp.name == "Test Exp"
        assert exp.experiment_id is not None

    def test_get_experiment(self, framework, hyp):
        exp = framework.create_experiment("Exp1", "d", hyp)
        fetched = framework.get(exp.experiment_id)
        assert fetched is not None
        assert fetched.name == "Exp1"

    def test_get_nonexistent(self, framework):
        assert framework.get("ghost") is None

    def test_list_experiments_empty(self, framework):
        assert framework.list_experiments() == []

    def test_list_experiments_all(self, framework, hyp):
        framework.create_experiment("E1", "d1", hyp)
        framework.create_experiment("E2", "d2", hyp)
        assert len(framework.list_experiments()) == 2

    def test_start_experiment(self, framework, hyp):
        from sovereign.labs.labs_framework import ExperimentStatus
        exp = framework.create_experiment("E1", "d", hyp)
        framework.start(exp.experiment_id)
        fetched = framework.get(exp.experiment_id)
        assert fetched.status == ExperimentStatus.RUNNING
        assert fetched.started_at != ""

    def test_pause_experiment(self, framework, hyp):
        from sovereign.labs.labs_framework import ExperimentStatus
        exp = framework.create_experiment("E1", "d", hyp)
        framework.start(exp.experiment_id)
        framework.pause(exp.experiment_id)
        assert framework.get(exp.experiment_id).status == ExperimentStatus.PAUSED

    def test_record_observation(self, framework, hyp):
        exp = framework.create_experiment("E1", "d", hyp)
        framework.record_observation(exp.experiment_id, "Interesting finding")
        obs = framework.get(exp.experiment_id).observations
        assert len(obs) == 1
        assert "Interesting finding" in obs[0]

    def test_record_result(self, framework, hyp):
        exp = framework.create_experiment("E1", "d", hyp)
        framework.record_result(exp.experiment_id, "cache_hit_rate", 0.80)
        results = framework.get(exp.experiment_id).results
        assert results["cache_hit_rate"]["value"] == 0.80

    def test_complete_success(self, framework, hyp):
        exp = framework.create_experiment("E1", "d", hyp)
        framework.record_result(exp.experiment_id, "cache_hit_rate", 0.80)
        evaluation = framework.complete(exp.experiment_id)
        assert evaluation["success"] is True
        assert evaluation["measured"] == 0.80

    def test_complete_failure(self, framework, hyp):
        from sovereign.labs.labs_framework import ExperimentStatus
        exp = framework.create_experiment("E1", "d", hyp)
        framework.record_result(exp.experiment_id, "cache_hit_rate", 0.50)
        evaluation = framework.complete(exp.experiment_id)
        assert evaluation["success"] is False
        assert framework.get(exp.experiment_id).status == ExperimentStatus.FAILED

    def test_graduate_experiment(self, framework, hyp):
        from sovereign.labs.labs_framework import ExperimentStatus
        exp = framework.create_experiment("E1", "d", hyp)
        framework.record_result(exp.experiment_id, "cache_hit_rate", 0.80)
        framework.complete(exp.experiment_id)
        framework.graduate(exp.experiment_id)
        assert framework.get(exp.experiment_id).status == ExperimentStatus.GRADUATED

    def test_graduate_not_completed_raises(self, framework, hyp):
        exp = framework.create_experiment("E1", "d", hyp)
        with pytest.raises((ValueError, Exception)):
            framework.graduate(exp.experiment_id)

    def test_running_experiments(self, framework, hyp):
        exp = framework.create_experiment("E1", "d", hyp)
        framework.start(exp.experiment_id)
        running = framework.running_experiments()
        assert len(running) == 1

    def test_dashboard_empty(self, framework):
        d = framework.dashboard()
        assert d["total"] == 0
        assert d["graduated"] == []

    def test_dashboard_with_data(self, framework, hyp):
        exp = framework.create_experiment("E1", "d", hyp)
        framework.record_result(exp.experiment_id, "cache_hit_rate", 0.80)
        framework.complete(exp.experiment_id)
        framework.graduate(exp.experiment_id)
        d = framework.dashboard()
        assert d["total"] == 1
        assert "E1" in d["graduated"]

    def test_list_by_status(self, framework, hyp):
        from sovereign.labs.labs_framework import ExperimentStatus
        exp = framework.create_experiment("E1", "d", hyp)
        framework.start(exp.experiment_id)
        running = framework.list_experiments(status=ExperimentStatus.RUNNING)
        assert len(running) == 1
        draft = framework.list_experiments(status=ExperimentStatus.DRAFT)
        assert len(draft) == 0

    def test_persistence(self, tmp_path, hyp):
        from sovereign.labs.labs_framework import LabsFramework
        path = tmp_path / "exp.json"
        f1 = LabsFramework(data_path=path)
        exp = f1.create_experiment("Persist", "d", hyp)
        f2 = LabsFramework(data_path=path)
        assert f2.get(exp.experiment_id) is not None

    def test_get_nonexistent_raises(self, framework):
        with pytest.raises(KeyError):
            framework._get("ghost")

    def test_create_with_configs(self, framework, hyp):
        exp = framework.create_experiment(
            "Config Exp", "desc", hyp,
            control_config={"model": "sonnet"},
            treatment_config={"model": "opus"},
            tags=["model-test"],
        )
        assert exp.control_config["model"] == "sonnet"
        assert "model-test" in exp.tags


# ===========================================================================
# Individual lab modules — import coverage
# ===========================================================================

class TestIndividualLabs:
    def _make_lab(self, lab_class, tmp_path):
        return lab_class(data_path=str(tmp_path / "exp.json"))

    def test_3d_lab(self, tmp_path):
        import importlib
        mod = importlib.import_module("sovereign.labs.3d_lab")
        lab = mod.ThreeDLab(data_path=str(tmp_path / "3d.json"))
        assert lab.lab_id == "3d"

    def test_ai_experiment_lab(self, tmp_path):
        from sovereign.labs.ai_experiment_lab import AIExperimentLab
        lab = AIExperimentLab(data_path=str(tmp_path / "ai.json"))
        assert lab.lab_id == "ai_experiment"

    def test_automation_lab(self, tmp_path):
        from sovereign.labs.automation_lab import AutomationLab
        lab = AutomationLab(data_path=str(tmp_path / "auto.json"))
        assert lab.lab_id == "automation"

    def test_behavioral_lab(self, tmp_path):
        from sovereign.labs.behavioral_lab import BehavioralLab
        lab = BehavioralLab(data_path=str(tmp_path / "beh.json"))
        assert lab.lab_id == "behavioral"

    def test_bio_lab(self, tmp_path):
        from sovereign.labs.bio_lab import BioLab
        lab = BioLab(data_path=str(tmp_path / "bio.json"))
        assert lab.lab_id == "bio"

    def test_black_swan_lab(self, tmp_path):
        from sovereign.labs.black_swan_lab import BlackSwanLab
        lab = BlackSwanLab(data_path=str(tmp_path / "bs.json"))
        assert lab.lab_id == "black_swan"

    def test_cyber_lab(self, tmp_path):
        from sovereign.labs.cyber_lab import CyberLab
        lab = CyberLab(data_path=str(tmp_path / "cy.json"))
        assert lab.lab_id == "cyber"

    def test_decision_science_lab(self, tmp_path):
        from sovereign.labs.decision_science_lab import DecisionScienceLab
        lab = DecisionScienceLab(data_path=str(tmp_path / "ds.json"))
        assert lab.lab_id == "decision_science"

    def test_design_lab(self, tmp_path):
        from sovereign.labs.design_lab import DesignLab
        lab = DesignLab(data_path=str(tmp_path / "de.json"))
        assert lab.lab_id == "design"

    def test_finance_lab(self, tmp_path):
        from sovereign.labs.finance_lab import FinanceLab
        lab = FinanceLab(data_path=str(tmp_path / "fi.json"))
        assert lab.lab_id == "finance"

    def test_future_systems_lab(self, tmp_path):
        from sovereign.labs.future_systems_lab import FutureSystemsLab
        lab = FutureSystemsLab(data_path=str(tmp_path / "fu.json"))
        assert lab.lab_id == "future_systems"

    def test_georisk_lab(self, tmp_path):
        from sovereign.labs.georisk_lab import GeoRiskLab
        lab = GeoRiskLab(data_path=str(tmp_path / "ge.json"))
        assert lab.lab_id == "georisk"

    def test_media_lab(self, tmp_path):
        from sovereign.labs.media_lab import MediaLab
        lab = MediaLab(data_path=str(tmp_path / "me.json"))
        assert lab.lab_id == "media"

    def test_memory_lab(self, tmp_path):
        from sovereign.labs.memory_lab import MemoryLab
        lab = MemoryLab(data_path=str(tmp_path / "ml.json"))
        assert lab.lab_id == "memory"

    def test_offline_survival_lab(self, tmp_path):
        from sovereign.labs.offline_survival_lab import OfflineSurvivalLab
        lab = OfflineSurvivalLab(data_path=str(tmp_path / "of.json"))
        assert lab.lab_id == "offline_survival"

    def test_product_lab(self, tmp_path):
        from sovereign.labs.product_lab import ProductLab
        lab = ProductLab(data_path=str(tmp_path / "pr.json"))
        assert lab.lab_id == "product"

    def test_red_team_lab(self, tmp_path):
        from sovereign.labs.red_team_lab import RedTeamLab
        lab = RedTeamLab(data_path=str(tmp_path / "rt.json"))
        assert lab.lab_id == "red_team"

    def test_research_lab(self, tmp_path):
        from sovereign.labs.research_lab import ResearchLab
        lab = ResearchLab(data_path=str(tmp_path / "re.json"))
        assert lab.lab_id == "research"

    def test_simulation_lab(self, tmp_path):
        from sovereign.labs.simulation_lab import SimulationLab
        lab = SimulationLab(data_path=str(tmp_path / "si.json"))
        assert lab.lab_id == "simulation"

    def test_social_dynamics_lab(self, tmp_path):
        from sovereign.labs.social_dynamics_lab import SocialDynamicsLab
        lab = SocialDynamicsLab(data_path=str(tmp_path / "so.json"))
        assert lab.lab_id == "social_dynamics"

    def test_strategy_lab(self, tmp_path):
        from sovereign.labs.strategy_lab import StrategyLab
        lab = StrategyLab(data_path=str(tmp_path / "st.json"))
        assert lab.lab_id == "strategy"


# ===========================================================================
# ExperimentStatus enum
# ===========================================================================

class TestExperimentStatus:
    def test_all_statuses(self):
        from sovereign.labs.labs_framework import ExperimentStatus
        statuses = [s.value for s in ExperimentStatus]
        assert "draft" in statuses
        assert "running" in statuses
        assert "completed" in statuses
        assert "graduated" in statuses
        assert "failed" in statuses


# ===========================================================================
# Memory domain schemas — real implementations
# ===========================================================================

class TestMemoryDomainStubs:
    def test_identity_domain(self):
        from sovereign.memory.domains.identity import IdentityRecord, DOMAIN_NAME
        r = IdentityRecord(full_name="Alice")
        assert r.full_name == "Alice"
        assert DOMAIN_NAME == "identity"

    def test_brand_domain(self):
        from sovereign.memory.domains.brand import BrandIdentity, DOMAIN_NAME
        r = BrandIdentity(name="Acme Corp")
        assert r.name == "Acme Corp"
        assert DOMAIN_NAME == "brand"

    def test_content_domain(self):
        from sovereign.memory.domains.content import ContentPiece, DOMAIN_NAME
        r = ContentPiece(content_id="c-001", title="Test Post")
        assert r.content_id == "c-001"
        assert r.title == "Test Post"
        assert DOMAIN_NAME == "content"

    def test_decision_domain(self):
        from sovereign.memory.domains.decision import DecisionRecord, DOMAIN_NAME
        r = DecisionRecord(decision_id="d-001", title="Go/No-Go")
        assert r.decision_id == "d-001"
        assert DOMAIN_NAME == "decision"

    def test_diary_domain(self):
        from sovereign.memory.domains.diary import DiaryEntry, DOMAIN_NAME
        r = DiaryEntry(entry_id="dr-001", date="2026-04-25")
        assert r.entry_id == "dr-001"
        assert DOMAIN_NAME == "diary"

    def test_health_routine_domain(self):
        from sovereign.memory.domains.health_routine import HealthProfile, DOMAIN_NAME
        r = HealthProfile(fitness_level="active")
        assert r.fitness_level == "active"
        assert DOMAIN_NAME == "health_routine"

    def test_inventory_domain(self):
        from sovereign.memory.domains.inventory import InventoryItem, DOMAIN_NAME
        r = InventoryItem(item_id="inv-001", name="Laptop")
        assert r.item_id == "inv-001"
        assert DOMAIN_NAME == "inventory"

    def test_learning_domain(self):
        from sovereign.memory.domains.learning import LearningItem, DOMAIN_NAME
        r = LearningItem(item_id="l-001", title="Python Course")
        assert r.item_id == "l-001"
        assert DOMAIN_NAME == "learning"

    def test_legal_compliance_domain(self):
        from sovereign.memory.domains.legal_compliance import Contract, DOMAIN_NAME
        r = Contract(contract_id="lc-001", title="NDA")
        assert r.contract_id == "lc-001"
        assert DOMAIN_NAME == "legal_compliance"

    def test_operational_domain(self):
        from sovereign.memory.domains.operational import SOP, DOMAIN_NAME
        r = SOP(sop_id="op-001", title="Onboarding SOP")
        assert r.sop_id == "op-001"
        assert DOMAIN_NAME == "operational"

    def test_relationship_domain(self):
        from sovereign.memory.domains.relationship import Contact, DOMAIN_NAME
        r = Contact(contact_id="rel-001", full_name="Jane Doe")
        assert r.contact_id == "rel-001"
        assert DOMAIN_NAME == "relationship"

    def test_research_domain(self):
        from sovereign.memory.domains.research import ResearchProject, DOMAIN_NAME
        r = ResearchProject(project_id="res-001", title="AI Survey")
        assert r.project_id == "res-001"
        assert DOMAIN_NAME == "research"


# ===========================================================================
# compare() and leaderboard() — new methods
# ===========================================================================

class TestCompareAndLeaderboard:
    @pytest.fixture
    def fw(self, tmp_path):
        from sovereign.labs.labs_framework import LabsFramework, Hypothesis
        fw = LabsFramework(data_path=tmp_path / "exp.json")
        hyp = Hypothesis(
            statement="Better model is faster",
            metric="score",
            success_threshold=0.5,   # low threshold so all seeded experiments complete
            baseline=0.3,
        )
        return fw, hyp

    def _seed(self, fw, hyp, name, value):
        exp = fw.create_experiment(name, "desc", hyp)
        fw.start(exp.experiment_id)
        fw.record_result(exp.experiment_id, "score", value)
        fw.complete(exp.experiment_id)
        return exp

    # --- compare ---

    def test_compare_returns_winner(self, fw):
        fw, hyp = fw
        e1 = self._seed(fw, hyp, "Lower", 0.6)
        e2 = self._seed(fw, hyp, "Higher", 0.9)
        result = fw.compare(e1.experiment_id, e2.experiment_id)
        assert "winner" in result
        assert result["winner"] == e2.experiment_id

    def test_compare_returns_delta(self, fw):
        fw, hyp = fw
        e1 = self._seed(fw, hyp, "A", 0.8)
        e2 = self._seed(fw, hyp, "B", 0.9)
        result = fw.compare(e1.experiment_id, e2.experiment_id)
        assert "delta" in result
        assert result["delta"] == pytest.approx(0.1, abs=0.01)

    def test_compare_invalid_id_raises_key_error(self, fw):
        fw, hyp = fw
        e1 = self._seed(fw, hyp, "Only", 0.7)
        with pytest.raises(KeyError):
            fw.compare(e1.experiment_id, "does-not-exist")

    # --- leaderboard ---

    def test_leaderboard_empty_when_no_experiments(self, fw):
        fw, _ = fw
        assert fw.leaderboard() == []

    def test_leaderboard_sorted_best_first(self, fw):
        fw, hyp = fw
        self._seed(fw, hyp, "Mid", 0.7)
        self._seed(fw, hyp, "Best", 0.95)
        self._seed(fw, hyp, "Worst", 0.5)
        board = fw.leaderboard()
        assert len(board) >= 3
        scores = [e.get("score", e.get("value", 0)) for e in board]
        assert scores == sorted(scores, reverse=True)

    def test_leaderboard_only_includes_completed_or_graduated(self, fw):
        fw, hyp = fw
        self._seed(fw, hyp, "Done", 0.8)           # COMPLETED
        fw.create_experiment("Draft", "desc", hyp)  # DRAFT — excluded
        board = fw.leaderboard()
        names = [e.get("name", "") for e in board]
        assert "Draft" not in names

    def test_leaderboard_accepts_metric_kwarg(self, fw):
        fw, hyp = fw
        self._seed(fw, hyp, "X", 0.8)
        board = fw.leaderboard(metric="score")
        assert isinstance(board, list)
        assert len(board) == 1
