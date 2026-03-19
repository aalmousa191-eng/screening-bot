#!/usr/bin/env python3
"""
Stock Screening Bot — CLI entry point.

Usage examples:
  python main.py                          # interactive menu
  python main.py run --preset oversold    # US oversold stocks
  python main.py run --preset breakout --market tasi
  python main.py run --preset trend --market both --limit 30
  python main.py list                     # show all presets
"""

import sys
import click
from rich.console import Console
from rich.prompt import Prompt, IntPrompt

from screener.presets import PRESETS
from screener.scanner import run_screen
from screener.display import render_results, render_preset_list

console = Console()

MARKET_CHOICES = click.Choice(["us", "tasi", "both"], case_sensitive=False)


# ──────────────────────────────────────────────────────────────
# CLI Group
# ──────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Stock Screening Bot — US & TASI market screener."""
    if ctx.invoked_subcommand is None:
        _interactive_menu()


# ──────────────────────────────────────────────────────────────
# run command
# ──────────────────────────────────────────────────────────────

@cli.command()
@click.option(
    "--preset", "-p",
    type=click.Choice(list(PRESETS.keys()), case_sensitive=False),
    required=True,
    help="Screening preset to run.",
)
@click.option(
    "--market", "-m",
    type=MARKET_CHOICES,
    default="us",
    show_default=True,
    help="Market to screen: us, tasi, or both.",
)
@click.option(
    "--limit", "-l",
    default=50,
    show_default=True,
    help="Maximum number of results.",
)
def run(preset, market, limit):
    """Run a screening preset and display results."""
    _do_screen(preset, market, limit)


# ──────────────────────────────────────────────────────────────
# list command
# ──────────────────────────────────────────────────────────────

@cli.command(name="list")
def list_presets():
    """List all available screening presets."""
    render_preset_list(PRESETS)


# ──────────────────────────────────────────────────────────────
# Shared helper
# ──────────────────────────────────────────────────────────────

def _do_screen(preset_key: str, market: str, limit: int) -> None:
    preset = PRESETS[preset_key.lower()]
    console.print(
        f"\n[bold cyan]Screening[/bold cyan] "
        f"[bold]{preset['label']}[/bold] on [bold]{market.upper()}[/bold] "
        f"(max {limit} results)…\n"
    )
    try:
        df = run_screen(preset, market=market.lower(), limit=limit)
        render_results(df, preset, market)
    except RuntimeError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {e}")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────
# Interactive Menu (when run with no arguments)
# ──────────────────────────────────────────────────────────────

def _interactive_menu() -> None:
    console.rule("[bold cyan]Stock Screening Bot[/bold cyan]")
    console.print()

    # Show presets
    render_preset_list(PRESETS)
    console.print()

    preset_keys = list(PRESETS.keys())
    preset_choice = Prompt.ask(
        "[bold]Choose a preset[/bold]",
        choices=preset_keys,
        default="oversold",
    )

    market_choice = Prompt.ask(
        "[bold]Market[/bold]",
        choices=["us", "tasi", "both"],
        default="us",
    )

    limit_choice = IntPrompt.ask(
        "[bold]Max results[/bold]",
        default=30,
    )

    console.print()
    _do_screen(preset_choice, market_choice, limit_choice)


if __name__ == "__main__":
    cli()
