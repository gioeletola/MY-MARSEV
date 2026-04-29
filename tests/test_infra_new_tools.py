"""Tests for xml_tool, environment_tool, crypto_tool, json_tool improvements, and WS ticket auth."""
from __future__ import annotations

import asyncio
import os


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# XmlTool
# ---------------------------------------------------------------------------

class TestXmlTool:
    def setup_method(self):
        from sovereign.tools.builtin.xml_tool import XmlTool
        self.tool = XmlTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "xml_tool"

    def test_parse_basic(self):
        xml = "<root><child>hello</child></root>"
        r = run(self.tool.execute(action="parse", xml=xml))
        assert r["error"] is None
        assert r["tag"] == "root"
        assert r["result"]["children"][0]["text"] == "hello"

    def test_to_dict(self):
        xml = "<person name='Alice'><age>30</age></person>"
        r = run(self.tool.execute(action="to_dict", xml=xml))
        assert r["error"] is None
        assert r["result"]["tag"] == "person"
        assert r["result"]["attrs"]["name"] == "Alice"

    def test_find(self):
        xml = "<root><item id='1'>first</item><item id='2'>second</item></root>"
        r = run(self.tool.execute(action="find", xml=xml, path="item"))
        assert r["error"] is None
        assert r["result"]["attrs"]["id"] == "1"

    def test_find_not_found(self):
        xml = "<root></root>"
        r = run(self.tool.execute(action="find", xml=xml, path="missing"))
        assert r["error"] is not None

    def test_find_all(self):
        xml = "<root><item>a</item><item>b</item><item>c</item></root>"
        r = run(self.tool.execute(action="find_all", xml=xml, path="item"))
        assert r["count"] == 3
        assert len(r["result"]) == 3

    def test_get_text_root(self):
        xml = "<greeting>Hello World</greeting>"
        r = run(self.tool.execute(action="get_text", xml=xml, path="."))
        assert r["result"] == "Hello World"

    def test_get_text_child(self):
        xml = "<root><title>My Title</title></root>"
        r = run(self.tool.execute(action="get_text", xml=xml, path="title"))
        assert r["result"] == "My Title"

    def test_get_attrs(self):
        xml = "<link href='https://example.com' rel='nofollow'/>"
        r = run(self.tool.execute(action="get_attrs", xml=xml, path="."))
        assert r["error"] is None
        assert r["result"]["href"] == "https://example.com"

    def test_get_attrs_not_found(self):
        xml = "<root></root>"
        r = run(self.tool.execute(action="get_attrs", xml=xml, path="missing"))
        assert r["error"] is not None

    def test_count(self):
        xml = "<data><row/><row/><row/><row/></data>"
        r = run(self.tool.execute(action="count", xml=xml, path="row"))
        assert r["result"] == 4

    def test_validate_valid(self):
        r = run(self.tool.execute(action="validate", xml="<root><child/></root>"))
        assert r["result"] is True
        assert r["error"] is None

    def test_validate_invalid(self):
        r = run(self.tool.execute(action="validate", xml="<unclosed>"))
        assert r["result"] is False
        assert r["error"] is not None

    def test_build_simple(self):
        r = run(self.tool.execute(action="build", tag="greeting", text="Hello"))
        assert r["error"] is None
        assert "<greeting>" in r["result"]
        assert "Hello" in r["result"]

    def test_build_with_attrs(self):
        r = run(self.tool.execute(action="build", tag="link", attrs={"href": "https://example.com"}))
        assert "href" in r["result"]

    def test_build_with_children(self):
        r = run(self.tool.execute(
            action="build",
            tag="list",
            children=[{"tag": "item", "text": "one"}, {"tag": "item", "text": "two"}],
        ))
        assert r["error"] is None
        assert "one" in r["result"]
        assert "two" in r["result"]

    def test_strip_namespaces(self):
        xml = '<root xmlns:ns="http://example.com"><ns:child>text</ns:child></root>'
        r = run(self.tool.execute(action="strip_namespaces", xml=xml))
        assert r["error"] is None
        assert "xmlns" not in r["result"]

    def test_parse_error(self):
        r = run(self.tool.execute(action="parse", xml="not xml at all <<<"))
        assert r["error"] is not None

    def test_unknown_action(self):
        r = run(self.tool.execute(action="unknown", xml="<root/>"))
        assert r["error"] is not None


# ---------------------------------------------------------------------------
# EnvironmentTool
# ---------------------------------------------------------------------------

class TestEnvironmentTool:
    def setup_method(self):
        from sovereign.tools.builtin.environment_tool import EnvironmentTool
        self.tool = EnvironmentTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "environment_tool"

    def test_python_info(self):
        r = run(self.tool.execute(action="python_info"))
        assert r["error"] is None
        assert "version" in r["result"]
        assert "3." in r["result"]["version"]

    def test_os_info(self):
        r = run(self.tool.execute(action="os_info"))
        assert r["error"] is None
        assert r["result"]["system"] in ("Linux", "Windows", "Darwin")

    def test_platform_info(self):
        r = run(self.tool.execute(action="platform_info"))
        assert r["error"] is None
        assert r["result"]["pid"] > 0
        assert r["result"]["cpu_count"] is not None or r["result"]["cpu_count"] is None

    def test_cwd(self):
        r = run(self.tool.execute(action="cwd"))
        assert r["error"] is None
        assert "/" in r["result"] or "\\" in r["result"]

    def test_sys_path(self):
        r = run(self.tool.execute(action="sys_path"))
        assert r["error"] is None
        assert isinstance(r["result"], list)
        assert r["count"] > 0

    def test_env_var_safe(self):
        os.environ["TEST_SAFE_VAR_SOVEREIGN"] = "hello"
        r = run(self.tool.execute(action="env_var", name="TEST_SAFE_VAR_SOVEREIGN"))
        assert r["result"] == "hello"
        assert r["found"] is True
        del os.environ["TEST_SAFE_VAR_SOVEREIGN"]

    def test_env_var_not_found(self):
        r = run(self.tool.execute(action="env_var", name="DEFINITELY_NOT_SET_XYZ"))
        assert r["found"] is False
        assert r["result"] is None

    def test_env_var_blocked_secret(self):
        r = run(self.tool.execute(action="env_var", name="MY_SECRET_KEY"))
        assert r["error"] is not None

    def test_env_var_blocked_token(self):
        r = run(self.tool.execute(action="env_var", name="API_TOKEN"))
        assert r["error"] is not None

    def test_env_var_no_name(self):
        r = run(self.tool.execute(action="env_var", name=""))
        assert r["error"] is not None

    def test_env_list(self):
        r = run(self.tool.execute(action="env_list"))
        assert r["error"] is None
        assert isinstance(r["result"], dict)
        assert r["count"] >= 0

    def test_env_list_with_prefix(self):
        r = run(self.tool.execute(action="env_list", prefix="PATH"))
        assert r["error"] is None

    def test_runtime_summary(self):
        r = run(self.tool.execute(action="runtime_summary"))
        assert r["error"] is None
        assert "python" in r["result"]
        assert "pid" in r["result"]
        assert "cwd" in r["result"]

    def test_unknown_action(self):
        r = run(self.tool.execute(action="unknown"))
        assert r["error"] is not None


# ---------------------------------------------------------------------------
# CryptoTool
# ---------------------------------------------------------------------------

class TestCryptoTool:
    def setup_method(self):
        from sovereign.tools.builtin.crypto_tool import CryptoTool
        self.tool = CryptoTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "crypto_tool"

    def test_hash_sha256(self):
        r = run(self.tool.execute(action="hash", data="hello", algorithm="sha256"))
        assert r["error"] is None
        assert len(r["result"]) == 64  # 32 bytes hex
        assert r["algorithm"] == "sha256"

    def test_hash_sha512(self):
        r = run(self.tool.execute(action="hash", data="hello", algorithm="sha512"))
        assert r["error"] is None
        assert len(r["result"]) == 128

    def test_hash_blake2b(self):
        r = run(self.tool.execute(action="hash", data="test", algorithm="blake2b"))
        assert r["error"] is None

    def test_hash_base64_encoding(self):
        r = run(self.tool.execute(action="hash", data="hello", algorithm="sha256", encoding="base64"))
        assert r["error"] is None
        assert len(r["result"]) < 64  # base64 is shorter than hex

    def test_hash_unknown_algorithm(self):
        r = run(self.tool.execute(action="hash", data="test", algorithm="md6"))
        assert r["error"] is not None

    def test_hash_deterministic(self):
        r1 = run(self.tool.execute(action="hash", data="same_input", algorithm="sha256"))
        r2 = run(self.tool.execute(action="hash", data="same_input", algorithm="sha256"))
        assert r1["result"] == r2["result"]

    def test_hash_different_inputs(self):
        r1 = run(self.tool.execute(action="hash", data="input_a", algorithm="sha256"))
        r2 = run(self.tool.execute(action="hash", data="input_b", algorithm="sha256"))
        assert r1["result"] != r2["result"]

    def test_hmac_sha256(self):
        r = run(self.tool.execute(action="hmac", data="message", key="secret", algorithm="sha256"))
        assert r["error"] is None
        assert len(r["result"]) == 64

    def test_hmac_no_key(self):
        r = run(self.tool.execute(action="hmac", data="message", key=""))
        assert r["error"] is not None

    def test_hmac_unsupported_algorithm(self):
        r = run(self.tool.execute(action="hmac", data="msg", key="key", algorithm="sha3_256"))
        assert r["error"] is not None

    def test_token_generation(self):
        r = run(self.tool.execute(action="token", nbytes=32))
        assert r["error"] is None
        assert len(r["result"]) > 20
        assert r["bytes"] == 32

    def test_token_unique(self):
        r1 = run(self.tool.execute(action="token"))
        r2 = run(self.tool.execute(action="token"))
        assert r1["result"] != r2["result"]

    def test_token_clamped(self):
        r = run(self.tool.execute(action="token", nbytes=99999))
        assert r["bytes"] == 256  # clamped to max

    def test_random_bytes_hex(self):
        r = run(self.tool.execute(action="random_bytes", nbytes=16, encoding="hex"))
        assert r["error"] is None
        assert len(r["result"]) == 32  # 16 bytes = 32 hex chars

    def test_random_bytes_base64(self):
        r = run(self.tool.execute(action="random_bytes", nbytes=16, encoding="base64"))
        assert r["error"] is None
        assert len(r["result"]) > 0

    def test_derive_key(self):
        r = run(self.tool.execute(action="derive_key", key="password", iterations=1000, nbytes=32))
        assert r["error"] is None
        assert len(r["result"]) == 64  # 32 bytes hex
        assert "salt" in r
        assert r["iterations"] == 1000

    def test_derive_key_with_salt(self):
        import os
        salt = os.urandom(16).hex()
        r1 = run(self.tool.execute(action="derive_key", key="password", salt=salt, iterations=1000))
        r2 = run(self.tool.execute(action="derive_key", key="password", salt=salt, iterations=1000))
        assert r1["result"] == r2["result"]  # same salt → same result

    def test_compare_equal(self):
        r = run(self.tool.execute(action="compare", a="hello", b="hello"))
        assert r["result"] is True

    def test_compare_not_equal(self):
        r = run(self.tool.execute(action="compare", a="hello", b="world"))
        assert r["result"] is False

    def test_checksum(self):
        r = run(self.tool.execute(action="checksum", data="test data"))
        assert r["error"] is None
        assert "sha256" in r["result"]
        assert "md5" in r["result"]
        assert "sha1" in r["result"]
        assert r["size_bytes"] > 0

    def test_unknown_action(self):
        r = run(self.tool.execute(action="unknown"))
        assert r["error"] is not None


# ---------------------------------------------------------------------------
# WS Ticket auth
# ---------------------------------------------------------------------------

class TestWsTicket:
    def test_create_and_consume_ticket(self):
        from sovereign.api.auth import consume_ws_ticket, create_ws_ticket
        ticket = create_ws_ticket()
        assert isinstance(ticket, str)
        assert len(ticket) > 10
        assert consume_ws_ticket(ticket) is True

    def test_ticket_single_use(self):
        from sovereign.api.auth import consume_ws_ticket, create_ws_ticket
        ticket = create_ws_ticket()
        assert consume_ws_ticket(ticket) is True
        assert consume_ws_ticket(ticket) is False  # already consumed

    def test_invalid_ticket(self):
        from sovereign.api.auth import consume_ws_ticket
        assert consume_ws_ticket("not-a-real-ticket") is False

    def test_expired_ticket_pruned(self):
        import time
        from sovereign.api.auth import _ws_ticket_lock, _ws_tickets, consume_ws_ticket
        fake_ticket = "expired-test-ticket-123"
        with _ws_ticket_lock:
            _ws_tickets[fake_ticket] = time.time() - 1  # already expired
        assert consume_ws_ticket(fake_ticket) is False  # pruned on access

    def test_multiple_tickets_independent(self):
        from sovereign.api.auth import consume_ws_ticket, create_ws_ticket
        t1 = create_ws_ticket()
        t2 = create_ws_ticket()
        assert t1 != t2
        assert consume_ws_ticket(t1) is True
        assert consume_ws_ticket(t2) is True


# ---------------------------------------------------------------------------
# JSON Tool — improve coverage of low-hit paths
# ---------------------------------------------------------------------------

class TestJsonToolExtra:
    def setup_method(self):
        from sovereign.tools.builtin.json_tool import JsonTool
        self.tool = JsonTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "json_tool"

    def test_format_pretty(self):
        r = run(self.tool.execute(action="format", json_text='{"x":1,"y":2}'))
        assert r["error"] is None
        assert "\n" in r["result"]

    def test_format_no_input(self):
        r = run(self.tool.execute(action="format", json_text=""))
        assert r["error"] is not None

    def test_minify(self):
        r = run(self.tool.execute(action="minify", json_text='{"x": 1, "y": 2}'))
        assert r["error"] is None
        assert " " not in r["result"]

    def test_validate_valid(self):
        r = run(self.tool.execute(action="validate", json_text='{"a": 1}'))
        assert r["valid"] is True
        assert r["error"] is None

    def test_validate_invalid(self):
        r = run(self.tool.execute(action="validate", json_text="not json"))
        assert r["valid"] is False

    def test_validate_no_input(self):
        r = run(self.tool.execute(action="validate", json_text=""))
        assert r["valid"] is False

    def test_query_dot_path(self):
        r = run(self.tool.execute(
            action="query",
            json_text='{"user": {"name": "Alice", "age": 30}}',
            path="user.name",
        ))
        assert r["error"] is None
        assert r["result"] == "Alice"

    def test_query_array_index(self):
        r = run(self.tool.execute(
            action="query",
            json_text='{"items": ["a", "b", "c"]}',
            path="items.1",
        ))
        assert r["error"] is None
        assert r["result"] == "b"

    def test_query_missing_key(self):
        r = run(self.tool.execute(
            action="query",
            json_text='{"a": 1}',
            path="b.c",
        ))
        assert r["error"] is not None

    def test_query_no_path(self):
        r = run(self.tool.execute(action="query", json_text='{"a": 1}', path=""))
        assert r["error"] is not None

    def test_diff_identical(self):
        r = run(self.tool.execute(
            action="diff",
            json_a='{"a": 1}',
            json_b='{"a": 1}',
        ))
        assert r["error"] is None
        assert r["differences"] == []
        assert r["identical"] is True

    def test_diff_added_key(self):
        r = run(self.tool.execute(
            action="diff",
            json_a='{"a": 1}',
            json_b='{"a": 1, "b": 2}',
        ))
        assert r["error"] is None
        assert any(d["type"] == "added" for d in r["differences"])

    def test_diff_removed_key(self):
        r = run(self.tool.execute(
            action="diff",
            json_a='{"a": 1, "b": 2}',
            json_b='{"a": 1}',
        ))
        assert any(d["type"] == "removed" for d in r["differences"])

    def test_diff_changed_value(self):
        r = run(self.tool.execute(
            action="diff",
            json_a='{"a": 1}',
            json_b='{"a": 2}',
        ))
        assert any(d["type"] == "changed" for d in r["differences"])

    def test_diff_missing_inputs(self):
        r = run(self.tool.execute(action="diff", json_a='{"a":1}', json_b=""))
        assert r["error"] is not None

    def test_diff_arrays(self):
        r = run(self.tool.execute(
            action="diff",
            json_a='[1, 2, 3]',
            json_b='[1, 2, 99]',
        ))
        assert r["error"] is None
        assert any(d["type"] == "changed" for d in r["differences"])

    def test_merge_dicts(self):
        r = run(self.tool.execute(
            action="merge",
            json_a='{"a": 1, "b": 2}',
            json_b='{"b": 99, "c": 3}',
        ))
        assert r["error"] is None
        assert r["result"]["c"] == 3
        assert r["result"]["b"] == 99

    def test_merge_deep(self):
        r = run(self.tool.execute(
            action="merge",
            json_a='{"x": {"a": 1, "b": 2}}',
            json_b='{"x": {"b": 99, "c": 3}}',
        ))
        assert r["error"] is None
        assert r["result"]["x"]["a"] == 1
        assert r["result"]["x"]["b"] == 99

    def test_merge_missing_inputs(self):
        r = run(self.tool.execute(action="merge", json_a='{"a":1}', json_b=""))
        assert r["error"] is not None

    def test_merge_non_dict(self):
        r = run(self.tool.execute(action="merge", json_a="[1,2]", json_b="[3,4]"))
        assert r["error"] is not None

    def test_unknown_action(self):
        r = run(self.tool.execute(action="nonexistent_action", json_text="{}"))
        assert r["error"] is not None
