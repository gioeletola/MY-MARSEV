"""Tests for ComputerUseTool — all external deps are mocked."""
from __future__ import annotations

import base64
import struct
import sys
import zlib
from types import ModuleType
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Minimal valid PNG using only stdlib (no Pillow required)
# ---------------------------------------------------------------------------

def _make_png(width: int = 100, height: int = 100) -> bytes:
    """Build a minimal valid RGB PNG with stdlib only."""
    def _chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    sig  = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    raw  = (b"\x00" + b"\x00\x00\x00" * width) * height
    idat = _chunk(b"IDAT", zlib.compress(raw))
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


_FAKE_PNG = _make_png()


# ---------------------------------------------------------------------------
# Helpers to inject fake optional modules before importing the tool
# ---------------------------------------------------------------------------

def _fake_mss_module() -> tuple[ModuleType, ModuleType]:
    """Return a minimal fake mss module."""
    mod = ModuleType("mss")
    tools_mod = ModuleType("mss.tools")

    class _FakeSct:
        monitors = [
            {},                                      # [0] = all
            {"top": 0, "left": 0, "width": 1920, "height": 1080},
        ]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def grab(self, _mon):
            img = MagicMock()
            img.rgb = b"\x00" * (100 * 100 * 3)
            img.size = (100, 100)
            return img

    def _to_png(rgb, size, output):
        output.write(_FAKE_PNG)

    mod.mss = _FakeSct
    tools_mod.to_png = _to_png
    return mod, tools_mod


def _fake_pil_module() -> ModuleType:
    """Return a minimal fake PIL.Image module."""
    pil = ModuleType("PIL")
    pil_image = ModuleType("PIL.Image")

    class _FakeImage:
        width = 100
        height = 100
        LANCZOS = 1

        def resize(self, size, resample=None):
            return self

    def _open(buf):
        return _FakeImage()

    pil_image.open = _open
    pil_image.LANCZOS = 1
    pil.Image = pil_image
    return pil, pil_image


def _inject_mss(monkeypatch):
    mss_mod, tools_mod = _fake_mss_module()
    monkeypatch.setitem(sys.modules, "mss", mss_mod)
    monkeypatch.setitem(sys.modules, "mss.tools", tools_mod)


def _inject_pil(monkeypatch):
    pil, pil_image = _fake_pil_module()
    monkeypatch.setitem(sys.modules, "PIL", pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", pil_image)
    return pil_image


def _inject_pag(monkeypatch):
    pag = ModuleType("pyautogui")
    pag.FAILSAFE = True
    pag.PAUSE = 0.0
    pag.moveTo    = MagicMock()
    pag.click     = MagicMock()
    pag.doubleClick = MagicMock()
    pag.rightClick  = MagicMock()
    pag.typewrite   = MagicMock()
    pag.hotkey      = MagicMock()
    pag.scroll      = MagicMock()
    pag.hscroll     = MagicMock()

    class _Point:
        x, y = 500, 400

    pag.position = MagicMock(return_value=_Point())
    monkeypatch.setitem(sys.modules, "pyautogui", pag)
    return pag


def _inject_tess(monkeypatch):
    tess = ModuleType("pytesseract")
    tess.Output = MagicMock()
    tess.Output.DICT = "dict"
    tess.image_to_data = MagicMock(return_value={
        "text": ["Hello", "World", ""],
        "conf": [90, 85, -1],
    })
    monkeypatch.setitem(sys.modules, "pytesseract", tess)
    return tess


def _inject_cv2(monkeypatch):
    import numpy as np
    cv2 = ModuleType("cv2")
    cv2.IMREAD_COLOR = 1
    cv2.TM_CCOEFF_NORMED = 5
    cv2.imdecode = MagicMock(return_value=np.zeros((100, 100, 3), dtype="uint8"))
    cv2.imread   = MagicMock(return_value=np.zeros((20, 20, 3), dtype="uint8"))
    result = np.zeros((81, 81), dtype="float32")
    result[40, 40] = 0.95  # high-confidence match
    cv2.matchTemplate = MagicMock(return_value=result)
    cv2.minMaxLoc     = MagicMock(return_value=(0.0, 0.95, (0, 0), (40, 40)))
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    return cv2


# ---------------------------------------------------------------------------
# Fixture: fresh import of ComputerUseTool with all deps mocked
# ---------------------------------------------------------------------------

@pytest.fixture()
def tool_all_deps(monkeypatch):
    """ComputerUseTool with mss, pyautogui, pytesseract, cv2, PIL all available."""
    _inject_mss(monkeypatch)
    pag = _inject_pag(monkeypatch)
    _inject_tess(monkeypatch)
    _inject_cv2(monkeypatch)
    _inject_pil(monkeypatch)

    # Patch _HAS_* flags on the already-imported module
    from sovereign.tools.builtin import computer_use as _cu_mod
    monkeypatch.setattr(_cu_mod, "_HAS_MSS",  True)
    monkeypatch.setattr(_cu_mod, "_HAS_PAG",  True)
    monkeypatch.setattr(_cu_mod, "_HAS_TESS", True)
    monkeypatch.setattr(_cu_mod, "_HAS_CV2",  True)
    monkeypatch.setattr(_cu_mod, "_HAS_PIL",  True)
    # Patch the module-level references used by the tool methods
    monkeypatch.setattr(_cu_mod, "_pag",  pag)
    monkeypatch.setattr(_cu_mod, "_tess", sys.modules["pytesseract"])
    monkeypatch.setattr(_cu_mod, "_cv2",  sys.modules["cv2"])
    import numpy as _np
    monkeypatch.setattr(_cu_mod, "_np",   _np)
    monkeypatch.setattr(_cu_mod, "_mss",  sys.modules["mss"])
    monkeypatch.setattr(_cu_mod, "_mss_tools", sys.modules["mss.tools"])
    pil_image_mod = sys.modules["PIL.Image"]
    monkeypatch.setattr(_cu_mod, "_PILImage", pil_image_mod)

    t = _cu_mod.ComputerUseTool()
    t._pag_mock = pag
    return t


@pytest.fixture()
def tool_no_deps(monkeypatch):
    """ComputerUseTool with NO optional deps available."""
    for mod_name in ("mss", "mss.tools", "pyautogui", "pytesseract", "cv2"):
        monkeypatch.setitem(sys.modules, mod_name, None)  # type: ignore[assignment]

    for mod_name in list(sys.modules):
        if "computer_use" in mod_name:
            del sys.modules[mod_name]

    # Re-import with NoneType stubs triggers ImportError path
    # Reset cached _HAS_* by patching the module directly after import
    from sovereign.tools.builtin import computer_use as _cu_mod
    monkeypatch.setattr(_cu_mod, "_HAS_MSS",     False)
    monkeypatch.setattr(_cu_mod, "_HAS_PAG",     False)
    monkeypatch.setattr(_cu_mod, "_HAS_TESS",    False)
    monkeypatch.setattr(_cu_mod, "_HAS_CV2",     False)
    monkeypatch.setattr(_cu_mod, "_HAS_XDOTOOL", False)
    return _cu_mod.ComputerUseTool()


# ---------------------------------------------------------------------------
# Schema tests (no deps needed)
# ---------------------------------------------------------------------------

def test_schema_name():
    from sovereign.tools.builtin.computer_use import ComputerUseTool
    assert ComputerUseTool().schema.name == "computer_use"


def test_schema_has_required_action():
    from sovereign.tools.builtin.computer_use import ComputerUseTool
    schema = ComputerUseTool().schema
    assert "action" in schema.input_schema["properties"]
    assert schema.input_schema["required"] == ["action"]


def test_schema_all_actions_listed():
    from sovereign.tools.builtin.computer_use import ComputerUseTool
    actions = ComputerUseTool().schema.input_schema["properties"]["action"]["enum"]
    for a in ("screenshot", "click", "type_text", "read_screen",
              "locate_on_screen", "find_window", "focus_window"):
        assert a in actions


# ---------------------------------------------------------------------------
# Missing-deps graceful errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_screenshot_missing_mss(tool_no_deps):
    result = await tool_no_deps.execute(action="screenshot")
    assert "error" in result
    assert "mss" in result["error"]


@pytest.mark.asyncio
async def test_click_missing_pyautogui(tool_no_deps):
    result = await tool_no_deps.execute(action="click", x=100, y=200)
    assert "error" in result
    assert "pyautogui" in result["error"]


@pytest.mark.asyncio
async def test_type_text_missing_pyautogui(tool_no_deps):
    result = await tool_no_deps.execute(action="type_text", text="hello")
    assert "error" in result


@pytest.mark.asyncio
async def test_read_screen_missing_mss(tool_no_deps):
    result = await tool_no_deps.execute(action="read_screen")
    assert "error" in result
    assert "mss" in result["error"]


@pytest.mark.asyncio
async def test_locate_on_screen_missing_mss(tool_no_deps):
    result = await tool_no_deps.execute(action="locate_on_screen", template_path="x.png")
    assert "error" in result


@pytest.mark.asyncio
async def test_find_window_no_xdotool(tool_no_deps):
    result = await tool_no_deps.execute(action="find_window", text="Terminal")
    assert "error" in result
    assert "xdotool" in result["error"]


@pytest.mark.asyncio
async def test_unknown_action_returns_error(tool_no_deps):
    result = await tool_no_deps.execute(action="fly_to_moon")  # type: ignore[arg-type]
    assert "error" in result


# ---------------------------------------------------------------------------
# Happy-path with mocked deps
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_screenshot_returns_base64_png(tool_all_deps):
    result = await tool_all_deps.execute(action="screenshot")
    assert "image_base64" in result
    assert result["format"] == "png"
    # Must be valid base64
    raw = base64.b64decode(result["image_base64"])
    assert raw[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_screenshot_with_region(tool_all_deps):
    result = await tool_all_deps.execute(
        action="screenshot",
        region={"top": 0, "left": 0, "width": 400, "height": 300},
    )
    assert "image_base64" in result
    assert "error" not in result


@pytest.mark.asyncio
async def test_click_left(tool_all_deps):
    result = await tool_all_deps.execute(action="click", x=300, y=200)
    assert result["clicked"] is True
    assert result["x"] == 300
    assert result["y"] == 200


@pytest.mark.asyncio
async def test_click_right(tool_all_deps):
    result = await tool_all_deps.execute(action="right_click", x=100, y=100)
    assert result["clicked"] is True


@pytest.mark.asyncio
async def test_double_click(tool_all_deps):
    result = await tool_all_deps.execute(action="double_click", x=50, y=50)
    assert result["clicked"] is True
    assert result["action"] == "double_click"


@pytest.mark.asyncio
async def test_move_mouse(tool_all_deps):
    result = await tool_all_deps.execute(action="move_mouse", x=800, y=600)
    assert result["moved"] is True
    assert result["x"] == 800


@pytest.mark.asyncio
async def test_get_mouse_pos(tool_all_deps):
    result = await tool_all_deps.execute(action="get_mouse_pos")
    assert "x" in result
    assert "y" in result


@pytest.mark.asyncio
async def test_type_text(tool_all_deps):
    result = await tool_all_deps.execute(action="type_text", text="Hello World")
    assert result["typed"] == 11


@pytest.mark.asyncio
async def test_hotkey(tool_all_deps):
    result = await tool_all_deps.execute(action="hotkey", keys=["ctrl", "c"])
    assert result["pressed"] == ["ctrl", "c"]


@pytest.mark.asyncio
async def test_hotkey_empty_keys(tool_all_deps):
    result = await tool_all_deps.execute(action="hotkey", keys=[])
    assert "error" in result


@pytest.mark.asyncio
async def test_scroll_down(tool_all_deps):
    result = await tool_all_deps.execute(
        action="scroll", x=500, y=400, direction="down", amount=5
    )
    assert result["scrolled"] is True
    assert result["direction"] == "down"
    assert result["amount"] == 5


@pytest.mark.asyncio
async def test_scroll_up(tool_all_deps):
    result = await tool_all_deps.execute(
        action="scroll", x=500, y=400, direction="up", amount=3
    )
    assert result["scrolled"] is True


@pytest.mark.asyncio
async def test_read_screen_returns_text(tool_all_deps):
    result = await tool_all_deps.execute(action="read_screen")
    assert "text" in result
    assert "Hello" in result["text"]
    assert "word_count" in result
    assert "avg_confidence" in result


@pytest.mark.asyncio
async def test_locate_on_screen_found(tool_all_deps, tmp_path):
    # Write a minimal valid PNG as template (no PIL required)
    tmpl = tmp_path / "template.png"
    tmpl.write_bytes(_make_png(20, 20))
    result = await tool_all_deps.execute(
        action="locate_on_screen",
        template_path=str(tmpl),
        confidence=0.8,
    )
    assert result["found"] is True
    assert result["x"] is not None
    assert result["match_confidence"] >= 0.8


@pytest.mark.asyncio
async def test_locate_on_screen_template_missing(tool_all_deps):
    result = await tool_all_deps.execute(
        action="locate_on_screen",
        template_path="/nonexistent/template.png",
    )
    assert "error" in result
    assert "Template not found" in result["error"]
