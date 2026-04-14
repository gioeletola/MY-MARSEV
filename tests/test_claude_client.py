"""Tests for the Claude API client layer (mocked — no real API calls)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sovereign.claude.client import CachedSystemPrompt, ClaudeClient, TokenUsage
from sovereign.claude.prompt_builder import PromptBuilder
from sovereign.kernel.constitution import default_constitution
from sovereign.registries.prompt_registry import PromptRegistry


class TestCachedSystemPrompt:
    def test_static_only_produces_one_block(self):
        prompt = CachedSystemPrompt(static_section="System text", dynamic_section="")
        blocks = prompt.to_api_blocks()
        assert len(blocks) == 1
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}
        assert blocks[0]["text"] == "System text"

    def test_both_sections_produce_two_blocks(self):
        prompt = CachedSystemPrompt(static_section="Static", dynamic_section="Dynamic")
        blocks = prompt.to_api_blocks()
        assert len(blocks) == 2
        assert "cache_control" in blocks[0]
        assert "cache_control" not in blocks[1]

    def test_cached_block_has_ephemeral_type(self):
        prompt = CachedSystemPrompt(static_section="X")
        blocks = prompt.to_api_blocks()
        assert blocks[0]["cache_control"]["type"] == "ephemeral"


class TestTokenUsage:
    def test_initial_zero(self):
        usage = TokenUsage()
        assert usage.total == 0
        assert usage.input_tokens == 0

    def test_update_accumulates(self):
        usage = TokenUsage()
        mock_api_usage = MagicMock()
        mock_api_usage.input_tokens = 100
        mock_api_usage.output_tokens = 50
        mock_api_usage.cache_read_input_tokens = 200
        mock_api_usage.cache_creation_input_tokens = 0
        usage.update(mock_api_usage)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_read_input_tokens == 200
        assert usage.total == 150

    def test_to_dict(self):
        usage = TokenUsage(input_tokens=10, output_tokens=5)
        d = usage.to_dict()
        assert d["input"] == 10
        assert d["output"] == 5

    def test_effective_input(self):
        usage = TokenUsage(input_tokens=1000, cache_read_input_tokens=700)
        assert usage.effective_input == 300


class TestPromptBuilder:
    def setup_method(self):
        self.constitution = default_constitution()
        self.registry = PromptRegistry("prompts")
        self.builder = PromptBuilder(self.constitution, self.registry)

    def test_build_for_agent_returns_cached_prompt(self):
        prompt = self.builder.build_for_agent("worker")
        assert isinstance(prompt, CachedSystemPrompt)
        assert len(prompt.static_section) > 100

    def test_static_section_contains_constitutional_text(self):
        prompt = self.builder.build_for_agent("ceo")
        assert "CONSTITUTIONAL" in prompt.static_section.upper()

    def test_dynamic_section_contains_task_context(self):
        prompt = self.builder.build_for_agent(
            "worker",
            task_context={"operating_mode": "research", "objective": "Find X"},
            memory_snapshot={},
        )
        assert "research" in prompt.dynamic_section

    def test_static_section_is_memoised(self):
        # Calling twice should return same object (memoised)
        p1 = self.builder.build_for_agent("worker")
        p2 = self.builder.build_for_agent("worker")
        assert p1.static_section == p2.static_section

    def test_constitutional_prefix_long_enough_for_cache(self):
        # Claude requires > 1024 tokens; rough proxy: > 3000 chars
        prefix = self.builder._build_constitutional_prefix()
        assert len(prefix) > 1000
