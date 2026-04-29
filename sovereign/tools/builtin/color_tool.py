"""Color Tool — convert, generate palettes, and analyse colors."""
from __future__ import annotations

import colorsys
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

_NAMED_COLORS: dict[str, str] = {
    "red": "#FF0000", "green": "#008000", "blue": "#0000FF", "white": "#FFFFFF",
    "black": "#000000", "yellow": "#FFFF00", "cyan": "#00FFFF", "magenta": "#FF00FF",
    "orange": "#FFA500", "purple": "#800080", "pink": "#FFC0CB", "brown": "#A52A2A",
    "gray": "#808080", "grey": "#808080", "silver": "#C0C0C0", "gold": "#FFD700",
    "navy": "#000080", "teal": "#008080", "lime": "#00FF00", "coral": "#FF7F50",
    "salmon": "#FA8072", "indigo": "#4B0082", "violet": "#EE82EE", "turquoise": "#40E0D0",
}


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    return r, g, b


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


class ColorTool(BaseTool):
    """Convert, mix, analyse, and generate color palettes."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="color_tool",
            description="Convert hex↔RGB↔HSL, generate complementary/analogous/triadic palettes, lighten/darken, check contrast, analyse colors.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["hex_to_rgb", "rgb_to_hex", "hex_to_hsl", "hsl_to_hex",
                                 "complement", "palette", "lighten", "darken",
                                 "contrast_ratio", "mix", "named_to_hex"],
                        "description": "Action to perform",
                    },
                    "color": {"type": "string", "description": "Hex color (#RRGGBB or name)"},
                    "color2": {"type": "string", "description": "Second color for mix/contrast"},
                    "r": {"type": "integer", "description": "Red 0–255"},
                    "g": {"type": "integer", "description": "Green 0–255"},
                    "b": {"type": "integer", "description": "Blue 0–255"},
                    "h": {"type": "number", "description": "Hue 0–360"},
                    "s": {"type": "number", "description": "Saturation 0–100"},
                    "lightness": {"type": "number", "description": "Lightness 0–100"},
                    "amount": {"type": "number", "description": "Lighten/darken amount 0–100"},
                    "palette_type": {"type": "string", "description": "complementary|analogous|triadic|tetradic|monochromatic"},
                    "weight": {"type": "number", "description": "Mix weight 0–1 (default 0.5)"},
                },
                "required": ["action"],
            },
        )

    async def execute(
        self, action: str, color: str = "#000000", color2: str = "#FFFFFF",
        r: int = 0, g: int = 0, b: int = 0,
        h: float = 0.0, s: float = 0.0, lightness: float = 50.0,
        amount: float = 20.0, palette_type: str = "complementary", weight: float = 0.5,
        **_: Any,
    ) -> Any:
        try:
            color = _NAMED_COLORS.get(color.lower(), color)
            color2 = _NAMED_COLORS.get(color2.lower(), color2)

            if action == "hex_to_rgb":
                rv, gv, bv = _hex_to_rgb(color)
                return {"result": {"r": rv, "g": gv, "b": bv}, "css": f"rgb({rv},{gv},{bv})", "error": None}
            if action == "rgb_to_hex":
                return {"result": _rgb_to_hex(r, g, b), "error": None}
            if action == "hex_to_hsl":
                return self._hex_to_hsl(color)
            if action == "hsl_to_hex":
                return self._hsl_to_hex(h, s, lightness)
            if action == "complement":
                return self._complement(color)
            if action == "palette":
                return self._palette(color, palette_type)
            if action == "lighten":
                return self._adjust_lightness(color, amount)
            if action == "darken":
                return self._adjust_lightness(color, -amount)
            if action == "contrast_ratio":
                return self._contrast(color, color2)
            if action == "mix":
                return self._mix(color, color2, weight)
            if action == "named_to_hex":
                result = _NAMED_COLORS.get(color.lower())
                return {"result": result, "error": None if result else f"Unknown color: {color}"}
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _hex_to_hsl(self, hex_color: str) -> dict:
        rv, gv, bv = _hex_to_rgb(hex_color)
        h_val, l_val, s_val = colorsys.rgb_to_hls(rv / 255, gv / 255, bv / 255)
        return {
            "result": {"h": round(h_val * 360, 1), "s": round(s_val * 100, 1), "l": round(l_val * 100, 1)},
            "css": f"hsl({h_val*360:.1f},{s_val*100:.1f}%,{l_val*100:.1f}%)",
            "error": None,
        }

    def _hsl_to_hex(self, hv: float, sv: float, lv: float) -> dict:
        r_f, g_f, b_f = colorsys.hls_to_rgb(hv / 360, lv / 100, sv / 100)
        hex_col = _rgb_to_hex(round(r_f * 255), round(g_f * 255), round(b_f * 255))
        return {"result": hex_col, "error": None}

    def _complement(self, hex_color: str) -> dict:
        rv, gv, bv = _hex_to_rgb(hex_color)
        h_val, l_val, s_val = colorsys.rgb_to_hls(rv / 255, gv / 255, bv / 255)
        comp_h = (h_val + 0.5) % 1.0
        r_f, g_f, b_f = colorsys.hls_to_rgb(comp_h, l_val, s_val)
        comp = _rgb_to_hex(round(r_f * 255), round(g_f * 255), round(b_f * 255))
        return {"result": comp, "original": hex_color, "error": None}

    def _palette(self, hex_color: str, ptype: str) -> dict:
        rv, gv, bv = _hex_to_rgb(hex_color)
        h_val, l_val, s_val = colorsys.rgb_to_hls(rv / 255, gv / 255, bv / 255)

        def h_shift(shift: float) -> str:
            new_h = (h_val + shift) % 1.0
            rf, gf, bf = colorsys.hls_to_rgb(new_h, l_val, s_val)
            return _rgb_to_hex(round(rf * 255), round(gf * 255), round(bf * 255))

        if ptype == "analogous":
            colors = [hex_color, h_shift(1/12), h_shift(-1/12), h_shift(1/6), h_shift(-1/6)]
        elif ptype == "triadic":
            colors = [hex_color, h_shift(1/3), h_shift(2/3)]
        elif ptype == "tetradic":
            colors = [hex_color, h_shift(1/4), h_shift(1/2), h_shift(3/4)]
        elif ptype == "monochromatic":
            def l_shift(dl: float) -> str:
                new_l = max(0, min(1, l_val + dl))
                rf, gf, bf = colorsys.hls_to_rgb(h_val, new_l, s_val)
                return _rgb_to_hex(round(rf * 255), round(gf * 255), round(bf * 255))
            colors = [l_shift(d) for d in (-0.3, -0.15, 0, 0.15, 0.3)]
        else:
            colors = [hex_color, h_shift(0.5)]

        return {"result": colors, "type": ptype, "base": hex_color, "error": None}

    def _adjust_lightness(self, hex_color: str, delta: float) -> dict:
        rv, gv, bv = _hex_to_rgb(hex_color)
        h_val, l_val, s_val = colorsys.rgb_to_hls(rv / 255, gv / 255, bv / 255)
        new_l = max(0, min(1, l_val + delta / 100))
        r_f, g_f, b_f = colorsys.hls_to_rgb(h_val, new_l, s_val)
        result = _rgb_to_hex(round(r_f * 255), round(g_f * 255), round(b_f * 255))
        return {"result": result, "original": hex_color, "delta": delta, "error": None}

    def _luminance(self, rv: int, gv: int, bv: int) -> float:
        def srgb(c: float) -> float:
            c /= 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * srgb(rv) + 0.7152 * srgb(gv) + 0.0722 * srgb(bv)

    def _contrast(self, c1: str, c2: str) -> dict:
        l1 = self._luminance(*_hex_to_rgb(c1))
        l2 = self._luminance(*_hex_to_rgb(c2))
        ratio = (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)
        wcag_aa = ratio >= 4.5
        wcag_aaa = ratio >= 7.0
        return {
            "result": round(ratio, 2),
            "wcag_aa": wcag_aa,
            "wcag_aaa": wcag_aaa,
            "rating": "AAA" if wcag_aaa else ("AA" if wcag_aa else "Fail"),
            "error": None,
        }

    def _mix(self, c1: str, c2: str, w: float) -> dict:
        r1, g1, b1 = _hex_to_rgb(c1)
        r2, g2, b2 = _hex_to_rgb(c2)
        w = max(0.0, min(1.0, w))
        rm = round(r1 * (1 - w) + r2 * w)
        gm = round(g1 * (1 - w) + g2 * w)
        bm = round(b1 * (1 - w) + b2 * w)
        return {"result": _rgb_to_hex(rm, gm, bm), "c1": c1, "c2": c2, "weight": w, "error": None}
