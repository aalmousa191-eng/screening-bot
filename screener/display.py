"""
Rich terminal display for screener results.
"""

from __future__ import annotations

import pandas as pd
from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text
from rich.panel import Panel

console = Console()

# Human-friendly column labels
COLUMN_LABELS = {
    "ticker": "Ticker",
    "name": "Ticker",
    "description": "Company",
    "close": "Price",
    "change": "Chg%",
    "volume": "Volume",
    "average_volume_10d_calc": "Avg Vol (10d)",
    "market_cap_basic": "Market Cap",
    "RSI": "RSI",
    "EMA20": "EMA20",
    "EMA50": "EMA50",
    "EMA200": "EMA200",
    "Relative.Volume": "Rel. Vol",
    "MACD.macd": "MACD",
    "MACD.signal": "MACD Signal",
    "High.All": "52W High",
    "Low.All": "52W Low",
    "price_earnings_ttm": "P/E (TTM)",
    "earnings_per_share_basic_ttm": "EPS (TTM)",
    "market": "Market",
}


def _fmt_number(val, prefix="", suffix="", decimals=2) -> str:
    if pd.isna(val):
        return "-"
    if abs(val) >= 1_000_000_000:
        return f"{prefix}{val/1_000_000_000:.1f}B{suffix}"
    if abs(val) >= 1_000_000:
        return f"{prefix}{val/1_000_000:.1f}M{suffix}"
    if abs(val) >= 1_000:
        return f"{prefix}{val/1_000:.1f}K{suffix}"
    return f"{prefix}{val:.{decimals}f}{suffix}"


def _fmt_cell(col_name: str, val) -> Text:
    if pd.isna(val):
        return Text("-", style="dim")

    if col_name == "change":
        pct = float(val)
        color = "green" if pct > 0 else ("red" if pct < 0 else "white")
        sign = "+" if pct > 0 else ""
        return Text(f"{sign}{pct:.2f}%", style=color)

    if col_name == "RSI":
        rsi = float(val)
        if rsi <= 30:
            color = "bright_green"
        elif rsi >= 70:
            color = "bright_red"
        else:
            color = "white"
        return Text(f"{rsi:.1f}", style=color)

    if col_name in ("MACD.macd", "MACD.signal"):
        v = float(val)
        color = "green" if v > 0 else "red"
        return Text(f"{v:.3f}", style=color)

    if col_name == "Relative.Volume":
        rv = float(val)
        color = "bright_yellow" if rv >= 2 else "white"
        return Text(f"{rv:.2f}x", style=color)

    if col_name == "market_cap_basic":
        return Text(_fmt_number(val, prefix="$"), style="cyan")

    if col_name in ("volume", "average_volume_10d_calc"):
        return Text(_fmt_number(val), style="cyan")

    if col_name == "close":
        return Text(f"{float(val):,.2f}", style="bold white")

    if col_name in ("EMA20", "EMA50", "EMA200", "High.All", "Low.All"):
        return Text(f"{float(val):,.2f}", style="dim")

    if col_name in ("price_earnings_ttm", "earnings_per_share_basic_ttm"):
        v = float(val)
        color = "green" if v > 0 else "red"
        return Text(f"{v:.2f}", style=color)

    if col_name == "market":
        color = "blue" if str(val) == "US" else "magenta"
        return Text(str(val), style=f"bold {color}")

    return Text(str(val))


def render_results(df: pd.DataFrame, preset: dict, market: str) -> None:
    if df.empty:
        console.print(
            Panel(
                "[yellow]No stocks matched the criteria.[/yellow]",
                title=f"[bold]{preset['label']}[/bold]",
                border_style="yellow",
            )
        )
        return

    title = f"[bold green]{preset['label']}[/bold green]  "
    title += f"[dim]{preset['description']}[/dim]  "
    title += f"[bold]Market: {market.upper()}[/bold]  "
    title += f"[dim]{len(df)} result(s)[/dim]"

    table = Table(
        title=title,
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        header_style="bold cyan",
        title_justify="left",
    )

    # Determine which columns are present in the dataframe
    display_cols = [c for c in df.columns if c != "ticker"]

    for col_name in display_cols:
        label = COLUMN_LABELS.get(col_name, col_name)
        justify = "right" if col_name not in ("name", "description", "market") else "left"
        table.add_column(label, justify=justify)

    for _, row in df.iterrows():
        cells = [_fmt_cell(c, row[c]) for c in display_cols]
        table.add_row(*cells)

    console.print(table)


def render_preset_list(presets: dict) -> None:
    table = Table(
        title="Available Screening Presets",
        box=box.SIMPLE_HEAVY,
        header_style="bold cyan",
    )
    table.add_column("Key", style="bold yellow")
    table.add_column("Name", style="bold")
    table.add_column("Description")

    for key, preset in presets.items():
        table.add_row(key, preset["label"], preset["description"])

    console.print(table)
