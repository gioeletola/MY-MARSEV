"""Tests for swarm agent factory pattern and agent collections."""
from __future__ import annotations
import pytest

from sovereign.swarm.base_agent import BaseAgent
from sovereign.swarm.finance_agents import FINANCE_AGENTS, CashflowAnalystAgent
from sovereign.swarm.business_agents import BUSINESS_AGENTS
from sovereign.swarm.personal_agents import PERSONAL_AGENTS
from sovereign.swarm.security_agents import SECURITY_AGENTS
from sovereign.swarm.offline_agents import OFFLINE_AGENTS


def test_all_finance_agents_have_agent_id():
    for cls in FINANCE_AGENTS:
        assert cls.agent_id, f"{cls.__name__} missing agent_id"


def test_all_business_agents_have_agent_id():
    for cls in BUSINESS_AGENTS:
        assert cls.agent_id, f"{cls.__name__} missing agent_id"


def test_all_personal_agents_have_agent_id():
    for cls in PERSONAL_AGENTS:
        assert cls.agent_id, f"{cls.__name__} missing agent_id"


def test_no_duplicate_agent_ids_in_finance():
    ids = [cls.agent_id for cls in FINANCE_AGENTS]
    assert len(ids) == len(set(ids)), "Duplicate agent_ids in FINANCE_AGENTS"


def test_no_duplicate_agent_ids_in_business():
    ids = [cls.agent_id for cls in BUSINESS_AGENTS]
    assert len(ids) == len(set(ids)), "Duplicate agent_ids in BUSINESS_AGENTS"


def test_agents_are_base_agent_subclasses():
    assert issubclass(FINANCE_AGENTS[0], BaseAgent)
    assert issubclass(BUSINESS_AGENTS[0], BaseAgent)


def test_cashflow_analyst_agent_id():
    assert CashflowAnalystAgent.agent_id == "cashflow_analyst"


def test_finance_agent_count():
    assert len(FINANCE_AGENTS) >= 20


def test_business_agent_count():
    assert len(BUSINESS_AGENTS) >= 60


def test_offline_agents_use_haiku_model():
    for cls in OFFLINE_AGENTS:
        assert "haiku" in cls.model.lower(), f"{cls.agent_id} should use haiku model"


def test_all_agents_have_model_attr():
    for cls in FINANCE_AGENTS + BUSINESS_AGENTS:
        assert hasattr(cls, "model"), f"{cls.__name__} missing model attr"
        assert cls.model, f"{cls.__name__} has empty model"


def test_security_agents_all_subclass_base():
    from sovereign.swarm.security_agents import SECURITY_AGENTS
    for cls in SECURITY_AGENTS:
        assert issubclass(cls, BaseAgent)


def test_personal_workers_load():
    from sovereign.swarm.personal_workers import PERSONAL_WORKERS
    assert len(PERSONAL_WORKERS) >= 20


def test_imperial_agents_load():
    from sovereign.swarm.imperial_agents import IMPERIAL_AGENTS
    assert len(IMPERIAL_AGENTS) >= 20


def test_decision_networking_agents_load():
    from sovereign.swarm.decision_networking_agents import DECISION_NETWORKING_AGENTS
    assert len(DECISION_NETWORKING_AGENTS) >= 10
