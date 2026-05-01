#!/usr/bin/env python3
"""
SOVEREIGN AI OS — CLI entry point.

Usage:
  python main.py run "Your request here"
  python main.py run --interactive
  python main.py demo
  python main.py status
  sovereign run "..."          (if installed via: pip install -e .)
"""
from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="sovereign",
    help="SOVEREIGN AI OS — Multi-agent orchestration operating system.",
    no_args_is_help=True,
)
console = Console()


# ---------------------------------------------------------------------------
# run command
# ---------------------------------------------------------------------------

@app.command()
def run(
    prompt: Optional[str] = typer.Argument(
        None, help="Request to process. Omit with --interactive for REPL mode."
    ),
    mode: str = typer.Option(
        "command", "--mode", "-m",
        help="Operating mode: command|business|personal|finance|study|travel|research|builder",
    ),
    config: str = typer.Option(
        "config/sovereign.yaml", "--config", "-c", help="Path to sovereign.yaml"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Start interactive REPL session."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show full JSON output."
    ),
) -> None:
    """Process a request through the SOVEREIGN AI OS."""
    import os
    os.environ.setdefault("SOVEREIGN_DEFAULT_MODE", mode)

    try:
        from sovereign.bootstrap import create_orchestrator
        orch = create_orchestrator(config)
    except EnvironmentError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(1)

    if interactive:
        asyncio.run(_interactive_loop(orch, verbose=verbose))
    elif prompt:
        result = asyncio.run(orch.handle_request(prompt))
        _print_result(result, verbose=verbose)
    else:
        console.print("[yellow]Provide a prompt or use --interactive[/yellow]")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# demo command
# ---------------------------------------------------------------------------

@app.command()
def demo(
    config: str = typer.Option("config/sovereign.yaml", "--config", "-c"),
) -> None:
    """
    Run a minimal demo to verify Claude API connectivity and the full pipeline.

    Sends a fixed prompt through: InputPipeline → CEOAgent → WorkerAgent → StructuredOutput.
    """
    console.print(Panel(
        "[bold cyan]SOVEREIGN AI OS[/bold cyan] — Demo\n"
        "Verifying Claude API connectivity and full pipeline...",
        border_style="cyan",
    ))

    try:
        from sovereign.bootstrap import create_orchestrator
        orch = create_orchestrator(config)
    except EnvironmentError as exc:
        console.print(f"[red]Setup error:[/red] {exc}")
        raise typer.Exit(1)

    result = asyncio.run(orch.handle_request(
        "Give me a brief executive summary of the SOVEREIGN AI OS capabilities "
        "and suggest my top 3 next actions to set it up."
    ))
    _print_result(result, verbose=True)


# ---------------------------------------------------------------------------
# status command
# ---------------------------------------------------------------------------

@app.command()
def status(
    config: str = typer.Option("config/sovereign.yaml", "--config", "-c"),
) -> None:
    """Show system health, registry status, and token usage."""
    try:
        from sovereign.bootstrap import create_orchestrator
        orch = create_orchestrator(config)
    except EnvironmentError as exc:
        console.print(f"[red]Setup error:[/red] {exc}")
        raise typer.Exit(1)

    health = orch.health()
    usage = orch.get_usage()

    # Health table
    colour = {"ok": "green", "degraded": "yellow", "critical": "red"}.get(
        health["overall"], "white"
    )
    table = Table(title="System Health", show_header=True)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    for check, state in health["checks"].items():
        c = {"ok": "green", "degraded": "yellow"}.get(state, "red")
        table.add_row(check, f"[{c}]{state}[/{c}]")
    console.print(table)

    if health["alerts"]:
        for alert in health["alerts"]:
            console.print(f"[yellow]⚠  {alert}[/yellow]")

    # Usage
    console.print(f"\n[bold]Token usage:[/bold] {usage}")
    console.print(f"[bold]Overall:[/bold] [{colour}]{health['overall'].upper()}[/{colour}]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _interactive_loop(orch, *, verbose: bool = False) -> None:
    """REPL loop — type 'exit' or Ctrl-C to quit."""
    console.print(Panel(
        "[bold cyan]SOVEREIGN AI OS[/bold cyan] — Interactive Mode\n"
        "Type [yellow]exit[/yellow] or [yellow]quit[/yellow] to end the session.\n"
        "Type [yellow]status[/yellow] to check system health.",
        border_style="cyan",
    ))

    while True:
        try:
            user_input = console.input("\n[bold green]▶ [/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Session ended.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            console.print("[dim]Goodbye.[/dim]")
            break
        if user_input.lower() == "status":
            health = orch.health()
            console.print(health)
            continue

        with console.status("[dim]Processing...[/dim]"):
            result = await orch.handle_request(user_input)
        _print_result(result, verbose=verbose)


def _print_result(result, *, verbose: bool = False) -> None:
    """Pretty-print a StructuredOutput to the terminal."""
    colour_map = {
        "success":          "green",
        "partial":          "yellow",
        "failed":           "red",
        "escalated":        "magenta",
        "pending_approval": "yellow",
        "skipped":          "dim",
    }
    colour = colour_map.get(result.status.value, "white")

    console.print(Panel(
        result.result,
        title=f"[{colour}]{result.status.value.upper()}[/{colour}]  "
              f"[dim]{result.agent_id} · {result.session_id}[/dim]",
        border_style=colour,
        expand=False,
    ))

    if result.requires_human_review:
        console.print("[bold yellow]⚠  This result requires human review.[/bold yellow]")

    if result.error:
        console.print(f"[red]Error:[/red] {result.error}")

    tokens = result.tokens_used
    console.print(
        f"[dim]Tokens — in:{tokens.get('input',0)} "
        f"out:{tokens.get('output',0)} "
        f"cache_read:{tokens.get('cache_read',0)} "
        f"confidence:{result.confidence:.0%}[/dim]"
    )

    if verbose and result.data:
        console.print(JSON(result.to_json()))


# ---------------------------------------------------------------------------
# serve command
# ---------------------------------------------------------------------------

@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Bind address."),
    port: int = typer.Option(8080, "--port", "-p", help="Port number."),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev)."),
    config: str = typer.Option("config/sovereign.yaml", "--config", "-c"),
) -> None:
    """Start the SOVEREIGN AI OS web interface (FastAPI + WebSocket)."""
    import os
    import uvicorn
    os.environ.setdefault("SOVEREIGN_CONFIG", config)
    console.print(Panel(
        f"[bold cyan]SOVEREIGN AI OS[/bold cyan] — Web UI\n"
        f"Listening on [yellow]http://{host}:{port}[/yellow]\n"
        f"WebSocket at [yellow]ws://{host}:{port}/ws[/yellow]",
        border_style="cyan",
    ))
    uvicorn.run(
        "sovereign.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@app.command()
def telegram(
    config: str = typer.Option("config/sovereign.yaml", "--config", "-c"),
    token: str = typer.Option("", "--token", "-t", help="Telegram bot token (overrides TELEGRAM_BOT_TOKEN env var)."),
    allowed: str = typer.Option("", "--allowed", "-a", help="Comma-separated allowed chat IDs."),
) -> None:
    """Start the SOVEREIGN Telegram bot (long-poll, bidirectional)."""
    import os
    os.environ.setdefault("SOVEREIGN_CONFIG", config)
    bot_token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        console.print("[red]No bot token. Set TELEGRAM_BOT_TOKEN or pass --token.[/red]")
        raise typer.Exit(1)
    allowed_ids = allowed or os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
    try:
        from sovereign.bootstrap import create_orchestrator
        orch = create_orchestrator(config)
    except EnvironmentError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(1)

    console.print(Panel(
        "[bold cyan]SOVEREIGN AI OS[/bold cyan] — Telegram Bot\n"
        "Long-poll mode active. Press Ctrl-C to stop.",
        border_style="cyan",
    ))

    async def _run() -> None:
        from sovereign.integrations.telegram_bot import TelegramBot
        bot = TelegramBot(orch, bot_token, allowed_ids)
        try:
            await bot.start()
        except KeyboardInterrupt:
            bot.stop()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# agent sub-commands
# ---------------------------------------------------------------------------

agent_app = typer.Typer(name="agent", help="Manage and inspect agents.", no_args_is_help=True)
app.add_typer(agent_app)


@agent_app.command("list")
def agent_list(
    config: str = typer.Option("config/sovereign.yaml", "--config", "-c"),  # noqa: ARG001
) -> None:
    """List all registered agents (no API key required)."""
    import inspect
    import importlib
    from sovereign.swarm.base_agent import BaseAgent

    _swarm_modules = [
        "sovereign.swarm.business_agents",
        "sovereign.swarm.finance_agents",
        "sovereign.swarm.personal_agents",
        "sovereign.swarm.personal_workers",
        "sovereign.swarm.imperial_agents",
        "sovereign.swarm.decision_networking_agents",
        "sovereign.swarm.security_agents",
        "sovereign.swarm.offline_agents",
        "sovereign.swarm.black_tier_agents",
        "sovereign.swarm.special_agent",
        "sovereign.swarm.domain_chiefs",
        "sovereign.executive.ceo_agent",
        "sovereign.executive.chief_of_staff",
        "sovereign.executive.coordinator",
        "sovereign.executive.guardian",
        "sovereign.executive.executive_assistant",
        "sovereign.executive.task_setter",
    ]

    agents: list[tuple[str, str, str]] = []
    for mod_name in _swarm_modules:
        try:
            mod = importlib.import_module(mod_name)
            for _name, obj in inspect.getmembers(mod, inspect.isclass):
                if (
                    issubclass(obj, BaseAgent)
                    and obj is not BaseAgent
                    and hasattr(obj, "agent_id")
                    and obj.agent_id
                ):
                    agents.append((
                        obj.agent_id,
                        getattr(obj, "agent_name", obj.agent_id),
                        getattr(obj, "model", "—"),
                    ))
        except Exception:
            pass

    # Deduplicate by agent_id
    seen: set[str] = set()
    unique = [(aid, name, model) for aid, name, model in agents if aid not in seen and not seen.add(aid)]  # type: ignore[func-returns-value]

    table = Table(title=f"Registered Agents ({len(unique)} total)")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Model", style="dim")
    for aid, name, model in sorted(unique, key=lambda x: x[0]):
        table.add_row(aid, name, model)
    console.print(table)


@agent_app.command("info")
def agent_info(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    config: str = typer.Option("config/sovereign.yaml", "--config", "-c"),  # noqa: ARG001
) -> None:
    """Show detailed info about a specific agent (no API key required)."""
    import inspect
    import importlib
    from sovereign.swarm.base_agent import BaseAgent

    _swarm_modules = [
        "sovereign.swarm.business_agents", "sovereign.swarm.finance_agents",
        "sovereign.swarm.personal_agents", "sovereign.swarm.personal_workers",
        "sovereign.swarm.imperial_agents", "sovereign.swarm.decision_networking_agents",
        "sovereign.swarm.security_agents", "sovereign.swarm.offline_agents",
        "sovereign.swarm.black_tier_agents", "sovereign.swarm.special_agent",
        "sovereign.swarm.domain_chiefs", "sovereign.executive.ceo_agent",
        "sovereign.executive.chief_of_staff", "sovereign.executive.coordinator",
        "sovereign.executive.guardian", "sovereign.executive.executive_assistant",
        "sovereign.executive.task_setter",
    ]

    found = None
    for mod_name in _swarm_modules:
        try:
            mod = importlib.import_module(mod_name)
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if (
                    issubclass(obj, BaseAgent)
                    and obj is not BaseAgent
                    and getattr(obj, "agent_id", None) == agent_id
                ):
                    found = obj
                    break
        except Exception:
            pass
        if found:
            break

    if found is None:
        console.print(f"[red]Agent '{agent_id}' not found.[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold]ID:[/bold] {found.agent_id}\n"
        f"[bold]Name:[/bold] {getattr(found, 'agent_name', found.agent_id)}\n"
        f"[bold]Model:[/bold] {getattr(found, 'model', '—')}\n"
        f"[bold]Requires review:[/bold] {getattr(found, 'requires_review', False)}\n"
        f"[bold]Confidence:[/bold] {getattr(found, 'default_confidence', '—')}",
        title=f"Agent: {agent_id}",
        border_style="cyan",
    ))


# ---------------------------------------------------------------------------
# connector sub-commands
# ---------------------------------------------------------------------------

connector_app = typer.Typer(name="connector", help="Manage data connectors.", no_args_is_help=True)
app.add_typer(connector_app)


@connector_app.command("list")
def connector_list() -> None:
    """List all registered connectors and their status."""
    import inspect
    import sovereign.integrations.connectors as _cpkg
    from sovereign.integrations.connectors import __all__ as _call
    from sovereign.integrations.connectors.connector_base import ConnectorStatus  # noqa: F401

    connectors = []
    for _name in _call:
        _obj = getattr(_cpkg, _name, None)
        if _obj and inspect.isclass(_obj) and hasattr(_obj, "connector_id") and _obj.connector_id:
            connectors.append(_obj())

    table = Table(title=f"Connectors ({len(connectors)} total)")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("OAuth")
    table.add_column("Description", style="dim")
    for c in connectors:
        status_colour = {
            "connected": "green", "beta": "yellow",
            "disconnected": "red", "error": "red",
        }.get(c.connector_status.value, "white")
        table.add_row(
            c.connector_id,
            c.connector_name,
            f"[{status_colour}]{c.connector_status.value}[/{status_colour}]",
            "✓" if c.requires_oauth else "—",
            c.connector_description or "—",
        )
    console.print(table)


@connector_app.command("sync")
def connector_sync(
    connector_id: str = typer.Argument(..., help="Connector ID to sync"),
) -> None:
    """Trigger an immediate sync for a connector."""
    import inspect
    import sovereign.integrations.connectors as _cpkg
    from sovereign.integrations.connectors import __all__ as _call
    from sovereign.integrations.connectors.sync_engine import SyncEngine

    all_connectors = {}
    for _name in _call:
        _obj = getattr(_cpkg, _name, None)
        if _obj and inspect.isclass(_obj) and hasattr(_obj, "connector_id") and _obj.connector_id:
            all_connectors[_obj.connector_id] = _obj

    if connector_id not in all_connectors:
        available = ", ".join(sorted(all_connectors.keys()))
        console.print(f"[red]Unknown connector: {connector_id}[/red]")
        console.print(f"[yellow]Available connector IDs:[/yellow] {available}")
        raise typer.Exit(1)

    connector = all_connectors[connector_id]()
    engine = SyncEngine()
    engine.register(connector)

    async def _run():
        result = await engine.sync_one(connector_id)
        if result and result.success:
            console.print(f"[green]✓ Synced {connector_id}: {result.records_synced} records[/green]")
        else:
            err = result.errors if result else ["unknown"]
            console.print(f"[red]✗ Sync failed: {err}[/red]")

    asyncio.run(_run())


@connector_app.command("health")
def connector_health() -> None:
    """Check health of all connectors."""
    import inspect
    import sovereign.integrations.connectors as _cpkg
    from sovereign.integrations.connectors import __all__ as _call

    connectors = []
    for _name in _call:
        _obj = getattr(_cpkg, _name, None)
        if _obj and inspect.isclass(_obj) and hasattr(_obj, "connector_id") and _obj.connector_id:
            connectors.append(_obj())

    async def _run():
        health_results = await asyncio.gather(
            *[c.health() for c in connectors], return_exceptions=True
        )
        table = Table(title=f"Connector Health ({len(connectors)} connectors)")
        table.add_column("ID", style="cyan")
        table.add_column("Status")
        table.add_column("Records")
        table.add_column("Error", style="dim")
        for c, h in zip(connectors, health_results):
            if isinstance(h, Exception):
                table.add_row(c.connector_id, "[red]error[/red]", "—", str(h))
            else:
                sc = {"connected": "green", "beta": "yellow"}.get(h.status.value, "red")
                table.add_row(
                    c.connector_id,
                    f"[{sc}]{h.status.value}[/{sc}]",
                    str(h.records_synced),
                    h.last_error or "—",
                )
        console.print(table)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# skill sub-commands
# ---------------------------------------------------------------------------

skill_app = typer.Typer(name="skill", help="Manage skills.", no_args_is_help=True)
app.add_typer(skill_app)


@skill_app.command("list")
def skill_list() -> None:
    """List all available skills."""
    from sovereign.skills import get_skill_manager
    mgr = get_skill_manager()
    skills = mgr.list_all()
    table = Table(title="Skills")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Approval")
    table.add_column("Tags", style="dim")
    for s in skills:
        sc = "green" if s["status"] == "active" else "yellow"
        table.add_row(
            s["skill_id"],
            s["name"],
            f"[{sc}]{s['status']}[/{sc}]",
            "[red]Yes[/red]" if s["requires_approval"] else "—",
            ", ".join(s.get("tags", [])),
        )
    console.print(table)


@skill_app.command("enable")
def skill_enable(skill_id: str = typer.Argument(...)) -> None:
    """Enable a skill."""
    from sovereign.skills import get_skill_manager
    try:
        get_skill_manager().enable(skill_id)
        console.print(f"[green]✓ Skill '{skill_id}' enabled.[/green]")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")


@skill_app.command("disable")
def skill_disable(skill_id: str = typer.Argument(...)) -> None:
    """Disable a skill."""
    from sovereign.skills import get_skill_manager
    try:
        get_skill_manager().disable(skill_id)
        console.print(f"[yellow]✓ Skill '{skill_id}' disabled.[/yellow]")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")


@skill_app.command("run")
def skill_run(
    skill_id: str = typer.Argument(..., help="Skill ID"),
    input_json: str = typer.Option("{}", "--input", "-i", help="JSON input params"),
) -> None:
    """Run a skill with provided inputs."""
    import json as _json
    from sovereign.skills import get_skill_manager
    try:
        params = _json.loads(input_json)
    except _json.JSONDecodeError as exc:
        console.print(f"[red]Invalid JSON: {exc}[/red]")
        raise typer.Exit(1)

    async def _run():
        mgr = get_skill_manager()
        result = await mgr.execute(skill_id, params)
        colour = "green" if result.success else "red"
        console.print(Panel(
            str(result.output or result.error),
            title=f"[{colour}]Skill: {skill_id}[/{colour}]",
            border_style=colour,
        ))
        console.print(f"[dim]Duration: {result.duration_ms:.0f}ms[/dim]")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# lab sub-commands
# ---------------------------------------------------------------------------

lab_app = typer.Typer(name="lab", help="Manage experimental labs.", no_args_is_help=True)
app.add_typer(lab_app)


@lab_app.command("list")
def lab_list() -> None:
    """List all labs with experiment counts and status."""
    import importlib
    import pathlib as _pl
    table = Table(title="SOVEREIGN Labs (21)")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Templates", justify="right")
    table.add_column("Data File", style="dim")
    for f in sorted(_pl.Path("sovereign/labs").glob("*.py")):
        if f.name in ("__init__.py", "labs_framework.py"):
            continue
        try:
            mod = importlib.import_module(f"sovereign.labs.{f.stem}")
            for name in dir(mod):
                obj = getattr(mod, name)
                if isinstance(obj, type) and hasattr(obj, "lab_id") and obj.lab_id not in ("base", ""):
                    data_f = _pl.Path(f"data/labs/{obj.lab_id}_experiments.json")
                    exists = "[green]✓[/green]" if data_f.exists() else "[red]✗[/red]"
                    table.add_row(
                        obj.lab_id, obj.lab_name,
                        str(len(getattr(obj, "experiment_templates", []))),
                        exists,
                    )
        except Exception:
            pass
    console.print(table)


@lab_app.command("status")
def lab_status(lab_id: str = typer.Argument(..., help="Lab ID")) -> None:
    """Show detailed status of a lab including running experiments."""
    import importlib
    import pathlib as _pl
    for f in _pl.Path("sovereign/labs").glob("*.py"):
        if f.name in ("__init__.py", "labs_framework.py"):
            continue
        try:
            mod = importlib.import_module(f"sovereign.labs.{f.stem}")
            for name in dir(mod):
                obj = getattr(mod, name)
                if isinstance(obj, type) and hasattr(obj, "lab_id") and obj.lab_id == lab_id:
                    data_path = f"data/labs/{lab_id}_experiments.json"
                    instance = obj(data_path=data_path)
                    report = instance.status_report()
                    console.print(Panel(
                        f"[bold]{report['lab_name']}[/bold]\n{report['description']}\n\n"
                        f"[dim]Agents:[/dim] {', '.join(report['agents'])}\n"
                        f"[dim]Benchmarks:[/dim] {report['benchmarks']}\n"
                        f"[dim]Templates:[/dim] {report['templates_available']}",
                        title=f"Lab: {lab_id}",
                        border_style="cyan",
                    ))
                    db = report["experiment_summary"]
                    console.print(f"Total experiments: {db['total']} | By status: {db['by_status']}")
                    if report["running"]:
                        console.print("\n[yellow]Running:[/yellow]")
                        for r in report["running"]:
                            console.print(f"  · [{r['id']}] {r['name']}")
                    return
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")
            return
    console.print(f"[red]Lab '{lab_id}' not found.[/red]")


@lab_app.command("experiments")
def lab_experiments(lab_id: str = typer.Argument(..., help="Lab ID")) -> None:
    """List all experiments in a lab."""
    import json as _json
    import pathlib as _pl
    data_path = _pl.Path(f"data/labs/{lab_id}_experiments.json")
    if not data_path.exists():
        console.print(f"[yellow]No data file for lab '{lab_id}'. Run: python main.py lab run {lab_id}[/yellow]")
        return
    raw = _json.loads(data_path.read_text())
    table = Table(title=f"Experiments: {lab_id}")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Tags", style="dim")
    for exp_id, exp in raw.items():
        s = exp.get("status", "draft")
        sc = {"running": "yellow", "completed": "green", "graduated": "magenta", "failed": "red", "draft": "dim"}.get(s, "white")
        table.add_row(exp_id, exp["name"], f"[{sc}]{s}[/{sc}]", ", ".join(exp.get("tags", [])))
    console.print(table)


@lab_app.command("run")
def lab_run(
    lab_id: str = typer.Argument(..., help="Lab ID"),
    template: int = typer.Option(0, "--template", "-t", help="Template index (0-based)"),
) -> None:
    """Start a quick experiment in a lab from its templates."""
    import importlib
    import pathlib as _pl
    for f in _pl.Path("sovereign/labs").glob("*.py"):
        if f.name in ("__init__.py", "labs_framework.py"):
            continue
        try:
            mod = importlib.import_module(f"sovereign.labs.{f.stem}")
            for name in dir(mod):
                obj = getattr(mod, name)
                if isinstance(obj, type) and hasattr(obj, "lab_id") and obj.lab_id == lab_id:
                    data_path = f"data/labs/{lab_id}_experiments.json"
                    instance = obj(data_path=data_path)
                    exp = instance.quick_experiment(template_index=template)
                    console.print(f"[green]✓ Started experiment:[/green] [{exp.experiment_id}] {exp.name}")
                    console.print(f"[dim]Status: {exp.status.value} | Hypothesis: {exp.hypothesis.statement}[/dim]")
                    return
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")
            return
    console.print(f"[red]Lab '{lab_id}' not found.[/red]")


# ---------------------------------------------------------------------------
# model sub-commands
# ---------------------------------------------------------------------------

model_app = typer.Typer(name="model", help="Browse the model catalog.", no_args_is_help=True)
app.add_typer(model_app)


@model_app.command("list")
def model_list(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Filter by provider"),
    local: bool = typer.Option(False, "--local", help="Show only local/offline models"),
    tier: Optional[str] = typer.Option(None, "--tier", "-t", help="Filter by tier"),
) -> None:
    """List all models in the catalog."""
    from sovereign.intelligence import get_model_catalog, ModelTier

    catalog = get_model_catalog()
    if local:
        models = catalog.local_models()
    elif provider:
        models = catalog.by_provider(provider)
    elif tier:
        try:
            t = ModelTier(tier)
            models = catalog.by_tier(t)
        except ValueError:
            console.print(f"[red]Unknown tier: {tier}. Options: frontier|balanced|fast|local[/red]")
            raise typer.Exit(1)
    else:
        models = catalog.all()

    table = Table(title="Model Catalog")
    table.add_column("Model ID", style="cyan")
    table.add_column("Provider")
    table.add_column("Tier")
    table.add_column("Context", justify="right")
    table.add_column("Cost/1k in", justify="right", style="dim")
    table.add_column("Private")
    for m in models:
        tier_colour = {
            "frontier": "magenta", "balanced": "cyan",
            "fast": "green", "local": "yellow",
        }.get(m.tier.value, "white")
        table.add_row(
            m.model_id,
            m.provider,
            f"[{tier_colour}]{m.tier.value}[/{tier_colour}]",
            f"{m.context_window_tokens // 1000}k",
            f"${m.cost_per_1k_input_usd:.5f}" if m.cost_per_1k_input_usd > 0 else "free",
            "[green]✓[/green]" if m.privacy_safe else "—",
        )
    console.print(table)


# ---------------------------------------------------------------------------
# health command (standalone)
# ---------------------------------------------------------------------------

@app.command()
def health(
    config: str = typer.Option("config/sovereign.yaml", "--config", "-c"),
    engines: bool = typer.Option(False, "--engines", "-e", help="Also probe engine backends"),
) -> None:
    """Quick system health check."""
    try:
        from sovereign.bootstrap import create_orchestrator
        orch = create_orchestrator(config)
        h = orch.health()
        colour = {"ok": "green", "degraded": "yellow", "critical": "red"}.get(h["overall"], "white")
        console.print(f"[{colour}]System: {h['overall'].upper()}[/{colour}]")
        for check, state in h.get("checks", {}).items():
            c = "green" if state == "ok" else "yellow"
            console.print(f"  [{c}]{check}[/{c}]: {state}")
    except EnvironmentError as exc:
        console.print(f"[red]Config error: {exc}[/red]")

    if engines:
        async def _probe():
            from sovereign.engine.discovery import discover_engines
            multi = await discover_engines()
            h = await multi.health()
            console.print(f"\nEngines: [{('green' if h.available_models else 'red')}]{h.status.value}[/]")
            for m in h.available_models[:8]:
                console.print(f"  · {m}")
        asyncio.run(_probe())


# ---------------------------------------------------------------------------
# vault sub-commands
# ---------------------------------------------------------------------------

vault_app = typer.Typer(name="vault", help="Manage the secrets vault.", no_args_is_help=True)
app.add_typer(vault_app)


@vault_app.command("set")
def vault_set(
    key: str = typer.Argument(..., help="Secret key"),
    value: str = typer.Argument(..., help="Secret value"),
) -> None:
    """Store a secret in the vault."""
    try:
        from sovereign.security.secrets import get_secret_manager
        get_secret_manager().set(key, value)
        console.print(f"[green]✓ Secret '{key}' stored.[/green]")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")


@vault_app.command("get")
def vault_get(key: str = typer.Argument(..., help="Secret key")) -> None:
    """Retrieve a secret from the vault."""
    try:
        from sovereign.security.secrets import get_secret_manager
        val = get_secret_manager().get(key)
        if val is None:
            console.print(f"[yellow]Key '{key}' not found.[/yellow]")
        else:
            console.print(f"[green]{key}[/green] = {val[:4]}{'*' * max(0, len(val) - 4)}")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")


@vault_app.command("list")
def vault_list() -> None:
    """List all stored secret keys (values hidden)."""
    try:
        from sovereign.security.secrets import get_secret_manager
        keys = get_secret_manager().list_keys()
        if not keys:
            console.print("[dim]No secrets stored.[/dim]")
            return
        for k in keys:
            console.print(f"  · {k}")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")


@vault_app.command("delete")
def vault_delete(key: str = typer.Argument(..., help="Secret key to delete")) -> None:
    """Delete a secret from the vault."""
    try:
        from sovereign.security.secrets import get_secret_manager
        get_secret_manager().delete(key)
        console.print(f"[yellow]✓ Secret '{key}' deleted.[/yellow]")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")


# ---------------------------------------------------------------------------
# brief command — morning daily briefing
# ---------------------------------------------------------------------------

@app.command()
def brief(
    config: str = typer.Option(
        "config/sovereign.yaml", "--config", "-c", help="Path to sovereign.yaml"
    ),
    send_telegram: bool = typer.Option(
        False, "--telegram", help="Send briefing to Telegram (requires TELEGRAM_BOT_TOKEN)"
    ),
) -> None:
    """
    Print (and optionally send) a morning briefing.

    Shows: date, time, weather hint, upcoming calendar events, urgent tasks,
    open decisions, and motivational context from your personal constitution.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    console.print(Panel(
        f"[cyan]🌅 SOVEREIGN Morning Briefing[/cyan]\n"
        f"[dim]{now.strftime('%A, %d %B %Y — %H:%M UTC')}[/dim]",
        style="bold",
    ))

    briefing_lines: list[str] = []

    try:
        from sovereign.memory.domains.next_action import NextActionStore
        na = NextActionStore()
        urgent = na.urgent()
        overdue = na.overdue()
        if urgent or overdue:
            console.print("\n[yellow]⚡ Urgent tasks:[/yellow]")
            for a in (overdue + urgent)[:5]:
                prefix = "⚠️" if a in overdue else "→"
                console.print(f"  {prefix} {a.title}")
            briefing_lines.append(f"Urgent: {len(urgent)} | Overdue: {len(overdue)}")
    except Exception:
        pass

    try:
        from sovereign.memory.domains.decision import DecisionMemoryStore
        dec = DecisionMemoryStore()
        open_dec = dec.by_status("open")
        if open_dec:
            console.print("\n[violet]🧭 Open decisions:[/violet]")
            for d in open_dec[:3]:
                console.print(f"  · {d.title}")
    except Exception:
        pass

    try:
        from sovereign.memory.domains.diary import DiaryMemoryStore
        diary = DiaryMemoryStore()
        avg_mood = diary.average_mood(7)
        console.print(f"\n[dim]📓 Mood avg (7d): {avg_mood:.1f}/10[/dim]")
    except Exception:
        pass

    try:
        from sovereign.memory.domains.personal_constitution import PersonalConstitutionStore
        pcs = PersonalConstitutionStore()
        c = pcs.get_constitution()
        if c.daily_non_negotiables:
            console.print("\n[green]✅ Daily non-negotiables:[/green]")
            for item in c.daily_non_negotiables[:5]:
                console.print(f"  · {item}")
        if c.personal_mission:
            console.print(f"\n[bold]Mission:[/bold] {c.personal_mission}")
    except Exception:
        pass

    if send_telegram:
        async def _send() -> None:
            from sovereign.reporting.weekly_report import send_telegram_report
            text = "🌅 *Morning Briefing*\n" + "\n".join(briefing_lines)
            await send_telegram_report(text)
        asyncio.run(_send())
        console.print("\n[green]✓ Sent to Telegram.[/green]")


# ---------------------------------------------------------------------------
# report command — send weekly report
# ---------------------------------------------------------------------------

@app.command()
def report(
    config: str = typer.Option(
        "config/sovereign.yaml", "--config", "-c", help="Path to sovereign.yaml"
    ),
    print_only: bool = typer.Option(
        False, "--print", help="Print report to stdout instead of sending to Telegram."
    ),
    data_dir: str = typer.Option(
        "data", "--data-dir", help="Path to data directory."
    ),
) -> None:
    """Generate and send the weekly life report via Telegram."""
    from sovereign.reporting.weekly_report import build_weekly_report, send_telegram_report

    console.print("[cyan]Generating weekly report...[/cyan]")
    text = build_weekly_report(data_dir)

    if print_only:
        console.print(text)
        return

    async def _send() -> None:
        sent = await send_telegram_report(text)
        if sent:
            console.print("[green]✓ Weekly report sent to Telegram.[/green]")
        else:
            console.print("[yellow]Report printed (Telegram not configured).[/yellow]")
            console.print(text)

    asyncio.run(_send())


if __name__ == "__main__":
    app()
