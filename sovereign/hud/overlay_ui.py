"""Overlay UI — generates floating HTML/Canvas glass panels for the SOVEREIGN HUD."""
from __future__ import annotations

import json
import logging
import time
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


_POSITION_CSS = {
    "top-left":     "top:16px; left:16px;",
    "top-right":    "top:16px; right:16px;",
    "bottom-left":  "bottom:16px; left:16px;",
    "bottom-right": "bottom:16px; right:16px;",
    "center":       "top:50%; left:50%; transform:translate(-50%,-50%);",
}

_THEME_CSS = {
    "dark":    "background:rgba(10,10,15,0.92); border:1px solid #1e1e2e; color:#e2e8f0;",
    "glass":   "background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); "
               "backdrop-filter:blur(12px); color:#e2e8f0;",
    "minimal": "background:transparent; border:1px solid rgba(6,182,212,0.3); color:#06b6d4;",
}


class OverlayUI:
    """
    Builds standalone HTML overlay panels and a full HUD page
    that can be injected into any browser window or served as an
    always-on-top electron window.
    """

    def __init__(self) -> None:
        self._panels: dict[str, PanelConfig] = {}

    def register_panel(self, config: PanelConfig) -> None:
        self._panels[config.panel_id] = config

    def unregister_panel(self, panel_id: str) -> bool:
        return bool(self._panels.pop(panel_id, None))

    # ------------------------------------------------------------------
    # HTML generation
    # ------------------------------------------------------------------

    def render_panel(self, config: PanelConfig) -> str:
        """Generate self-contained HTML for one overlay panel."""
        pos_css   = _POSITION_CSS.get(config.position, _POSITION_CSS["top-right"])
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
    // Live update via WebSocket event
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
        }}catch(ex){{}}
      }});
    }}
  }})();
</script>"""

    def render_hud_page(self, ws_url: str = "ws://localhost:8080/ws") -> str:
        """
        Generate a full-screen transparent HUD HTML page.
        Can be opened in an Electron always-on-top window or a browser extension.
        """
        panels_html = "\n".join(
            self.render_panel(cfg) for cfg in self._panels.values()
        )
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

  // Subtle scan-line animation
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

    def update_panel_data(self, panel_id: str, data: dict[str, Any]) -> bool:
        panel = self._panels.get(panel_id)
        if not panel:
            return False
        panel.data.update(data)
        return True

    def build_agent_status_panel(self, agents: list[dict]) -> PanelConfig:
        """Convenience: build a panel showing agent status from a list of {id, status} dicts."""
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
