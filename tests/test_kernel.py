"""Tests for the constitutional kernel layer."""
import pytest

from sovereign.kernel.action_classes import ActionClass
from sovereign.kernel.constitution import default_constitution
from sovereign.kernel.stop_conditions import IterationState, StopConditionEvaluator


class TestActionClass:
    def test_ordering(self):
        assert ActionClass.READ < ActionClass.SUGGEST < ActionClass.DRAFT < ActionClass.EXECUTE

    def test_requires_approval(self):
        assert ActionClass.EXECUTE.requires_approval(ActionClass.SUGGEST)
        assert not ActionClass.READ.requires_approval(ActionClass.SUGGEST)

    def test_from_str(self):
        assert ActionClass.from_str("execute") == ActionClass.EXECUTE
        assert ActionClass.from_str("READ") == ActionClass.READ

    def test_from_str_invalid(self):
        with pytest.raises(ValueError, match="Unknown action class"):
            ActionClass.from_str("UNKNOWN")


class TestConstitution:
    def test_default_constitution(self):
        c = default_constitution()
        assert len(c.principles) == 10
        assert c.max_action_class == ActionClass.SUGGEST

    def test_render_for_prompt(self):
        c = default_constitution()
        rendered = c.render_for_prompt()
        assert "CONSTITUTIONAL KERNEL" in rendered
        assert "SUGGEST" in rendered
        assert len(rendered) > 500  # must be substantial for cache eligibility

    def test_is_action_permitted(self):
        c = default_constitution(ActionClass.SUGGEST)
        assert c.is_action_permitted(ActionClass.READ)
        assert c.is_action_permitted(ActionClass.SUGGEST)
        assert not c.is_action_permitted(ActionClass.EXECUTE)

    def test_contains_stop_keyword(self):
        c = default_constitution()
        assert c.contains_stop_keyword("please STOP the process")
        assert not c.contains_stop_keyword("continue with the task")

    def test_frozen(self):
        c = default_constitution()
        with pytest.raises((AttributeError, TypeError)):
            c.max_action_class = ActionClass.EXECUTE  # type: ignore[misc]

    def test_constitution_hash_stable(self):
        c = default_constitution()
        assert c.constitution_hash() == c.constitution_hash()
        assert len(c.constitution_hash()) == 12


class TestStopConditions:
    def setup_method(self):
        self.constitution = default_constitution()
        self.evaluator = StopConditionEvaluator(
            constitution=self.constitution,
            max_iterations=5,
            max_tokens_per_session=10_000,
            error_budget=3,
        )

    def test_no_stop_initially(self):
        stop, reason = self.evaluator.should_stop(0, 0, 0)
        assert not stop
        assert reason == ""

    def test_stops_at_max_iterations(self):
        stop, reason = self.evaluator.should_stop(5, 0, 0)
        assert stop
        assert "Max iterations" in reason

    def test_stops_at_token_budget(self):
        stop, reason = self.evaluator.should_stop(0, 10_001, 0)
        assert stop
        assert "Token budget" in reason

    def test_stops_at_error_budget(self):
        stop, reason = self.evaluator.should_stop(0, 0, 3)
        assert stop
        assert "Error budget" in reason

    def test_stops_on_keyword(self):
        stop, reason = self.evaluator.should_stop(0, 0, 0, "please ABORT the task")
        assert stop
        assert "stop keyword" in reason


class TestIterationState:
    def test_tick(self):
        state = IterationState()
        state.tick()
        assert state.iteration == 1

    def test_add_tokens(self):
        state = IterationState()
        state.add_tokens(1000)
        assert state.tokens_used == 1000

    def test_error_tracking(self):
        state = IterationState()
        state.record_error()
        state.record_error()
        assert state.errors == 2
        state.reset_errors()
        assert state.errors == 0
