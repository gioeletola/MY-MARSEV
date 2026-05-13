"""
ComputerUseTool — local mouse/keyboard control + OCR screen reading.

Does NOT require Claude's computer-use API. Uses only local Python libraries:
  - mss            → fast multi-monitor screenshot capture
  - pyautogui      → mouse click, move, scroll; keyboard type
  - pytesseract    → OCR (requires system `tesseract` binary)
  - cv2            → template matching to locate UI elements on screen
  - xdotool        → Linux window management (find/focus by title)

All dependencies are optional: if a library is missing the relevant action
returns {"error": "...", "hint": "pip install sovereign[computer-use]"}.

Security notes:
  - Requires EXECUTE action class approval (set requires_review=True for agents)
  - FAILSAFE enabled: move mouse to top-left corner (0, 0) to abort pyautogui
  - All actions are logged at INFO level for audit trail
  - type_text deliberately inserts 50ms inter-key delay to be interruptible
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import shutil
import subprocess
from typing import Any

from sovereign.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency detection (all checked once at import time)
# Pre-defined as None so monkeypatching in tests always works.
# ---------------------------------------------------------------------------

_mss: Any = None
_mss_tools: Any = None
_pag: Any = None
_PILImage: Any = None
_tess: Any = None
_cv2: Any = None
_np: Any = None

try:
    import mss as _mss          # type: ignore[no-redef]
    import mss.tools as _mss_tools  # type: ignore[no-redef]
    _HAS_MSS = True
except ImportError:
    _HAS_MSS = False

try:
    import pyautogui as _pag    # type: ignore[no-redef]
    _pag.FAILSAFE = True        # top-left corner aborts
    _pag.PAUSE    = 0.05        # 50ms inter-action pause
    _HAS_PAG = True
except ImportError:
    _HAS_PAG = False

try:
    from PIL import Image as _PILImage  # type: ignore[no-redef]
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

try:
    import pytesseract as _tess  # type: ignore[no-redef]
    _HAS_TESS = True
except ImportError:
    _HAS_TESS = False

try:
    import cv2 as _cv2           # type: ignore[no-redef]
    import numpy as _np          # type: ignore[no-redef]
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False

_HAS_XDOTOOL = bool(shutil.which("xdotool"))

_INSTALL_HINT = (
    "pip install sovereign[computer-use]  "
    "# mss pyautogui pytesseract opencv-python-headless"
)


def _missing(lib: str) -> dict:
    return {"error": f"{lib} not available", "hint": _INSTALL_HINT}


# ---------------------------------------------------------------------------
# Helper: capture screen region → PNG bytes
# ---------------------------------------------------------------------------

def _capture_region(region: dict | None = None, monitor_idx: int = 1) -> bytes:
    """Return raw PNG bytes for the given screen region (or full monitor)."""
    with _mss.mss() as sct:
        if region:
            mon = {
                "top":    int(region.get("top", 0)),
                "left":   int(region.get("left", 0)),
                "width":  int(region.get("width", 800)),
                "height": int(region.get("height", 600)),
            }
        else:
            monitors = sct.monitors
            idx = min(monitor_idx, len(monitors) - 1)
            mon = monitors[idx]
        img = sct.grab(mon)
        buf = io.BytesIO()
        _mss_tools.to_png(img.rgb, img.size, output=buf)
        return buf.getvalue()


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

class ComputerUseTool(BaseTool):
    """
    Control mouse, keyboard, and read the screen via OCR.

    Available actions:
      screenshot       — capture screen or region → base64 PNG
      click            — left/right/middle click at (x, y)
      double_click     — double-click at (x, y)
      right_click      — right-click at (x, y)
      move_mouse       — move pointer to (x, y)
      get_mouse_pos    — return current pointer coordinates
      type_text        — type a string (keyboard simulation)
      hotkey           — press a key combination, e.g. ["ctrl", "c"]
      scroll           — scroll up/down/left/right at (x, y)
      read_screen      — OCR the screen (or a region) → plain text
      locate_on_screen — find a template image → (x, y) coordinates
      find_window      — list open windows matching a title substring
      focus_window     — bring a window to foreground by title substring
    """

    name = "computer_use"
    description = (
        "Control the local computer: take screenshots, move/click the mouse, "
        "type text, scroll, read screen text via OCR, locate UI elements by "
        "image matching, and manage windows."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "screenshot", "click", "double_click", "right_click",
                    "move_mouse", "get_mouse_pos", "type_text", "hotkey",
                    "scroll", "read_screen", "locate_on_screen",
                    "find_window", "focus_window",
                ],
                "description": "The operation to perform.",
            },
            "x": {"type": "integer", "description": "Screen X coordinate (pixels)."},
            "y": {"type": "integer", "description": "Screen Y coordinate (pixels)."},
            "text": {"type": "string", "description": "Text to type or window title to search."},
            "keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key names for hotkey, e.g. ['ctrl', 's'].",
            },
            "button": {
                "type": "string",
                "enum": ["left", "right", "middle"],
                "default": "left",
                "description": "Mouse button for click actions.",
            },
            "direction": {
                "type": "string",
                "enum": ["up", "down", "left", "right"],
                "default": "down",
                "description": "Scroll direction.",
            },
            "amount": {
                "type": "integer",
                "default": 3,
                "description": "Scroll amount in clicks.",
            },
            "duration": {
                "type": "number",
                "default": 0.2,
                "description": "Mouse movement duration in seconds.",
            },
            "region": {
                "type": "object",
                "properties": {
                    "top":    {"type": "integer"},
                    "left":   {"type": "integer"},
                    "width":  {"type": "integer"},
                    "height": {"type": "integer"},
                },
                "description": "Optional screen region {top, left, width, height}.",
            },
            "monitor": {
                "type": "integer",
                "default": 1,
                "description": "Monitor index (1 = primary).",
            },
            "language": {
                "type": "string",
                "default": "eng",
                "description": "Tesseract language code for OCR.",
            },
            "template_path": {
                "type": "string",
                "description": "Path to a PNG/JPG image to locate on screen.",
            },
            "confidence": {
                "type": "number",
                "default": 0.8,
                "description": "Minimum match confidence for locate_on_screen (0–1).",
            },
            "interval": {
                "type": "number",
                "default": 0.05,
                "description": "Delay (seconds) between keystrokes for type_text.",
            },
        },
        "required": ["action"],
    }

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def execute(self, **kwargs: Any) -> dict:  # type: ignore[override]
        action = kwargs.get("action", "")
        try:
            if action == "screenshot":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._screenshot,
                    kwargs.get("region"), kwargs.get("monitor", 1)
                )
            if action in ("click", "double_click", "right_click"):
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._click, action,
                    kwargs.get("x", 0), kwargs.get("y", 0),
                    kwargs.get("button", "left"), kwargs.get("duration", 0.2)
                )
            if action == "move_mouse":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._move_mouse,
                    kwargs.get("x", 0), kwargs.get("y", 0),
                    kwargs.get("duration", 0.2)
                )
            if action == "get_mouse_pos":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._get_mouse_pos
                )
            if action == "type_text":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._type_text,
                    kwargs.get("text", ""), kwargs.get("interval", 0.05)
                )
            if action == "hotkey":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._hotkey, kwargs.get("keys", [])
                )
            if action == "scroll":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._scroll,
                    kwargs.get("x", 0), kwargs.get("y", 0),
                    kwargs.get("direction", "down"), kwargs.get("amount", 3)
                )
            if action == "read_screen":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._read_screen,
                    kwargs.get("region"), kwargs.get("language", "eng"),
                    kwargs.get("monitor", 1)
                )
            if action == "locate_on_screen":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._locate_on_screen,
                    kwargs.get("template_path", ""),
                    kwargs.get("confidence", 0.8),
                    kwargs.get("monitor", 1)
                )
            if action == "find_window":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._find_window, kwargs.get("text", "")
                )
            if action == "focus_window":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._focus_window, kwargs.get("text", "")
                )
            return {"error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.error("ComputerUseTool[%s] error: %s", action, exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Implementations
    # ------------------------------------------------------------------

    def _screenshot(self, region: dict | None, monitor: int) -> dict:
        if not _HAS_MSS:
            return _missing("mss")
        png = _capture_region(region, monitor)
        b64 = base64.b64encode(png).decode()
        size = len(png)
        logger.info("screenshot captured — %d bytes", size)
        return {"image_base64": b64, "format": "png", "size_bytes": size}

    def _click(
        self, action: str, x: int, y: int, button: str, duration: float
    ) -> dict:
        if not _HAS_PAG:
            return _missing("pyautogui")
        _pag.moveTo(x, y, duration=duration)
        if action == "double_click":
            _pag.doubleClick(x, y, button=button)
        elif action == "right_click":
            _pag.rightClick(x, y)
        else:
            _pag.click(x, y, button=button)
        logger.info("%s at (%d, %d)", action, x, y)
        return {"clicked": True, "action": action, "x": x, "y": y}

    def _move_mouse(self, x: int, y: int, duration: float) -> dict:
        if not _HAS_PAG:
            return _missing("pyautogui")
        _pag.moveTo(x, y, duration=duration)
        logger.info("move_mouse → (%d, %d)", x, y)
        return {"moved": True, "x": x, "y": y}

    def _get_mouse_pos(self) -> dict:
        if not _HAS_PAG:
            return _missing("pyautogui")
        pos = _pag.position()
        return {"x": pos.x, "y": pos.y}

    def _type_text(self, text: str, interval: float) -> dict:
        if not _HAS_PAG:
            return _missing("pyautogui")
        _pag.typewrite(text, interval=interval)
        logger.info("type_text: %d chars", len(text))
        return {"typed": len(text)}

    def _hotkey(self, keys: list[str]) -> dict:
        if not _HAS_PAG:
            return _missing("pyautogui")
        if not keys:
            return {"error": "keys list is empty"}
        _pag.hotkey(*keys)
        logger.info("hotkey: %s", "+".join(keys))
        return {"pressed": keys}

    def _scroll(self, x: int, y: int, direction: str, amount: int) -> dict:
        if not _HAS_PAG:
            return _missing("pyautogui")
        _pag.moveTo(x, y)
        clicks = amount if direction in ("up", "right") else -amount
        if direction in ("left", "right"):
            _pag.hscroll(clicks)
        else:
            _pag.scroll(clicks)
        logger.info("scroll %s ×%d at (%d, %d)", direction, amount, x, y)
        return {"scrolled": True, "direction": direction, "amount": amount}

    def _read_screen(
        self, region: dict | None, language: str, monitor: int
    ) -> dict:
        if not _HAS_MSS:
            return _missing("mss")
        if not _HAS_TESS:
            return _missing("pytesseract")
        if not _HAS_PIL:
            return _missing("Pillow")
        png = _capture_region(region, monitor)
        img = _PILImage.open(io.BytesIO(png))
        # Upscale small captures to improve OCR accuracy
        if img.width < 1000:
            img = img.resize((img.width * 2, img.height * 2), _PILImage.LANCZOS)
        data = _tess.image_to_data(img, lang=language, output_type=_tess.Output.DICT)
        words = [
            w for w, c in zip(data["text"], data["conf"])
            if w.strip() and int(c) > 0
        ]
        avg_conf = (
            sum(int(c) for c in data["conf"] if int(c) > 0) /
            max(1, sum(1 for c in data["conf"] if int(c) > 0))
        )
        text = " ".join(words)
        logger.info("read_screen: %d words, conf=%.1f%%", len(words), avg_conf)
        return {"text": text, "word_count": len(words), "avg_confidence": round(avg_conf, 1)}

    def _locate_on_screen(
        self, template_path: str, confidence: float, monitor: int
    ) -> dict:
        if not _HAS_MSS:
            return _missing("mss")
        if not _HAS_CV2:
            return _missing("opencv-python-headless")
        from pathlib import Path
        tmpl_file = Path(template_path)
        if not tmpl_file.exists():
            return {"error": f"Template not found: {template_path}"}
        png = _capture_region(None, monitor)
        screen = _cv2.imdecode(_np.frombuffer(png, _np.uint8), _cv2.IMREAD_COLOR)
        tmpl  = _cv2.imread(str(tmpl_file), _cv2.IMREAD_COLOR)
        if tmpl is None:
            return {"error": f"Could not load template: {template_path}"}
        res = _cv2.matchTemplate(screen, tmpl, _cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = _cv2.minMaxLoc(res)
        found = float(max_val) >= confidence
        cx = int(max_loc[0] + tmpl.shape[1] / 2)
        cy = int(max_loc[1] + tmpl.shape[0] / 2)
        logger.info(
            "locate_on_screen: %s → found=%s conf=%.3f at (%d,%d)",
            template_path, found, max_val, cx, cy,
        )
        return {
            "found": found,
            "x": cx if found else None,
            "y": cy if found else None,
            "match_confidence": round(float(max_val), 4),
        }

    def _find_window(self, title: str) -> dict:
        if not _HAS_XDOTOOL:
            return {"error": "xdotool not available", "hint": "sudo apt install xdotool"}
        result = subprocess.run(
            ["xdotool", "search", "--name", title],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {"windows": [], "query": title}
        wids = result.stdout.strip().splitlines()
        windows = []
        for wid in wids[:20]:
            name_res = subprocess.run(
                ["xdotool", "getwindowname", wid],
                capture_output=True, text=True, timeout=3,
            )
            windows.append({"id": wid, "title": name_res.stdout.strip()})
        return {"windows": windows, "query": title}

    def _focus_window(self, title: str) -> dict:
        if not _HAS_XDOTOOL:
            return {"error": "xdotool not available", "hint": "sudo apt install xdotool"}
        result = subprocess.run(
            ["xdotool", "search", "--name", title, "windowactivate", "--sync"],
            capture_output=True, text=True, timeout=5,
        )
        focused = result.returncode == 0
        logger.info("focus_window '%s' → %s", title, focused)
        return {"focused": focused, "title": title}
