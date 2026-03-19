"""
Rich-based output formatters for the stock screener.
"""
from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
import pandas as pd

console = Console()


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _fmt_num(v, decimals=2, prefix="", suffix="") -> str:
    if v is None:
        return "[dim]N/A[/dim]"
    try:
        return f"{prefix}{v:.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_large(v, currency="") -> str:
    if v is None:
        return "[dim]N/A[/dim]"
    prefix = f"{currency} " if currency else ""
    if abs(v) >= 1e12:
        return f"{prefix}{v/1e12:.2f}T"
    if abs(v) >= 1e9:
        return f"{prefix}{v/1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"{prefix}{v/1e6:.2f}M"
    return f"{prefix}{v:,.0f}"


def _colorize_pct(v, good_if_positive=True) -> str:
    if v is None:
        return "[dim]N/A[/dim]"
    color = "green" if (v >= 0) == good_if_positive else "red"
    return f"[{color}]{v:+.2f}%[/{color}]"


def _grade_color(grade: str) -> str:
    colors = {"A+": "bright_green", "A": "green", "B+": "cyan",
              "B": "blue", "C": "yellow", "D": "red", "N/A": "dim"}
    c = colors.get(grade, "white")
    return f"[{c}]{grade}[/{c}]"


def _recommendation_color(rec: str) -> str:
    rec = (rec or "").lower()
    if "strong_buy" in rec or "strongbuy" in rec:
        return "[bright_green]STRONG BUY[/bright_green]"
    if "buy" in rec:
        return "[green]BUY[/green]"
    if "hold" in rec or "neutral" in rec:
        return "[yellow]HOLD[/yellow]"
    if "underperform" in rec or "sell" in rec:
        return "[red]SELL[/red]"
    return f"[dim]{rec.upper()}[/dim]"


# ─────────────────────────────────────────────────────────────────
# Screener results table
# ─────────────────────────────────────────────────────────────────

def print_screen_results(results: list[dict], market: str = "US", preset: str = "") -> None:
    if not results:
        console.print(f"\n[yellow]No stocks passed the screening criteria.[/yellow]")
        return

    title = f"[bold]{market} Screen Results[/bold]"
    if preset:
        title += f"  [dim]preset: {preset}[/dim]"

    table = Table(
        title=title,
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        highlight=True,
        row_styles=["", "dim"],
    )

    table.add_column("#",         style="dim", width=3)
    table.add_column("Ticker",    style="bold yellow", min_width=8)
    table.add_column("Name",      min_width=20, max_width=30, no_wrap=True)
    table.add_column("Sector",    min_width=12, max_width=20, no_wrap=True)
    table.add_column("Mkt Cap",   justify="right", min_width=9)
    table.add_column("Price",     justify="right", min_width=8)
    table.add_column("P/E",       justify="right", min_width=6)
    table.add_column("P/B",       justify="right", min_width=6)
    table.add_column("EV/EBITDA", justify="right", min_width=9)
    table.add_column("ROE %",     justify="right", min_width=7)
    table.add_column("Net Mg%",   justify="right", min_width=8)
    table.add_column("D/E",       justify="right", min_width=6)
    table.add_column("Rev Grw%",  justify="right", min_width=9)
    table.add_column("Div Yld%",  justify="right", min_width=9)
    table.add_column("Score",     justify="right", min_width=6)

    for rank, s in enumerate(results, 1):
        currency = s.get("currency", "")
        table.add_row(
            str(rank),
            s.get("ticker", ""),
            s.get("name", "")[:30],
            s.get("sector", "N/A"),
            _fmt_large(s.get("market_cap"), currency),
            _fmt_num(s.get("price"), 2, suffix=f" {currency}"),
            _fmt_num(s.get("pe_trailing"), 1, suffix="x"),
            _fmt_num(s.get("pb"), 2, suffix="x"),
            _fmt_num(s.get("ev_ebitda"), 1, suffix="x"),
            _colorize_pct(s.get("roe"), good_if_positive=True),
            _colorize_pct(s.get("net_margin"), good_if_positive=True),
            _fmt_num(s.get("debt_equity"), 2, suffix="x"),
            _colorize_pct(s.get("revenue_growth"), good_if_positive=True),
            _colorize_pct(s.get("dividend_yield"), good_if_positive=True),
            f"[bold]{s.get('score', 0):.1f}[/bold]",
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]Showing {len(results)} stocks passing all criteria. Run [bold]analyze <TICKER>[/bold] for full report.[/dim]\n")


# ─────────────────────────────────────────────────────────────────
# Full fundamental analysis report
# ─────────────────────────────────────────────────────────────────

def print_fundamental_report(report: dict) -> None:
    if "error" in report:
        console.print(f"[red]Error fetching data for {report['ticker']}: {report['error']}[/red]")
        return

    ticker = report["ticker"]
    ov = report.get("overview", {})
    pi = report.get("price_info", {})
    val = report.get("valuation", {})
    prof = report.get("profitability", {})
    grw = report.get("growth", {})
    health = report.get("financial_health", {})
    cf = report.get("cashflow", {})
    div = report.get("dividends", {})
    ana = report.get("analyst", {})
    currency = ov.get("currency", "USD")

    console.print()
    console.rule(f"[bold cyan] FUNDAMENTAL ANALYSIS: {ticker} — {ov.get('name', ticker)} [/bold cyan]")

    # ---- Overview panel ----
    overview_lines = [
        f"[bold]Sector:[/bold]   {ov.get('sector', 'N/A')}",
        f"[bold]Industry:[/bold] {ov.get('industry', 'N/A')}",
        f"[bold]Country:[/bold]  {ov.get('country', 'N/A')}",
        f"[bold]Exchange:[/bold] {ov.get('exchange', 'N/A')}",
        f"[bold]Currency:[/bold] {currency}",
    ]
    if ov.get("description"):
        desc = ov["description"]
        overview_lines.append("")
        overview_lines.append(f"[italic]{desc[:500]}{'...' if len(desc) > 500 else ''}[/italic]")

    console.print(Panel("\n".join(overview_lines), title="[bold]Company Overview[/bold]", border_style="cyan"))

    # ---- Price & Market Summary ----
    price = pi.get("price")
    mc = pi.get("market_cap")
    ev = pi.get("enterprise_value")
    low52 = pi.get("52w_low")
    high52 = pi.get("52w_high")

    price_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    price_table.add_column("K", style="bold")
    price_table.add_column("V")
    price_table.add_column("K", style="bold")
    price_table.add_column("V")

    price_table.add_row(
        "Current Price",  _fmt_num(price, 2, suffix=f" {currency}"),
        "Market Cap",     _fmt_large(mc, currency),
    )
    price_table.add_row(
        "Enterprise Value", _fmt_large(ev, currency),
        "Beta",           _fmt_num(pi.get("beta"), 2, suffix="x"),
    )
    price_table.add_row(
        "52W Low",  _fmt_num(low52, 2, suffix=f" {currency}"),
        "52W High", _fmt_num(high52, 2, suffix=f" {currency}"),
    )
    price_table.add_row(
        "% from 52W Low",  _colorize_pct(pi.get("pct_from_low"), True),
        "% from 52W High", _colorize_pct(pi.get("pct_from_high"), True),
    )
    price_table.add_row(
        "Avg Volume", _fmt_large(pi.get("avg_volume")),
        "Float",      _fmt_large(ov.get("float_shares")),
    )

    console.print(Panel(price_table, title="[bold]Price & Market Data[/bold]", border_style="blue"))

    # ---- Valuation ----
    val_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    val_table.add_column("Metric", style="bold")
    val_table.add_column("Value", justify="right")
    val_table.add_column("Metric", style="bold")
    val_table.add_column("Value", justify="right")

    val_table.add_row("P/E (Trailing)", _fmt_num(val.get("pe_trailing"), 2, suffix="x"),
                      "P/E (Forward)",  _fmt_num(val.get("pe_forward"), 2, suffix="x"))
    val_table.add_row("Price/Book",     _fmt_num(val.get("pb"), 2, suffix="x"),
                      "Price/Sales",    _fmt_num(val.get("ps_trailing"), 2, suffix="x"))
    val_table.add_row("EV/EBITDA",      _fmt_num(val.get("ev_ebitda"), 2, suffix="x"),
                      "EV/Revenue",     _fmt_num(val.get("ev_revenue"), 2, suffix="x"))
    val_table.add_row("PEG Ratio",      _fmt_num(val.get("peg"), 2, suffix="x"),
                      "", "")

    console.print(Panel(val_table, title="[bold]Valuation Multiples[/bold]", border_style="magenta"))

    # ---- Profitability ----
    grades = prof.get("grades", {})
    prof_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    prof_table.add_column("Metric", style="bold")
    prof_table.add_column("Value", justify="right")
    prof_table.add_column("Grade", justify="center")
    prof_table.add_column("Metric", style="bold")
    prof_table.add_column("Value", justify="right")
    prof_table.add_column("Grade", justify="center")

    prof_table.add_row(
        "Gross Margin",     _colorize_pct(prof.get("gross_margin"), True), "",
        "Operating Margin", _colorize_pct(prof.get("operating_margin"), True), "",
    )
    prof_table.add_row(
        "Net Margin", _colorize_pct(prof.get("net_margin"), True), _grade_color(grades.get("margin", "N/A")),
        "EBITDA",     _fmt_large(prof.get("ebitda"), currency), "",
    )
    prof_table.add_row(
        "ROE",  _colorize_pct(prof.get("roe"), True), _grade_color(grades.get("roe", "N/A")),
        "ROA",  _colorize_pct(prof.get("roa"), True), _grade_color(grades.get("roa", "N/A")),
    )

    console.print(Panel(prof_table, title="[bold]Profitability[/bold]", border_style="green"))

    # ---- Growth ----
    grw_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    grw_table.add_column("Metric", style="bold")
    grw_table.add_column("Value", justify="right")
    grw_table.add_column("Metric", style="bold")
    grw_table.add_column("Value", justify="right")

    grw_table.add_row(
        "Revenue Growth (YoY)", _colorize_pct(grw.get("revenue_growth"), True),
        "Earnings Growth (YoY)", _colorize_pct(grw.get("earnings_growth"), True),
    )
    grw_table.add_row(
        "EPS Growth (YoY)", _colorize_pct(grw.get("eps_growth"), True),
        "", "",
    )
    grw_table.add_row(
        "EPS (Trailing)", _fmt_num(grw.get("eps_trailing"), 2, suffix=f" {currency}"),
        "EPS (Forward)",  _fmt_num(grw.get("eps_forward"), 2, suffix=f" {currency}"),
    )

    # Revenue history mini-table
    rev_h = grw.get("revenue_history", {})
    if rev_h:
        rev_rows = "  |  ".join(
            f"[bold]{y}:[/bold] {_fmt_large(v, currency)}"
            for y, v in sorted(rev_h.items())[-4:]
        )
        grw_table.add_row("Revenue History", rev_rows, "", "")

    ni_h = grw.get("net_income_history", {})
    if ni_h:
        ni_rows = "  |  ".join(
            f"[bold]{y}:[/bold] {_fmt_large(v, currency)}"
            for y, v in sorted(ni_h.items())[-4:]
        )
        grw_table.add_row("Net Income History", ni_rows, "", "")

    console.print(Panel(grw_table, title="[bold]Growth[/bold]", border_style="yellow"))

    # ---- Financial Health ----
    h_grades = health.get("grades", {})
    health_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    health_table.add_column("Metric", style="bold")
    health_table.add_column("Value", justify="right")
    health_table.add_column("Grade", justify="center")
    health_table.add_column("Metric", style="bold")
    health_table.add_column("Value", justify="right")
    health_table.add_column("Grade", justify="center")

    health_table.add_row(
        "Current Ratio",  _fmt_num(health.get("current_ratio"), 2, suffix="x"), _grade_color(h_grades.get("liquidity", "N/A")),
        "Quick Ratio",    _fmt_num(health.get("quick_ratio"), 2, suffix="x"), "",
    )
    health_table.add_row(
        "Debt/Equity",    _fmt_num(health.get("debt_equity"), 2, suffix="x"), _grade_color(h_grades.get("debt", "N/A")),
        "Total Cash",     _fmt_large(health.get("total_cash"), currency), "",
    )
    health_table.add_row(
        "Total Debt",     _fmt_large(health.get("total_debt"), currency), "",
        "", "", "",
    )

    debt_h = health.get("debt_history", {})
    if debt_h:
        debt_rows = "  |  ".join(
            f"[bold]{y}:[/bold] {_fmt_large(v, currency)}"
            for y, v in sorted(debt_h.items())[-4:]
        )
        health_table.add_row("Debt History", debt_rows, "", "", "", "")

    console.print(Panel(health_table, title="[bold]Financial Health[/bold]", border_style="red"))

    # ---- Cash Flow ----
    cf_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    cf_table.add_column("Metric", style="bold")
    cf_table.add_column("Value", justify="right")
    cf_table.add_column("Metric", style="bold")
    cf_table.add_column("Value", justify="right")

    cf_table.add_row(
        "Operating Cash Flow", _fmt_large(cf.get("operating_cf"), currency),
        "Capital Expenditure",  _fmt_large(cf.get("capex"), currency),
    )
    cf_table.add_row(
        "Free Cash Flow",  _fmt_large(cf.get("fcf"), currency),
        "FCF Yield",       _colorize_pct(cf.get("fcf_yield"), True),
    )

    fcf_h = cf.get("fcf_history", {})
    if fcf_h:
        fcf_rows = "  |  ".join(
            f"[bold]{y}:[/bold] {_fmt_large(v, currency)}"
            for y, v in sorted(fcf_h.items())[-4:]
        )
        cf_table.add_row("FCF History", fcf_rows, "", "")

    console.print(Panel(cf_table, title="[bold]Cash Flow[/bold]", border_style="bright_blue"))

    # ---- Dividends ----
    if div.get("yield") or div.get("rate"):
        div_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        div_table.add_column("Metric", style="bold")
        div_table.add_column("Value", justify="right")
        div_table.add_column("Metric", style="bold")
        div_table.add_column("Value", justify="right")

        div_table.add_row(
            "Dividend Yield",  _colorize_pct(div.get("yield"), True),
            "Dividend Rate",   _fmt_num(div.get("rate"), 2, suffix=f" {currency}"),
        )
        div_table.add_row(
            "Payout Ratio",    _colorize_pct(div.get("payout_ratio"), True),
            "Ex-Dividend Date", str(div.get("ex_date", "N/A")),
        )

        console.print(Panel(div_table, title="[bold]Dividends[/bold]", border_style="bright_yellow"))

    # ---- Analyst Consensus ----
    upside = ana.get("upside_pct")
    analyst_text = [
        f"[bold]Consensus:[/bold]  {_recommendation_color(ana.get('recommendation', 'N/A'))}",
        f"[bold]# Analysts:[/bold] {ana.get('analyst_count', 'N/A')}",
        f"[bold]Price Target:[/bold] {_fmt_num(ana.get('target_price'), 2, suffix=f' {currency}')}",
        f"[bold]Upside/Downside:[/bold] {_colorize_pct(upside, True) if upside is not None else '[dim]N/A[/dim]'}",
    ]
    console.print(Panel("\n".join(analyst_text), title="[bold]Analyst Consensus[/bold]", border_style="bright_cyan"))

    # ---- Strengths & Risks ----
    strengths = report.get("strengths", [])
    risks = report.get("risks", [])

    if strengths:
        s_text = "\n".join(f"[green]✔ {s}[/green]" for s in strengths)
        console.print(Panel(s_text, title="[bold green]Strengths[/bold green]", border_style="green"))

    if risks:
        r_text = "\n".join(f"[red]✘ {r}[/red]" for r in risks)
        console.print(Panel(r_text, title="[bold red]Risks & Concerns[/bold red]", border_style="red"))

    # ---- Score ----
    score = report.get("score", 0)
    score_color = "bright_green" if score >= 70 else "yellow" if score >= 50 else "red"
    console.print(
        Panel(
            f"[{score_color}][bold]{score:.1f} / 100[/bold][/{score_color}]\n"
            "[dim]Composite quality/value score (higher = better)[/dim]",
            title="[bold]Overall Score[/bold]",
            border_style=score_color,
        )
    )

    console.print()


def make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("•"),
        TextColumn("{task.fields[ticker]}"),
        TimeElapsedColumn(),
        console=console,
    )
