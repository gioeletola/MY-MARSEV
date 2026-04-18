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


if __name__ == "__main__":
    app()
