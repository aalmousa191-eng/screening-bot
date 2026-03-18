#!/usr/bin/env python3
"""
Stock Screener & Fundamental Analyzer
Supports: US (via Polygon.io + Yahoo Finance) | TASI (via Yahoo Finance .SR)

Usage:
    python main.py screen us [OPTIONS]
    python main.py screen tasi [OPTIONS]
    python main.py screen both [OPTIONS]
    python main.py analyze <TICKER> [OPTIONS]
    python main.py criteria
"""
from __future__ import annotations

import sys
import json
import csv
import os
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.prompt import Confirm

console = Console()


# ─────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """
    \b
    ╔══════════════════════════════════════════╗
    ║     Stock Screener & Analyzer v1.0       ║
    ║   Markets: US (Polygon.io) + TASI (YF)   ║
    ╚══════════════════════════════════════════╝
    """
    pass


# ─────────────────────────────────────────────────────────────────
# `screen` command group
# ─────────────────────────────────────────────────────────────────

@cli.group()
def screen():
    """Screen stocks using fundamental criteria."""
    pass


COMMON_SCREEN_OPTIONS = [
    click.option("--preset", "-p",
                 type=click.Choice(["value", "growth", "dividend", "quality"]),
                 default=None,
                 help="Use a named screening preset (overrides default criteria)."),
    click.option("--max-tickers", "-n", default=None, type=int,
                 help="Max number of tickers to evaluate (speeds up run)."),
    click.option("--export", "-e", default=None, metavar="FILE.csv",
                 help="Export results to a CSV file."),
    click.option("--criteria", "-c", default=None, metavar="JSON",
                 help='Override criteria as JSON, e.g. \'{"max_pe": 20, "min_roe": 15}\''),
]


def add_options(options):
    def decorator(f):
        for option in reversed(options):
            f = option(f)
        return f
    return decorator


@screen.command("us")
@add_options(COMMON_SCREEN_OPTIONS)
@click.option("--max-tickers", "-n", default=300, type=int,
              help="Max US tickers to evaluate (default 300).")
def screen_us(preset, max_tickers, export, criteria):
    """Screen US stocks (NASDAQ + NYSE) using Polygon.io + Yahoo Finance."""
    from screener.us_screener import screen_us as _screen
    from utils.formatters import print_screen_results, make_progress, console

    extra_criteria = {}
    if criteria:
        try:
            extra_criteria = json.loads(criteria)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON criteria: {e}[/red]")
            sys.exit(1)

    console.print(f"\n[bold cyan]Screening US stocks[/bold cyan] "
                  f"(up to [bold]{max_tickers}[/bold] tickers"
                  f"{f', preset: [bold]{preset}[/bold]' if preset else ''})\n")

    from config.settings import POLYGON_API_KEY
    if not POLYGON_API_KEY:
        console.print("[red]⚠  POLYGON_API_KEY not set. Create a .env file with your key.[/red]")
        console.print("[dim]Copy .env.example → .env and add your key.[/dim]\n")
        sys.exit(1)

    results = []
    with make_progress() as progress:
        task = progress.add_task("Screening US stocks...", total=max_tickers, ticker="starting...")

        def cb(current, total, ticker):
            progress.update(task, completed=current, ticker=ticker)

        results = _screen(
            criteria=extra_criteria or None,
            preset=preset,
            max_tickers=max_tickers,
            progress_cb=cb,
        )

    print_screen_results(results, market="US", preset=preset or "default")

    if export:
        _export_csv(results, export)
        console.print(f"[green]Results exported to[/green] [bold]{export}[/bold]")


@screen.command("tasi")
@add_options(COMMON_SCREEN_OPTIONS)
@click.option("--max-tickers", "-n", default=None, type=int,
              help="Max TASI tickers to evaluate (default: all).")
def screen_tasi(preset, max_tickers, export, criteria):
    """Screen Saudi (TASI/Tadawul) stocks using Yahoo Finance."""
    from screener.tasi_screener import screen_tasi as _screen
    from utils.formatters import print_screen_results, make_progress, console
    from data.tasi_client import get_tasi_tickers

    extra_criteria = {}
    if criteria:
        try:
            extra_criteria = json.loads(criteria)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON criteria: {e}[/red]")
            sys.exit(1)

    total_universe = len(get_tasi_tickers(use_static=True))
    cap = max_tickers or total_universe

    console.print(f"\n[bold green]Screening TASI stocks[/bold green] "
                  f"(up to [bold]{cap}[/bold] tickers"
                  f"{f', preset: [bold]{preset}[/bold]' if preset else ''})\n")

    results = []
    with make_progress() as progress:
        task = progress.add_task("Screening TASI stocks...", total=cap, ticker="starting...")

        def cb(current, total, ticker):
            progress.update(task, completed=current, ticker=ticker)

        results = _screen(
            criteria=extra_criteria or None,
            preset=preset,
            max_tickers=max_tickers,
            progress_cb=cb,
        )

    print_screen_results(results, market="TASI", preset=preset or "default")

    if export:
        _export_csv(results, export)
        console.print(f"[green]Results exported to[/green] [bold]{export}[/bold]")


@screen.command("both")
@add_options(COMMON_SCREEN_OPTIONS)
@click.option("--us-max", default=200, type=int, help="Max US tickers (default 200).")
@click.option("--tasi-max", default=None, type=int, help="Max TASI tickers (default: all).")
def screen_both(preset, max_tickers, export, criteria, us_max, tasi_max):
    """Screen both US and TASI stocks simultaneously."""
    from screener.us_screener import screen_us as _screen_us
    from screener.tasi_screener import screen_tasi as _screen_tasi
    from utils.formatters import print_screen_results, make_progress, console
    from config.settings import POLYGON_API_KEY

    extra_criteria = {}
    if criteria:
        try:
            extra_criteria = json.loads(criteria)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON criteria: {e}[/red]")
            sys.exit(1)

    if not POLYGON_API_KEY:
        console.print("[yellow]⚠  POLYGON_API_KEY not set – skipping US screening.[/yellow]\n")
        us_results = []
    else:
        console.print(f"\n[bold cyan]── US Screen ──[/bold cyan]")
        with make_progress() as progress:
            task = progress.add_task("Screening US...", total=us_max, ticker="starting...")
            def us_cb(c, t, tick):
                progress.update(task, completed=c, ticker=tick)
            us_results = _screen_us(criteria=extra_criteria or None, preset=preset,
                                    max_tickers=us_max, progress_cb=us_cb)

        print_screen_results(us_results, market="US", preset=preset or "default")

    console.print(f"\n[bold green]── TASI Screen ──[/bold green]")
    with make_progress() as progress:
        task = progress.add_task("Screening TASI...", total=tasi_max or 150, ticker="starting...")
        def tasi_cb(c, t, tick):
            progress.update(task, completed=c, ticker=tick)
        tasi_results = _screen_tasi(criteria=extra_criteria or None, preset=preset,
                                    max_tickers=tasi_max, progress_cb=tasi_cb)

    print_screen_results(tasi_results, market="TASI", preset=preset or "default")

    if export:
        all_results = us_results + tasi_results
        _export_csv(all_results, export)
        console.print(f"[green]Combined results exported to[/green] [bold]{export}[/bold]")


# ─────────────────────────────────────────────────────────────────
# `analyze` command
# ─────────────────────────────────────────────────────────────────

@cli.command("analyze")
@click.argument("ticker")
@click.option("--export", "-e", default=None, metavar="FILE.json",
              help="Export the report as JSON.")
def analyze(ticker, export):
    """
    Run a full fundamental analysis on TICKER.

    \b
    Examples:
        python main.py analyze AAPL
        python main.py analyze 2222.SR      # Saudi Aramco
        python main.py analyze MSFT --export msft_report.json
    """
    from analysis.fundamental import build_report
    from utils.formatters import print_fundamental_report

    ticker = ticker.upper()
    console.print(f"\n[bold]Fetching fundamental data for [cyan]{ticker}[/cyan]...[/bold]\n")

    report = build_report(ticker)
    print_fundamental_report(report)

    if export:
        with open(export, "w") as f:
            json.dump(report, f, indent=2, default=str)
        console.print(f"[green]Report exported to[/green] [bold]{export}[/bold]")


# ─────────────────────────────────────────────────────────────────
# `criteria` command – show current active criteria
# ─────────────────────────────────────────────────────────────────

@cli.command("criteria")
@click.option("--preset", "-p",
              type=click.Choice(["value", "growth", "dividend", "quality"]),
              default=None,
              help="Show criteria for a specific preset.")
def show_criteria(preset):
    """Display the active screening criteria (or a named preset)."""
    from config.settings import SCREENING_CRITERIA, PRESETS

    if preset:
        crit = dict(SCREENING_CRITERIA)
        crit.update(PRESETS[preset])
        title = f"Preset: [bold]{preset.upper()}[/bold]"
    else:
        crit = SCREENING_CRITERIA
        title = "Default Screening Criteria"

    table = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Parameter", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Description")

    descriptions = {
        "max_pe":             ("Max P/E (trailing)", "Price-to-Earnings – lower = cheaper"),
        "max_pb":             ("Max P/B", "Price-to-Book"),
        "max_ps":             ("Max P/S", "Price-to-Sales"),
        "max_ev_ebitda":      ("Max EV/EBITDA", "Enterprise multiple"),
        "max_peg":            ("Max PEG", "P/E to growth ratio"),
        "min_roe":            ("Min ROE %", "Return on Equity"),
        "min_roa":            ("Min ROA %", "Return on Assets"),
        "min_gross_margin":   ("Min Gross Margin %", "Revenue minus COGS / Revenue"),
        "min_operating_margin":("Min Oper. Margin %", "Operating income / Revenue"),
        "min_net_margin":     ("Min Net Margin %", "Net income / Revenue"),
        "min_revenue_growth": ("Min Rev. Growth %", "YoY revenue growth"),
        "min_eps_growth":     ("Min EPS Growth %", "YoY EPS growth"),
        "max_debt_equity":    ("Max Debt/Equity", "Total debt / shareholders equity"),
        "min_current_ratio":  ("Min Current Ratio", "Current assets / current liabilities"),
        "min_quick_ratio":    ("Min Quick Ratio", "(Current assets – inventory) / liabilities"),
        "min_dividend_yield": ("Min Dividend Yield %", "Annual dividends / price"),
        "min_market_cap":     ("Min Market Cap", "Minimum market capitalisation"),
        "max_market_cap":     ("Max Market Cap", "Maximum market capitalisation"),
        "min_52w_from_low":   ("Min % above 52W Low", "Momentum: distance from 52-week low"),
        "max_52w_from_high":  ("Max % below 52W High", "Must be within N% of 52-week high"),
    }

    for key, value in crit.items():
        label, desc = descriptions.get(key, (key, ""))
        val_str = "[dim]disabled[/dim]" if value is None else f"[bold]{value}[/bold]"
        table.add_row(label, val_str, desc)

    console.print()
    console.print(table)
    console.print()
    console.print("[dim]To override criteria at runtime use: [bold]--criteria '{\"max_pe\": 20}'[/bold][/dim]")
    console.print("[dim]Edit [bold]config/settings.py[/bold] to change defaults permanently.[/dim]\n")


# ─────────────────────────────────────────────────────────────────
# `tickers` helper – list TASI tickers
# ─────────────────────────────────────────────────────────────────

@cli.command("tickers")
@click.option("--market", "-m", type=click.Choice(["tasi", "us"]), default="tasi")
@click.option("--limit", "-l", default=50, type=int)
def list_tickers(market, limit):
    """List available tickers for a market."""
    if market == "tasi":
        from data.tasi_client import get_tasi_tickers
        tickers = get_tasi_tickers(use_static=True)
    else:
        from data.polygon_client import get_all_us_tickers
        from config.settings import POLYGON_API_KEY
        if not POLYGON_API_KEY:
            console.print("[red]POLYGON_API_KEY not set.[/red]")
            return
        tickers = get_all_us_tickers(max_tickers=limit)

    tickers = tickers[:limit]
    console.print(f"\n[bold]{market.upper()} Tickers[/bold] (showing {len(tickers)}):\n")
    cols = [tickers[i:i+8] for i in range(0, len(tickers), 8)]
    for row in cols:
        console.print("  " + "  ".join(f"[yellow]{t:<10}[/yellow]" for t in row))
    console.print()


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _export_csv(results: list[dict], filepath: str) -> None:
    if not results:
        return
    keys = [k for k in results[0].keys() if not isinstance(results[0][k], dict)]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)


# ─────────────────────────────────────────────────────────────────
# Entry
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
