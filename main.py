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
    config: str = typer.Option("config/sovereign.yaml", "--config", "-c"),
) -> None:
    """List all registered agents."""
    from sovereign.bootstrap import create_orchestrator
    orch = create_orchestrator(config)
    agents = orch._agent_registry.list_all() if hasattr(orch, "_agent_registry") else []
    table = Table(title="Registered Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Model", style="dim")
    for a in agents:
        aid = getattr(a, "agent_id", str(a))
        name = getattr(a, "agent_name", aid)
        model = getattr(a, "model", "—")
        table.add_row(aid, name, model)
    console.print(table)


@agent_app.command("info")
def agent_info(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    config: str = typer.Option("config/sovereign.yaml", "--config", "-c"),
) -> None:
    """Show detailed info about a specific agent."""
    from sovereign.bootstrap import create_orchestrator
    orch = create_orchestrator(config)
    reg = getattr(orch, "_agent_registry", None)
    agent = reg.get(agent_id) if reg else None
    if agent is None:
        console.print(f"[red]Agent '{agent_id}' not found.[/red]")
        raise typer.Exit(1)
    console.print(Panel(
        f"[bold]ID:[/bold] {agent.agent_id}\n"
        f"[bold]Name:[/bold] {getattr(agent, 'agent_name', '—')}\n"
        f"[bold]Model:[/bold] {getattr(agent, 'model', '—')}\n"
        f"[bold]Requires review:[/bold] {getattr(agent, 'requires_review', False)}",
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
    from sovereign.integrations.connectors import (
        GitHubConnector, WeatherConnector, NotionConnector, GmailConnector,
    )
    connectors = [GitHubConnector(), WeatherConnector(), NotionConnector(), GmailConnector()]
    table = Table(title="Connectors")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("OAuth")
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
        )
    console.print(table)


@connector_app.command("sync")
def connector_sync(
    connector_id: str = typer.Argument(..., help="Connector ID to sync"),
) -> None:
    """Trigger an immediate sync for a connector."""
    from sovereign.integrations.connectors import (
        GitHubConnector, WeatherConnector, NotionConnector, GmailConnector,
    )
    from sovereign.integrations.connectors.sync_engine import SyncEngine

    all_connectors = {
        "github": GitHubConnector,
        "weather": WeatherConnector,
        "notion": NotionConnector,
        "gmail": GmailConnector,
    }
    if connector_id not in all_connectors:
        console.print(f"[red]Unknown connector: {connector_id}[/red]")
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
    from sovereign.integrations.connectors import (
        GitHubConnector, WeatherConnector, NotionConnector, GmailConnector,
    )
    connectors = [GitHubConnector(), WeatherConnector(), NotionConnector(), GmailConnector()]

    async def _run():
        table = Table(title="Connector Health")
        table.add_column("ID", style="cyan")
        table.add_column("Status")
        table.add_column("Records")
        for c in connectors:
            h = await c.health()
            sc = {"connected": "green", "beta": "yellow"}.get(h.status.value, "red")
            table.add_row(
                c.connector_id,
                f"[{sc}]{h.status.value}[/{sc}]",
                str(h.records_synced),
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


if __name__ == "__main__":
    app()
