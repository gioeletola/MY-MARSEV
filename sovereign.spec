# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for SOVEREIGN AI OS local desktop app.

Build:
    pip install pyinstaller
    pyinstaller sovereign.spec

Output: dist/sovereign/  (directory mode)
        dist/sovereign-cli  (single executable, optional)
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(".").resolve()

block_cipher = None

# ── Collect data files ────────────────────────────────────────────────────────
datas = [
    ("config/*.yaml", "config"),
    ("prompts/system/*.txt", "prompts/system"),
    ("prompts/tasks/*.txt", "prompts/tasks"),
    ("sovereign/api/templates/*.html", "sovereign/api/templates"),
    ("sovereign/api/static", "sovereign/api/static"),
    ("sovereign/skills/data/*.toml", "sovereign/skills/data"),
    (".env.example", "."),
]

# ── Hidden imports (dynamic imports not caught by analysis) ──────────────────
hiddenimports = [
    # FastAPI / Starlette internals
    "starlette.routing",
    "starlette.middleware",
    "starlette.middleware.cors",
    "starlette.responses",
    "starlette.staticfiles",
    "starlette.templating",
    "fastapi.middleware.cors",
    "fastapi.staticfiles",
    "fastapi.templating",
    # Pydantic
    "pydantic.deprecated.class_validators",
    "pydantic_core",
    # YAML / TOML
    "yaml",
    "tomllib",
    # Anthropic SDK
    "anthropic",
    "anthropic._client",
    "anthropic.types",
    # Structlog
    "structlog",
    "structlog.stdlib",
    # Rich / Typer
    "rich.console",
    "rich.table",
    "typer",
    # httpx
    "httpx",
    "httpx._client",
    # Sovereign modules
    "sovereign",
    "sovereign.bootstrap",
    "sovereign.orchestrator",
    "sovereign.api.server",
    "sovereign.api.auth",
    "sovereign.api.ws_handler",
    "sovereign.kernel.constitution",
    "sovereign.kernel.action_classes",
    "sovereign.memory.memory_manager",
    "sovereign.tools.tool_registry",
    "sovereign.tools.builtin.web_search",
    "sovereign.tools.builtin.file_ops",
    "sovereign.tools.builtin.code_exec",
    "sovereign.tools.builtin.memory_tool",
    "sovereign.tools.builtin.hash_tool",
    "sovereign.tools.builtin.url_tool",
    "sovereign.tools.builtin.date_tool",
    "sovereign.tools.builtin.text_analysis_tool",
    "sovereign.tools.builtin.base64_tool",
    "sovereign.tools.builtin.uuid_tool",
    "sovereign.tools.builtin.number_tool",
    "sovereign.tools.builtin.color_tool",
    "sovereign.tools.builtin.template_render_tool",
    "sovereign.tools.builtin.markdown_tool",
]

a = Analysis(
    ["main.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PIL",
        "cv2",
        "torch",
        "tensorflow",
        "jupyter",
        "IPython",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Directory bundle (recommended — faster startup) ───────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sovereign",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="sovereign",
)
