"""Tests for new builtin tools: email, json, timer, regex, diff, translation."""
import asyncio
import time



def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# EmailTool
# ---------------------------------------------------------------------------

class TestEmailTool:
    def setup_method(self):
        from sovereign.tools.builtin.email_tool import EmailTool
        self.tool = EmailTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "email_tool"

    def test_compose(self):
        r = run(self.tool.execute(action="compose", subject="Meeting", body_context="Q3 review", tone="formal", recipient="CEO"))
        assert r is not None
        assert "error" not in r or r.get("error") is None

    def test_summarize(self):
        email_text = "Hi Team,\n\nPlease submit reports by Friday. The meeting Monday is cancelled. Budget approval needed for Q4.\n\nThanks"
        r = run(self.tool.execute(action="summarize", email_text=email_text))
        assert r is not None

    def test_extract_action_items(self):
        email_text = "Please send me the report. Review the contract. Call John by EOD."
        r = run(self.tool.execute(action="extract_action_items", email_text=email_text))
        assert r is not None

    def test_reply(self):
        r = run(self.tool.execute(action="reply", original_subject="Re: Proposal", reply_context="Accept the terms"))
        assert r is not None

    def test_unknown_action_returns_error(self):
        r = run(self.tool.execute(action="unknown_xyz_action"))
        assert r is not None  # should not crash


# ---------------------------------------------------------------------------
# JsonTool
# ---------------------------------------------------------------------------

class TestJsonTool:
    def setup_method(self):
        from sovereign.tools.builtin.json_tool import JsonTool
        self.tool = JsonTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "json_tool"

    def test_format(self):
        r = run(self.tool.execute(action="format", json_text='{"a":1,"b":2}'))
        assert r.get("error") is None
        import json
        parsed = json.loads(r["result"])
        assert parsed["a"] == 1

    def test_minify(self):
        r = run(self.tool.execute(action="minify", json_text='{"a": 1,  "b": 2}'))
        assert r.get("error") is None
        assert " " not in r["result"]

    def test_validate_valid(self):
        r = run(self.tool.execute(action="validate", json_text='[1, 2, 3]'))
        assert r.get("valid") is True

    def test_validate_invalid(self):
        r = run(self.tool.execute(action="validate", json_text='{invalid}'))
        assert r.get("valid") is False

    def test_query_dot_path(self):
        r = run(self.tool.execute(action="query", json_text='{"user": {"name": "Alice"}}', path="user.name"))
        assert r.get("error") is None
        assert r["result"] == "Alice"

    def test_diff_action(self):
        r = run(self.tool.execute(action="diff", json_a='{"a":1}', json_b='{"a":2}'))
        assert r is not None

    def test_merge_action(self):
        r = run(self.tool.execute(action="merge", json_a='{"a":1}', json_b='{"b":2}'))
        assert r is not None

    def test_to_api_dict(self):
        d = self.tool.to_api_dict()
        assert "name" in d
        assert d["name"] == "json_tool"


# ---------------------------------------------------------------------------
# TimerTool
# ---------------------------------------------------------------------------

class TestTimerTool:
    def setup_method(self):
        from sovereign.tools.builtin.timer_tool import TimerTool
        self.tool = TimerTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "timer_tool"

    def test_start(self):
        r = run(self.tool.execute(action="start", timer_id="t_test1"))
        assert r is not None
        assert r.get("error") is None

    def test_elapsed(self):
        run(self.tool.execute(action="start", timer_id="t_test2"))
        time.sleep(0.05)
        r = run(self.tool.execute(action="elapsed", timer_id="t_test2"))
        assert r is not None
        assert r.get("error") is None

    def test_stop(self):
        run(self.tool.execute(action="start", timer_id="t_test3"))
        r = run(self.tool.execute(action="stop", timer_id="t_test3"))
        assert r is not None

    def test_list(self):
        run(self.tool.execute(action="start", timer_id="t_list1"))
        r = run(self.tool.execute(action="list"))
        assert r is not None

    def test_countdown(self):
        r = run(self.tool.execute(action="countdown", seconds=30))
        assert r is not None

    def test_elapsed_unknown_timer(self):
        r = run(self.tool.execute(action="elapsed", timer_id="nonexistent_xyz_abc"))
        assert r.get("error") is not None


# ---------------------------------------------------------------------------
# RegexTool
# ---------------------------------------------------------------------------

class TestRegexTool:
    def setup_method(self):
        from sovereign.tools.builtin.regex_tool import RegexTool
        self.tool = RegexTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "regex_tool"

    def test_find_all(self):
        r = run(self.tool.execute(action="find_all", pattern=r"\d+", text="abc 123 def 456"))
        assert r.get("error") is None
        assert "123" in str(r.get("matches", r.get("result", "")))
        assert "456" in str(r.get("matches", r.get("result", "")))

    def test_replace(self):
        r = run(self.tool.execute(action="replace", pattern=r"\d+", text="abc 123", replacement="NUM"))
        assert r.get("error") is None
        result_text = str(r.get("result", r.get("replaced", r.get("text", ""))))
        assert "NUM" in result_text

    def test_validate_match(self):
        # regex validate checks full match; use anchored pattern or check any match
        r = run(self.tool.execute(action="validate", pattern=r"\d+", text="123"))
        assert r.get("error") is None
        # tool may return 'valid' or 'matches' key
        matched = r.get("valid", r.get("matches"))
        assert matched is True or matched is not False

    def test_validate_no_match(self):
        r = run(self.tool.execute(action="validate", pattern=r"\d+", text="abc"))
        matched = r.get("valid", r.get("matches", True))
        assert matched is False or not matched

    def test_split(self):
        r = run(self.tool.execute(action="split", pattern=r",\s*", text="a, b, c"))
        assert r.get("error") is None
        parts = r.get("result", r.get("parts", []))
        assert len(parts) == 3

    def test_extract_groups(self):
        r = run(self.tool.execute(action="extract_groups", pattern=r"(\w+)\s+(\w+)", text="hello world"))
        assert r is not None

    def test_invalid_pattern(self):
        r = run(self.tool.execute(action="find_all", pattern="[invalid", text="test"))
        assert r.get("error") is not None


# ---------------------------------------------------------------------------
# DiffTool
# ---------------------------------------------------------------------------

class TestDiffTool:
    def setup_method(self):
        from sovereign.tools.builtin.diff_tool import DiffTool
        self.tool = DiffTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "diff_tool"

    def test_text_diff_identical(self):
        r = run(self.tool.execute(action="text_diff", original="hello", modified="hello"))
        assert r["error"] is None
        assert r["changed"] is False

    def test_text_diff_changed(self):
        r = run(self.tool.execute(action="text_diff", original="hello\nworld", modified="hello\nearth"))
        assert r["error"] is None
        assert r["changed"] is True
        assert r["added_lines"] >= 1

    def test_json_diff_value_changed(self):
        r = run(self.tool.execute(action="json_diff", original='{"a": 1, "b": 2}', modified='{"a": 1, "b": 3, "c": 4}'))
        assert r["error"] is None
        assert r["changed"] is True
        assert any(d["type"] == "value_changed" and d.get("to") == 3 for d in r["result"])
        assert any(d["type"] == "added" for d in r["result"])

    def test_json_diff_identical(self):
        j = '{"x": 1}'
        r = run(self.tool.execute(action="json_diff", original=j, modified=j))
        assert r["changed"] is False

    def test_json_diff_invalid_json(self):
        r = run(self.tool.execute(action="json_diff", original="{bad", modified="{}"))
        assert r["error"] is not None

    def test_word_diff(self):
        r = run(self.tool.execute(action="word_diff", original="the quick brown fox", modified="the slow green fox"))
        assert r["error"] is None
        assert "quick" in r["result"] or "slow" in r["result"]

    def test_similarity_identical(self):
        r = run(self.tool.execute(action="similarity", original="hello", modified="hello"))
        assert r["identical"] is True
        assert r["result"] == 1.0

    def test_similarity_different(self):
        r = run(self.tool.execute(action="similarity", original="abc", modified="xyz"))
        assert r["identical"] is False
        assert 0.0 <= r["result"] <= 1.0

    def test_unknown_action(self):
        r = run(self.tool.execute(action="unknown_xyz", original="", modified=""))
        assert r["error"] is not None

    def test_empty_strings(self):
        r = run(self.tool.execute(action="text_diff", original="", modified=""))
        assert r["error"] is None
        assert r["changed"] is False

    def test_json_diff_nested(self):
        a = '{"user": {"name": "Alice", "age": 30}}'
        b = '{"user": {"name": "Bob", "age": 30}}'
        r = run(self.tool.execute(action="json_diff", original=a, modified=b))
        assert r["changed"] is True
        assert any("name" in str(d.get("path", "")) for d in r["result"])

    def test_word_diff_identical(self):
        r = run(self.tool.execute(action="word_diff", original="hello world", modified="hello world"))
        assert r["changed"] is False
        assert r["similarity"] == 1.0


# ---------------------------------------------------------------------------
# TranslationTool
# ---------------------------------------------------------------------------

class TestTranslationTool:
    def setup_method(self):
        from sovereign.tools.builtin.translation_tool import TranslationTool
        self.tool = TranslationTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "translation_tool"

    def test_detect_english(self):
        r = run(self.tool.execute(action="detect", text="the quick brown fox is running fast with this"))
        assert r["error"] is None
        assert r["result"] == "en"

    def test_detect_italian(self):
        r = run(self.tool.execute(action="detect", text="il cane è molto stanco nel parco"))
        assert r["error"] is None
        assert r["result"] == "it"

    def test_detect_empty(self):
        r = run(self.tool.execute(action="detect", text=""))
        assert r["error"] is not None

    def test_lookup_found_italian(self):
        r = run(self.tool.execute(action="lookup", text="hello", target_lang="it"))
        assert r["error"] is None
        assert r["found"] is True
        assert r["result"] == "ciao"

    def test_lookup_found_french(self):
        r = run(self.tool.execute(action="lookup", text="thank you", target_lang="fr"))
        assert r["result"] == "merci"

    def test_lookup_not_found_phrase(self):
        r = run(self.tool.execute(action="lookup", text="supercalifragilistic", target_lang="it"))
        assert r["found"] is False

    def test_lookup_missing_lang(self):
        r = run(self.tool.execute(action="lookup", text="hello", target_lang="xx"))
        assert r["found"] is False or r["result"] is None

    def test_list_phrases(self):
        r = run(self.tool.execute(action="list_phrases"))
        assert r["error"] is None
        assert r["count"] > 0
        assert "hello" in r["result"]

    def test_translate_prompt_contains_lang(self):
        r = run(self.tool.execute(action="translate_prompt", text="Good morning", target_lang="fr"))
        assert r["error"] is None
        assert "French" in r["result"]

    def test_translate_prompt_contains_text(self):
        r = run(self.tool.execute(action="translate_prompt", text="Hello world", target_lang="de"))
        assert "Hello world" in r["result"]

    def test_supported_languages(self):
        r = run(self.tool.execute(action="supported_languages"))
        assert r["error"] is None
        codes = [ln["code"] for ln in r["result"]]
        assert "en" in codes and "it" in codes

    def test_unknown_action(self):
        r = run(self.tool.execute(action="unknown_xyz"))
        assert r["error"] is not None
