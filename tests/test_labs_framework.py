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
# Memory domain stubs — just import to get coverage
# ===========================================================================

class TestMemoryDomainStubs:
    def test_identity_domain(self):
        from sovereign.memory.domains.identity import IdentityRecord, DOMAIN_NAME
        r = IdentityRecord(id="id-001")
        assert r.id == "id-001"
        assert DOMAIN_NAME == "identity"

    def test_brand_domain(self):
        from sovereign.memory.domains.brand import BrandRecord, DOMAIN_NAME
        r = BrandRecord(id="b-001")
        assert r.id == "b-001"
        assert DOMAIN_NAME == "brand"

    def test_content_domain(self):
        from sovereign.memory.domains.content import ContentRecord, DOMAIN_NAME
        r = ContentRecord(id="c-001")
        assert r.id == "c-001"
        assert DOMAIN_NAME == "content"

    def test_decision_domain(self):
        from sovereign.memory.domains.decision import DecisionRecord, DOMAIN_NAME
        r = DecisionRecord(id="d-001")
        assert r.id == "d-001"
        assert DOMAIN_NAME == "decision"

    def test_diary_domain(self):
        from sovereign.memory.domains.diary import DiaryRecord, DOMAIN_NAME
        r = DiaryRecord(id="dr-001")
        assert r.id == "dr-001"
        assert DOMAIN_NAME == "diary"

    def test_health_routine_domain(self):
        from sovereign.memory.domains.health_routine import Health_routineRecord, DOMAIN_NAME
        r = Health_routineRecord(id="hr-001")
        assert r.id == "hr-001"
        assert DOMAIN_NAME == "health_routine"

    def test_inventory_domain(self):
        from sovereign.memory.domains.inventory import InventoryRecord, DOMAIN_NAME
        r = InventoryRecord(id="inv-001")
        assert r.id == "inv-001"
        assert DOMAIN_NAME == "inventory"

    def test_learning_domain(self):
        from sovereign.memory.domains.learning import LearningRecord, DOMAIN_NAME
        r = LearningRecord(id="l-001")
        assert r.id == "l-001"
        assert DOMAIN_NAME == "learning"

    def test_legal_compliance_domain(self):
        from sovereign.memory.domains.legal_compliance import Legal_complianceRecord, DOMAIN_NAME
        r = Legal_complianceRecord(id="lc-001")
        assert r.id == "lc-001"
        assert DOMAIN_NAME == "legal_compliance"

    def test_operational_domain(self):
        from sovereign.memory.domains.operational import OperationalRecord, DOMAIN_NAME
        r = OperationalRecord(id="op-001")
        assert r.id == "op-001"
        assert DOMAIN_NAME == "operational"

    def test_relationship_domain(self):
        from sovereign.memory.domains.relationship import RelationshipRecord, DOMAIN_NAME
        r = RelationshipRecord(id="rel-001")
        assert r.id == "rel-001"
        assert DOMAIN_NAME == "relationship"

    def test_research_domain(self):
        from sovereign.memory.domains.research import ResearchRecord, DOMAIN_NAME
        r = ResearchRecord(id="res-001")
        assert r.id == "res-001"
        assert DOMAIN_NAME == "research"
