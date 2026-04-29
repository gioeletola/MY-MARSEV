"""Overlay UI — generates floating HTML/Canvas glass panels for the SOVEREIGN HUD."""
from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PanelConfig:
    panel_id: str
    title: str
    position: str = "top-right"    # top-left / top-right / bottom-left / bottom-right / center
    width_px: int = 320
    opacity: float = 0.88
    theme: str = "dark"            # dark / glass / minimal
    auto_hide_s: float = 0.0       # 0 = never
    z_index: int = 9000
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class OverlayMessage:
    """A transient message to display in the HUD overlay."""
    text: str
    color: str = "#06b6d4"              # CSS colour string
    duration_ms: int = 3000             # 0 = persistent until dismissed
    position: str = "bottom-center"     # positional hint for CSS
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: float = field(default_factory=time.time)
    dismissed: bool = False

    @property
    def expired(self) -> bool:
        if self.duration_ms <= 0:
            return False
        return (time.time() - self.created_at) * 1000 > self.duration_ms


_POSITION_CSS = {
    "top-left":       "top:16px; left:16px;",
    "top-right":      "top:16px; right:16px;",
    "bottom-left":    "bottom:16px; left:16px;",
    "bottom-right":   "bottom:16px; right:16px;",
    "center":         "top:50%; left:50%; transform:translate(-50%,-50%);",
    "bottom-center":  "bottom:24px; left:50%; transform:translateX(-50%);",
}

_THEME_CSS = {
    "dark":    "background:rgba(10,10,15,0.92); border:1px solid #1e1e2e; color:#e2e8f0;",
    "glass":   "background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); "
               "backdrop-filter:blur(12px); color:#e2e8f0;",
    "minimal": "background:transparent; border:1px solid rgba(6,182,212,0.3); color:#06b6d4;",
}

_MAX_MESSAGE_QUEUE = 32


class OverlayUI:
    """
    Builds standalone HTML overlay panels and a full HUD page.
    Includes a queue-based message system for transient notifications.
    """

    def __init__(self) -> None:
        self._panels: dict[str, PanelConfig] = {}
        self._message_queue: deque[OverlayMessage] = deque(maxlen=_MAX_MESSAGE_QUEUE)

    # ── Panel management ──────────────────────────────────────────────────

    def register_panel(self, config: PanelConfig) -> None:
        self._panels[config.panel_id] = config

    def unregister_panel(self, panel_id: str) -> bool:
        return bool(self._panels.pop(panel_id, None))

    def update_panel_data(self, panel_id: str, data: dict[str, Any]) -> bool:
        panel = self._panels.get(panel_id)
        if not panel:
            return False
        panel.data.update(data)
        return True

    # ── Message queue ─────────────────────────────────────────────────────

    def push_message(self, message: OverlayMessage) -> str:
        """Add a message to the overlay queue. Returns the message_id."""
        self._message_queue.append(message)
        logger.debug("OverlayUI: queued message '%s' (%s)", message.text[:40], message.message_id)
        return message.message_id

    def dismiss_message(self, message_id: str) -> bool:
        """Mark a queued message as dismissed."""
        for msg in self._message_queue:
            if msg.message_id == message_id:
                msg.dismissed = True
                return True
        return False

    def active_messages(self) -> list[OverlayMessage]:
        """Return messages that are not expired or dismissed."""
        return [m for m in self._message_queue if not m.expired and not m.dismissed]

    def flush_expired(self) -> int:
        """Remove expired/dismissed messages from the queue. Returns count removed."""
        before = len(self._message_queue)
        to_keep = deque(
            (m for m in self._message_queue if not m.expired and not m.dismissed),
            maxlen=_MAX_MESSAGE_QUEUE,
        )
        self._message_queue = to_keep
        return before - len(to_keep)

    def render_message_bar(self) -> str:
        """Generate HTML snippet for all active overlay messages."""
        msgs = self.active_messages()
        if not msgs:
            return ""
        items = "".join(
            f'<div class="sov-msg" id="msg-{m.message_id}" '
            f'style="color:{m.color};border-left:3px solid {m.color};padding:6px 10px;'
            f'margin-bottom:4px;font-size:12px;">{m.text}'
            + (
                f'<script>setTimeout(()=>{{var e=document.getElementById("msg-{m.message_id}");'
                f'if(e)e.remove();}},{m.duration_ms});</script>'
                if m.duration_ms > 0 else ""
            )
            + "</div>"
            for m in msgs
        )
        pos_css = _POSITION_CSS.get("bottom-center", "bottom:24px; left:50%;")
        return (
            f'<div id="sov-msg-bar" style="position:fixed;{pos_css}'
            f'z-index:9999;max-width:420px;pointer-events:none;">{items}</div>'
        )

    # ── HTML generation ───────────────────────────────────────────────────

    def render_panel(self, config: PanelConfig) -> str:
        """Generate self-contained HTML for one overlay panel."""
        pos_css = _POSITION_CSS.get(config.position, _POSITION_CSS["top-right"])
        theme_css = _THEME_CSS.get(config.theme, _THEME_CSS["dark"])
        auto_hide_js = (
            f"setTimeout(()=>document.getElementById('{config.panel_id}').style.display='none',"
            f"{int(config.auto_hide_s * 1000)});"
            if config.auto_hide_s > 0 else ""
        )
        rows = "\n".join(
            f"<div class='row'><span class='label'>{k}</span>"
            f"<span class='value'>{v}</span></div>"
            for k, v in config.data.items()
        )
        return f"""\
<div id="{config.panel_id}" style="
    position:fixed; {pos_css}
    width:{config.width_px}px;
    opacity:{config.opacity};
    {theme_css}
    border-radius:10px; padding:12px 14px;
    font-family:'JetBrains Mono','Courier New',monospace;
    font-size:12px; z-index:{config.z_index};
    pointer-events:none; user-select:none;
">
  <div style="font-size:11px; font-weight:700; letter-spacing:0.08em;
              text-transform:uppercase; margin-bottom:8px; color:#06b6d4;">
    {config.title}
  </div>
  <style>
    #{config.panel_id} .row{{display:flex;justify-content:space-between;
                             padding:2px 0;border-bottom:1px solid rgba(255,255,255,0.04);}}
    #{config.panel_id} .label{{color:#6b7280;}}
    #{config.panel_id} .value{{color:#e2e8f0;font-weight:500;}}
  </style>
  {rows}
</div>
<script>
  (function(){{
    {auto_hide_js}
    if(window.__sovereignWS){{
      window.__sovereignWS.addEventListener('message', function(e){{
        try{{
          var d=JSON.parse(e.data);
          if(d.panel_id==='{config.panel_id}' && d.data){{
            var el=document.getElementById('{config.panel_id}');
            if(el) el.querySelectorAll('.value').forEach(function(v,i){{
              var keys=Object.keys(d.data);
              if(keys[i]) v.textContent=d.data[keys[i]];
            }});
          }}
          if(d.type==='overlay_message'){{
            var bar=document.getElementById('sov-msg-bar');
            if(bar){{
              var div=document.createElement('div');
              div.style.cssText='color:'+(d.color||'#06b6d4')+
                ';border-left:3px solid '+(d.color||'#06b6d4')+
                ';padding:6px 10px;margin-bottom:4px;font-size:12px;';
              div.textContent=d.text;
              bar.appendChild(div);
              if(d.duration_ms>0) setTimeout(()=>div.remove(), d.duration_ms);
            }}
          }}
        }}catch(ex){{}}
      }});
    }}
  }})();
</script>"""

    def render_hud_page(self, ws_url: str = "ws://localhost:8080/ws") -> str:
        """Generate a full-screen transparent HUD HTML page."""
        panels_html = "\n".join(
            self.render_panel(cfg) for cfg in self._panels.values()
        )
        msg_bar = self.render_message_bar()
        return f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <title>SOVEREIGN HUD</title>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet"/>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box;}}
    body{{background:transparent;overflow:hidden;font-family:'JetBrains Mono',monospace;}}
    canvas#hud-canvas{{position:fixed;top:0;left:0;width:100vw;height:100vh;
                       pointer-events:none;z-index:8999;}}
  </style>
</head>
<body>
<canvas id="hud-canvas"></canvas>
{panels_html}
{msg_bar}
<script>
(function(){{
  var ws;
  function connect(){{
    ws = new WebSocket("{ws_url}");
    window.__sovereignWS = ws;
    ws.onopen  = function(){{ console.log("HUD WS connected"); }};
    ws.onclose = function(){{ setTimeout(connect, 2000); }};
    ws.onmessage = function(e){{
      try{{
        var d = JSON.parse(e.data);
        if(d.type === "agent_status") updateAgentDot(d);
        if(d.type === "health")       updateHealthBar(d);
      }}catch(ex){{}}
    }};
  }}
  connect();

  var canvas = document.getElementById("hud-canvas");
  var ctx = canvas.getContext("2d");
  function resizeCanvas(){{
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
  }}
  window.addEventListener("resize", resizeCanvas);
  resizeCanvas();

  var scanY = 0;
  function drawScanLine(){{
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "rgba(6,182,212,0.03)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, scanY);
    ctx.lineTo(canvas.width, scanY);
    ctx.stroke();
    scanY = (scanY + 0.5) % canvas.height;
    requestAnimationFrame(drawScanLine);
  }}
  drawScanLine();

  function updateAgentDot(d){{ /* hook for agent status dots */ }}
  function updateHealthBar(d){{ /* hook for health bar */ }}
}})();
</script>
</body>
</html>"""

    # ── Convenience builders ──────────────────────────────────────────────

    def build_agent_status_panel(self, agents: list[dict]) -> PanelConfig:
        data = {a["id"]: a.get("status", "idle") for a in agents[:12]}
        return PanelConfig(
            panel_id="agent_status",
            title="Agent Swarm",
            position="top-right",
            data=data,
        )

    def build_health_panel(self, health: dict) -> PanelConfig:
        return PanelConfig(
            panel_id="system_health",
            title="System Health",
            position="top-left",
            data={
                "Overall":  health.get("overall", "—"),
                "Agents":   str(health.get("agents_registered", "—")),
                "Tools":    str(health.get("tools_registered", "—")),
                "Budget":   health.get("budget", {}).get("cost_usd", "—"),
            },
        )

    def notify(self, text: str, color: str = "#06b6d4", duration_ms: int = 4000) -> str:
        """Shorthand: push a transient notification message and return its ID."""
        msg = OverlayMessage(text=text, color=color, duration_ms=duration_ms)
        return self.push_message(msg)

    # ── Convenience aliases ───────────────────────────────────────────────

    def add_message(
        self,
        text: str,
        color: str = "#06b6d4",
        duration_ms: int = 3000,
        position: str = "bottom-center",
    ) -> str:
        """Queue a display message and return its message_id.

        This is an alias for :meth:`push_message` with keyword-arg style
        parameters, making the API easier to use from test code and the CLI.
        """
        msg = OverlayMessage(text=text, color=color, duration_ms=duration_ms, position=position)
        return self.push_message(msg)

    def clear(self) -> int:
        """Remove all queued messages (expired or not). Returns the count cleared."""
        count = len(self._message_queue)
        self._message_queue.clear()
        return count

    def get_pending(self) -> list[OverlayMessage]:
        """Return all queued messages that have not yet expired or been dismissed.

        Equivalent to :meth:`active_messages` — provided as an alternative name
        to match the interface contract expected by the test suite.
        """
        return self.active_messages()
