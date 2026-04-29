"""Tests for zero-coverage builtin tools: color, markdown, number, template_render, uuid."""
from __future__ import annotations

import asyncio
import re


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# ColorTool
# ---------------------------------------------------------------------------

class TestColorTool:
    def setup_method(self):
        from sovereign.tools.builtin.color_tool import ColorTool
        self.tool = ColorTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "color_tool"

    def test_hex_to_rgb(self):
        r = run(self.tool.execute(action="hex_to_rgb", color="#FF0000"))
        assert r["result"] == {"r": 255, "g": 0, "b": 0}
        assert r["error"] is None

    def test_hex_to_rgb_short(self):
        r = run(self.tool.execute(action="hex_to_rgb", color="#F00"))
        assert r["result"]["r"] == 255

    def test_hex_to_rgb_named(self):
        r = run(self.tool.execute(action="hex_to_rgb", color="red"))
        assert r["result"]["r"] == 255

    def test_rgb_to_hex(self):
        r = run(self.tool.execute(action="rgb_to_hex", r=255, g=0, b=0))
        assert r["result"] == "#FF0000"

    def test_rgb_to_hex_zero(self):
        r = run(self.tool.execute(action="rgb_to_hex", r=0, g=0, b=0))
        assert r["result"] == "#000000"

    def test_hex_to_hsl(self):
        r = run(self.tool.execute(action="hex_to_hsl", color="#FF0000"))
        assert r["error"] is None
        assert r["result"]["h"] == 0.0
        assert "css" in r

    def test_hsl_to_hex(self):
        r = run(self.tool.execute(action="hsl_to_hex", h=0.0, s=100.0, lightness=50.0))
        assert r["error"] is None
        assert isinstance(r["result"], str)
        assert r["result"].startswith("#")

    def test_complement(self):
        r = run(self.tool.execute(action="complement", color="#FF0000"))
        assert r["error"] is None
        assert r["original"] == "#FF0000"
        assert r["result"].startswith("#")

    def test_palette_complementary(self):
        r = run(self.tool.execute(action="palette", color="#FF0000", palette_type="complementary"))
        assert r["error"] is None
        assert len(r["result"]) == 2
        assert r["type"] == "complementary"

    def test_palette_analogous(self):
        r = run(self.tool.execute(action="palette", color="#FF0000", palette_type="analogous"))
        assert len(r["result"]) == 5

    def test_palette_triadic(self):
        r = run(self.tool.execute(action="palette", color="#FF0000", palette_type="triadic"))
        assert len(r["result"]) == 3

    def test_palette_tetradic(self):
        r = run(self.tool.execute(action="palette", color="#FF0000", palette_type="tetradic"))
        assert len(r["result"]) == 4

    def test_palette_monochromatic(self):
        r = run(self.tool.execute(action="palette", color="#FF0000", palette_type="monochromatic"))
        assert len(r["result"]) == 5

    def test_lighten(self):
        r = run(self.tool.execute(action="lighten", color="#000000", amount=50.0))
        assert r["error"] is None
        assert r["result"] != "#000000"

    def test_darken(self):
        r = run(self.tool.execute(action="darken", color="#FFFFFF", amount=50.0))
        assert r["error"] is None
        assert r["result"] != "#FFFFFF"

    def test_contrast_ratio_black_white(self):
        r = run(self.tool.execute(action="contrast_ratio", color="#000000", color2="#FFFFFF"))
        assert r["result"] == 21.0
        assert r["wcag_aaa"] is True
        assert r["rating"] == "AAA"

    def test_contrast_ratio_same_color(self):
        r = run(self.tool.execute(action="contrast_ratio", color="#808080", color2="#808080"))
        assert r["result"] == 1.0

    def test_mix_equal_weight(self):
        r = run(self.tool.execute(action="mix", color="#000000", color2="#FFFFFF", weight=0.5))
        assert r["error"] is None
        assert r["result"] == "#808080"

    def test_mix_weight_clamped(self):
        r = run(self.tool.execute(action="mix", color="#000000", color2="#FF0000", weight=1.1))
        assert r["weight"] == 1.0

    def test_named_to_hex(self):
        r = run(self.tool.execute(action="named_to_hex", color="blue"))
        assert r["result"] == "#0000FF"

    def test_named_to_hex_unknown(self):
        r = run(self.tool.execute(action="named_to_hex", color="notacolor"))
        assert r["result"] is None
        assert r["error"] is not None

    def test_unknown_action(self):
        r = run(self.tool.execute(action="unknown"))
        assert r["error"] is not None

    def test_css_output_hex_to_rgb(self):
        r = run(self.tool.execute(action="hex_to_rgb", color="#00FF00"))
        assert "css" in r
        assert "rgb(" in r["css"]


# ---------------------------------------------------------------------------
# MarkdownTool
# ---------------------------------------------------------------------------

class TestMarkdownTool:
    def setup_method(self):
        from sovereign.tools.builtin.markdown_tool import MarkdownTool
        self.tool = MarkdownTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "markdown_tool"

    def test_table_basic(self):
        r = run(self.tool.execute(action="table", headers=["Name", "Age"], rows=[["Alice", 30], ["Bob", 25]]))
        assert r["error"] is None
        assert "Name" in r["result"]
        assert "Alice" in r["result"]
        assert r["rows"] == 2
        assert r["cols"] == 2

    def test_table_no_headers(self):
        r = run(self.tool.execute(action="table", headers=[], rows=[]))
        assert r["error"] is not None

    def test_code_block(self):
        r = run(self.tool.execute(action="code_block", language="python", code="print('hi')"))
        assert "```python" in r["result"]
        assert "print" in r["result"]

    def test_heading_level_2(self):
        r = run(self.tool.execute(action="heading", level=2, title="My Title"))
        assert r["result"] == "## My Title"

    def test_heading_clamped_to_1(self):
        r = run(self.tool.execute(action="heading", level=0, title="Title"))
        assert r["result"].startswith("# ")

    def test_heading_clamped_to_6(self):
        r = run(self.tool.execute(action="heading", level=10, title="Title"))
        assert r["result"].startswith("###### ")

    def test_toc(self):
        md = "# Intro\n## Section A\n### Sub-section\n## Section B"
        r = run(self.tool.execute(action="toc", text=md))
        assert r["error"] is None
        assert r["heading_count"] == 4
        assert "Intro" in r["result"]
        assert "Section A" in r["result"]

    def test_extract_links(self):
        md = "See [Google](https://google.com) and [GitHub](https://github.com)"
        r = run(self.tool.execute(action="extract_links", text=md))
        assert r["count"] == 2
        assert r["result"][0]["text"] == "Google"
        assert r["result"][0]["url"] == "https://google.com"

    def test_extract_links_none(self):
        r = run(self.tool.execute(action="extract_links", text="No links here"))
        assert r["count"] == 0

    def test_extract_headings(self):
        md = "# H1\n## H2\n### H3"
        r = run(self.tool.execute(action="extract_headings", text=md))
        assert r["count"] == 3
        assert r["result"][0] == {"level": 1, "text": "H1"}
        assert r["result"][1] == {"level": 2, "text": "H2"}

    def test_to_plain(self):
        md = "# Title\n**bold** and *italic* and `code`\n- item1\n- item2"
        r = run(self.tool.execute(action="to_plain", text=md))
        assert r["error"] is None
        assert "#" not in r["result"]
        assert "**" not in r["result"]
        assert r["original_length"] > 0

    def test_badge(self):
        r = run(self.tool.execute(action="badge", label="build", message="passing", color="green"))
        assert r["error"] is None
        assert "![build]" in r["result"]
        assert "shields.io" in r["url"]

    def test_stats(self):
        md = "# Title\n\nSome text with a [link](https://example.com).\n\n```python\ncode\n```"
        r = run(self.tool.execute(action="stats", text=md))
        assert r["error"] is None
        assert r["result"]["headings"] == 1
        assert r["result"]["links"] == 1
        assert r["result"]["words"] > 0

    def test_list_to_md_unordered(self):
        r = run(self.tool.execute(action="list_to_md", items=["a", "b", "c"], ordered=False))
        assert r["count"] == 3
        assert r["result"].startswith("- a")

    def test_list_to_md_ordered(self):
        r = run(self.tool.execute(action="list_to_md", items=["x", "y"], ordered=True))
        assert "1. x" in r["result"]
        assert "2. y" in r["result"]

    def test_list_to_md_empty(self):
        r = run(self.tool.execute(action="list_to_md", items=[]))
        assert r["result"] == ""
        assert r["count"] == 0

    def test_unknown_action(self):
        r = run(self.tool.execute(action="badaction"))
        assert r["error"] is not None


# ---------------------------------------------------------------------------
# NumberTool
# ---------------------------------------------------------------------------

class TestNumberTool:
    def setup_method(self):
        from sovereign.tools.builtin.number_tool import NumberTool
        self.tool = NumberTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "number_tool"

    def test_math_floor(self):
        r = run(self.tool.execute(action="math", value=3.7, operation="floor"))
        assert r["result"] == 3

    def test_math_ceil(self):
        r = run(self.tool.execute(action="math", value=3.2, operation="ceil"))
        assert r["result"] == 4

    def test_math_round(self):
        r = run(self.tool.execute(action="math", value=3.14159, operation="round", decimals=2))
        assert r["result"] == 3.14

    def test_math_sqrt(self):
        r = run(self.tool.execute(action="math", value=16.0, operation="sqrt"))
        assert r["result"] == 4.0

    def test_math_log(self):
        r = run(self.tool.execute(action="math", value=100.0, operation="log10"))
        assert abs(r["result"] - 2.0) < 0.0001

    def test_math_pow(self):
        r = run(self.tool.execute(action="math", value=2.0, operation="pow", operand=10.0))
        assert r["result"] == 1024.0

    def test_math_abs(self):
        r = run(self.tool.execute(action="math", value=-5.0, operation="abs"))
        assert r["result"] == 5.0

    def test_math_sign_positive(self):
        r = run(self.tool.execute(action="math", value=3.0, operation="sign"))
        assert r["result"] == 1

    def test_math_sign_negative(self):
        r = run(self.tool.execute(action="math", value=-3.0, operation="sign"))
        assert r["result"] == -1

    def test_math_sign_zero(self):
        r = run(self.tool.execute(action="math", value=0.0, operation="sign"))
        assert r["result"] == 0

    def test_math_factorial(self):
        r = run(self.tool.execute(action="math", value=5.0, operation="factorial"))
        assert r["result"] == 120

    def test_math_unknown_operation(self):
        r = run(self.tool.execute(action="math", value=1.0, operation="modulo"))
        assert r["error"] is not None

    def test_format_decimal(self):
        r = run(self.tool.execute(action="format", value=1234567.89, decimals=2, locale_format="decimal"))
        assert "1,234,567.89" in r["result"]

    def test_format_currency(self):
        r = run(self.tool.execute(action="format", value=99.5, decimals=2, locale_format="currency"))
        assert "$" in r["result"]

    def test_format_percent(self):
        r = run(self.tool.execute(action="format", value=0.75, decimals=1, locale_format="percent"))
        assert "%" in r["result"]

    def test_format_scientific(self):
        r = run(self.tool.execute(action="format", value=12345.0, decimals=2, locale_format="scientific"))
        assert "e" in r["result"].lower()

    def test_convert_unit_length(self):
        r = run(self.tool.execute(action="convert_unit", value=1.0, from_unit="km", to_unit="m", unit_type="length"))
        assert r["result"] == 1000.0

    def test_convert_unit_weight(self):
        r = run(self.tool.execute(action="convert_unit", value=1.0, from_unit="kg", to_unit="lb", unit_type="weight"))
        assert abs(r["result"] - 2.204624) < 0.001

    def test_convert_unit_temperature_c_to_f(self):
        r = run(self.tool.execute(action="convert_unit", value=100.0, from_unit="c", to_unit="f", unit_type="temperature"))
        assert r["result"] == 212.0

    def test_convert_unit_temperature_f_to_c(self):
        r = run(self.tool.execute(action="convert_unit", value=32.0, from_unit="f", to_unit="c", unit_type="temperature"))
        assert r["result"] == 0.0

    def test_convert_unit_temperature_k(self):
        r = run(self.tool.execute(action="convert_unit", value=0.0, from_unit="c", to_unit="k", unit_type="temperature"))
        assert r["result"] == 273.15

    def test_convert_unit_unknown(self):
        r = run(self.tool.execute(action="convert_unit", value=1.0, from_unit="xyz", to_unit="abc", unit_type="length"))
        assert r["error"] is not None

    def test_convert_unit_unknown_temp(self):
        r = run(self.tool.execute(action="convert_unit", value=1.0, from_unit="x", to_unit="c", unit_type="temperature"))
        assert r["error"] is not None

    def test_convert_unit_unknown_temp_to(self):
        r = run(self.tool.execute(action="convert_unit", value=1.0, from_unit="c", to_unit="x", unit_type="temperature"))
        assert r["error"] is not None

    def test_stats_basic(self):
        r = run(self.tool.execute(action="stats", values=[1, 2, 3, 4, 5]))
        assert r["error"] is None
        assert r["result"]["mean"] == 3.0
        assert r["result"]["min"] == 1
        assert r["result"]["max"] == 5

    def test_stats_empty(self):
        r = run(self.tool.execute(action="stats", values=[]))
        assert r["error"] is not None

    def test_stats_single_value(self):
        r = run(self.tool.execute(action="stats", values=[42]))
        assert r["result"]["count"] == 1
        assert r["result"]["stdev"] == 0.0

    def test_stats_mode(self):
        r = run(self.tool.execute(action="stats", values=[1, 2, 2, 3, 3, 3]))
        assert r["result"]["mode"] == 3

    def test_stats_no_mode(self):
        r = run(self.tool.execute(action="stats", values=[1, 2, 3]))
        assert r["result"]["mode"] is None

    def test_percentage(self):
        r = run(self.tool.execute(action="percentage", part=25.0, total=200.0))
        assert r["result"] == 12.5
        assert "%" in r["formatted"]

    def test_percentage_zero_total(self):
        r = run(self.tool.execute(action="percentage", part=10.0, total=0.0))
        assert r["error"] is not None

    def test_clamp_in_range(self):
        r = run(self.tool.execute(action="clamp", value=50.0, min_val=0.0, max_val=100.0))
        assert r["result"] == 50.0
        assert r["clamped"] is False

    def test_clamp_below_min(self):
        r = run(self.tool.execute(action="clamp", value=-10.0, min_val=0.0, max_val=100.0))
        assert r["result"] == 0.0
        assert r["clamped"] is True

    def test_clamp_above_max(self):
        r = run(self.tool.execute(action="clamp", value=200.0, min_val=0.0, max_val=100.0))
        assert r["result"] == 100.0
        assert r["clamped"] is True

    def test_unknown_action(self):
        r = run(self.tool.execute(action="divide"))
        assert r["error"] is not None


# ---------------------------------------------------------------------------
# TemplateRenderTool
# ---------------------------------------------------------------------------

class TestTemplateRenderTool:
    def setup_method(self):
        from sovereign.tools.builtin.template_render_tool import TemplateRenderTool
        self.tool = TemplateRenderTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "template_render_tool"

    def test_render_basic(self):
        r = run(self.tool.execute(
            action="render",
            template="Hello, {{name}}!",
            variables={"name": "World"},
        ))
        assert r["result"] == "Hello, World!"
        assert r["complete"] is True
        assert r["missing_vars"] == []

    def test_render_multiple_vars(self):
        r = run(self.tool.execute(
            action="render",
            template="{{greeting}}, {{name}}! You are {{age}} years old.",
            variables={"greeting": "Hi", "name": "Alice", "age": "30"},
        ))
        assert r["result"] == "Hi, Alice! You are 30 years old."

    def test_render_missing_var(self):
        r = run(self.tool.execute(
            action="render",
            template="Hello, {{name}}! From {{sender}}.",
            variables={"name": "Alice"},
        ))
        assert r["complete"] is False
        assert "sender" in r["missing_vars"]

    def test_render_no_vars(self):
        r = run(self.tool.execute(action="render", template="Static text"))
        assert r["result"] == "Static text"
        assert r["complete"] is True

    def test_render_list(self):
        r = run(self.tool.execute(
            action="render_list",
            template="- {{name}}: {{value}}",
            items=[{"name": "A", "value": 1}, {"name": "B", "value": 2}],
            separator="\n",
        ))
        assert r["count"] == 2
        assert "- A: 1" in r["result"]
        assert "- B: 2" in r["result"]

    def test_render_list_scalar_items(self):
        r = run(self.tool.execute(
            action="render_list",
            template="Item: {{item}}",
            items=["foo", "bar"],
        ))
        assert "Item: foo" in r["result"]

    def test_render_list_custom_separator(self):
        r = run(self.tool.execute(
            action="render_list",
            template="{{item}}",
            items=["a", "b", "c"],
            separator=", ",
        ))
        assert r["result"] == "a, b, c"

    def test_fill_slots(self):
        r = run(self.tool.execute(
            action="fill_slots",
            template="Hello, {{name}}!",
            variables={"name": "Bob"},
        ))
        assert r["error"] is None
        assert "Bob" in r["result"]

    def test_extract_vars(self):
        r = run(self.tool.execute(
            action="extract_vars",
            template="Dear {{title}} {{last_name}}, your ref is {{ref_number}}.",
        ))
        assert r["error"] is None
        assert r["count"] == 3
        assert "title" in r["result"]
        assert "last_name" in r["result"]
        assert "ref_number" in r["result"]

    def test_extract_vars_none(self):
        r = run(self.tool.execute(action="extract_vars", template="No variables here."))
        assert r["count"] == 0
        assert r["result"] == []

    def test_validate_complete(self):
        r = run(self.tool.execute(
            action="validate",
            template="{{a}} + {{b}}",
            variables={"a": "1", "b": "2"},
        ))
        assert r["result"] is True
        assert r["missing_vars"] == []
        assert r["extra_vars"] == []

    def test_validate_missing(self):
        r = run(self.tool.execute(
            action="validate",
            template="{{a}} + {{b}} + {{c}}",
            variables={"a": "1"},
        ))
        assert r["result"] is False
        assert "b" in r["missing_vars"]
        assert "c" in r["missing_vars"]

    def test_validate_extra_vars(self):
        r = run(self.tool.execute(
            action="validate",
            template="{{a}}",
            variables={"a": "1", "extra": "unused"},
        ))
        assert r["result"] is True
        assert "extra" in r["extra_vars"]

    def test_unknown_action(self):
        r = run(self.tool.execute(action="unknown_action", template="x"))
        assert r["error"] is not None


# ---------------------------------------------------------------------------
# UUIDTool
# ---------------------------------------------------------------------------

class TestUUIDTool:
    def setup_method(self):
        from sovereign.tools.builtin.uuid_tool import UuidTool
        self.tool = UuidTool()

    def test_schema_name(self):
        assert self.tool.schema.name == "uuid_tool"

    def test_generate_v4(self):
        r = run(self.tool.execute(action="generate", version=4))
        assert r["error"] is None
        uid = r["result"]
        assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", uid)

    def test_generate_v1(self):
        r = run(self.tool.execute(action="generate", version=1))
        assert r["error"] is None
        assert "-" in r["result"]

    def test_generate_v5(self):
        r = run(self.tool.execute(action="generate", version=5))
        assert r["error"] is None
        assert "-" in r["result"]

    def test_generate_unique(self):
        r1 = run(self.tool.execute(action="generate"))
        r2 = run(self.tool.execute(action="generate"))
        assert r1["result"] != r2["result"]

    def test_validate_valid(self):
        r = run(self.tool.execute(action="validate", value="550e8400-e29b-41d4-a716-446655440000"))
        assert r["result"] is True

    def test_validate_invalid(self):
        r = run(self.tool.execute(action="validate", value="not-a-uuid"))
        assert r["result"] is False

    def test_inspect(self):
        r = run(self.tool.execute(action="inspect", value="550e8400-e29b-41d4-a716-446655440000"))
        assert r["error"] is None
        assert "version" in r["result"] or "variant" in r["result"] or r["result"] is not None

    def test_to_hex(self):
        uid = "550e8400-e29b-41d4-a716-446655440000"
        r = run(self.tool.execute(action="to_hex", value=uid))
        assert r["error"] is None
        assert isinstance(r["result"], str)
        assert "-" not in r["result"]

    def test_to_int(self):
        uid = "550e8400-e29b-41d4-a716-446655440000"
        r = run(self.tool.execute(action="to_int", value=uid))
        assert r["error"] is None
        assert isinstance(r["result"], int)
        assert r["result"] > 0

    def test_to_urn(self):
        uid = "550e8400-e29b-41d4-a716-446655440000"
        r = run(self.tool.execute(action="to_urn", value=uid))
        assert r["error"] is None
        assert r["result"].startswith("urn:uuid:")

    def test_bulk(self):
        r = run(self.tool.execute(action="bulk", count=5))
        assert r["error"] is None
        assert len(r["result"]) == 5
        assert len(set(r["result"])) == 5

    def test_bulk_default(self):
        r = run(self.tool.execute(action="bulk"))
        assert r["error"] is None
        assert len(r["result"]) > 0

    def test_inspect_invalid(self):
        r = run(self.tool.execute(action="inspect", value="bad-uuid"))
        assert r["error"] is not None or r["result"] is not None

    def test_unknown_action(self):
        r = run(self.tool.execute(action="unknown"))
        assert r["error"] is not None
