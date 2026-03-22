"""Claude Opus AI analyst for stock reports and morning briefs."""
import logging
from datetime import datetime

import anthropic
import pytz

from analysis.technical import TechnicalSnapshot, format_technical_report
from analysis.fundamental import FundamentalSnapshot, format_fundamental_report
from analysis.screener import ScreenerResult
from analysis.market_movers import MarketOverview
from config import config

logger = logging.getLogger(__name__)
ET = pytz.timezone("America/New_York")

_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
MODEL = "claude-opus-4-6"


async def _stream_response(system: str, user: str) -> str:
    """Call Claude with adaptive thinking and stream to collect full text."""
    full_text = ""
    async with _client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        async for text in stream.text_stream:
            full_text += text
    return full_text.strip()


# ── Stock Analysis ────────────────────────────────────────────────────────────

async def analyze_stock(
    ticker: str,
    tech: TechnicalSnapshot,
    fund: FundamentalSnapshot,
    ticker_details: dict,
) -> str:
    """Generate a full professional equity analysis for a given ticker."""
    system = (
        "You are a senior equity analyst at a top-tier investment bank. "
        "Produce a concise, professional analysis in the style of a Bloomberg / FactSet research note. "
        "Use plain text (no markdown headers, but use line breaks). "
        "Be specific with numbers and give a clear investment thesis."
    )

    # Serialise technical snapshot
    tech_summary = (
        f"Ticker: {ticker}\n"
        f"Price: ${tech.price:.2f}  Day change: {tech.change_pct:+.2f}%\n"
        f"Trend: {tech.trend_signal}  Overall signal: {tech.overall_signal}  Technical score: {tech.score}/100\n"
        f"SMA20: {'${:.2f}'.format(tech.sma20) if tech.sma20 else 'N/A'}  "
        f"SMA50: {'${:.2f}'.format(tech.sma50) if tech.sma50 else 'N/A'}  "
        f"SMA200: {'${:.2f}'.format(tech.sma200) if tech.sma200 else 'N/A'}\n"
        f"RSI(14): {f'{tech.rsi:.1f}' if tech.rsi is not None else 'N/A'}  "
        f"MACD: {f'{tech.macd:.4f}' if tech.macd is not None else 'N/A'}  "
        f"Hist: {f'{tech.macd_hist:+.4f}' if tech.macd_hist is not None else 'N/A'}\n"
        f"Bollinger %B: {f'{tech.bb_pct:.2f}' if tech.bb_pct is not None else 'N/A'}  "
        f"ATR: {f'{tech.atr:.2f}' if tech.atr is not None else 'N/A'} "
        f"({f'{tech.atr_pct:.1f}' if tech.atr_pct is not None else 'N/A'}%)\n"
        f"Volume ratio (vs 20d avg): {f'{tech.volume_ratio:.2f}' if tech.volume_ratio is not None else 'N/A'}x\n"
        f"Stochastic K/D: {f'{tech.stoch_k:.1f}' if tech.stoch_k is not None else 'N/A'}"
        f"/{f'{tech.stoch_d:.1f}' if tech.stoch_d is not None else 'N/A'}\n"
        f"52-week range: ${f'{tech.week52_low:.2f}' if tech.week52_low is not None else 'N/A'} "
        f"– ${f'{tech.week52_high:.2f}' if tech.week52_high is not None else 'N/A'}  "
        f"({f'{tech.pct_from_52w_high:+.1f}' if tech.pct_from_52w_high is not None else 'N/A'}% from 52w high)"
    )

    fund_summary = (
        f"Company: {fund.company_name}  |  Industry: {fund.industry or fund.sector}\n"
        f"Market Cap: {_fmt_large(fund.market_cap)}  |  EV: {_fmt_large(fund.ev)}\n"
        f"Revenue: {_fmt_large(fund.revenue)} "
        f"(YoY growth: {f'{fund.revenue_growth_yoy:+.1f}' if fund.revenue_growth_yoy is not None else 'N/A'}%)\n"
        f"Net Income: {_fmt_large(fund.net_income)}  |  "
        f"Net Margin: {f'{fund.net_margin:.1f}' if fund.net_margin is not None else 'N/A'}%\n"
        f"EBITDA: {_fmt_large(fund.ebitda)}  |  FCF: {_fmt_large(fund.free_cash_flow)}\n"
        f"Gross Margin: {f'{fund.gross_margin:.1f}' if fund.gross_margin is not None else 'N/A'}%  "
        f"Operating Margin: {f'{fund.operating_margin:.1f}' if fund.operating_margin is not None else 'N/A'}%\n"
        f"P/E: {f'{fund.pe_ratio:.1f}' if fund.pe_ratio is not None else 'N/A'}x  "
        f"P/S: {f'{fund.ps_ratio:.1f}' if fund.ps_ratio is not None else 'N/A'}x  "
        f"P/B: {f'{fund.pb_ratio:.1f}' if fund.pb_ratio is not None else 'N/A'}x  "
        f"EV/EBITDA: {f'{fund.ev_ebitda:.1f}' if fund.ev_ebitda is not None else 'N/A'}x\n"
        f"Debt/Equity: {f'{fund.debt_to_equity:.2f}' if fund.debt_to_equity is not None else 'N/A'}  "
        f"Current Ratio: {f'{fund.current_ratio:.2f}' if fund.current_ratio is not None else 'N/A'}  "
        f"ROE: {f'{fund.roe:.1f}' if fund.roe is not None else 'N/A'}%  "
        f"ROA: {f'{fund.roa:.1f}' if fund.roa is not None else 'N/A'}%\n"
        f"Valuation signal: {fund.valuation_signal}  Quality score: {fund.quality_score}/100"
    )

    desc = fund.description[:300] if fund.description else "N/A"

    user_prompt = f"""Provide a professional equity analysis for {ticker} ({fund.company_name}).

BUSINESS OVERVIEW:
{desc}

TECHNICAL DATA:
{tech_summary}

FUNDAMENTAL DATA:
{fund_summary}

Please provide:
1. INVESTMENT THESIS (2-3 sentences): Clear bull/bear case
2. TECHNICAL OUTLOOK: Key price levels, trend assessment, momentum commentary
3. FUNDAMENTAL ASSESSMENT: Valuation vs. peers, growth quality, balance sheet health
4. RISKS: Top 2-3 risks to watch
5. VERDICT: Buy / Hold / Sell with target price range if possible

Keep it under 600 words. Be specific, data-driven, and direct."""

    try:
        return await _stream_response(system, user_prompt)
    except Exception as e:
        logger.error("Claude analysis failed for %s: %s", ticker, e)
        return f"AI analysis unavailable: {e}"


# ── Morning Brief ─────────────────────────────────────────────────────────────

async def generate_morning_brief(
    overview: MarketOverview,
    top_stocks: list[ScreenerResult],
    date_str: str = "",
) -> str:
    """Generate the full morning market brief using Claude."""
    if not date_str:
        date_str = datetime.now(ET).strftime("%A, %B %d, %Y")

    system = (
        "You are a senior market strategist writing a pre-market morning brief "
        "for professional traders and investors. Write in a confident, concise, "
        "institutional voice — like a morning note from Goldman Sachs or JPMorgan. "
        "Use plain text, structured sections, no markdown syntax."
    )

    # Summarise market data
    index_lines = "\n".join(
        f"  {idx['name']}: ${idx['price']:.2f} ({idx['change_pct']:+.2f}%)"
        for idx in overview.indices
    )
    sector_lines = "\n".join(
        f"  {sec['name']}: {sec['change_pct']:+.2f}%"
        for sec in overview.sectors
    )
    gainer_lines = "\n".join(
        f"  {m.ticker}: ${m.price:.2f} (+{m.change_pct:.2f}%)"
        for m in overview.gainers[:5]
    )
    loser_lines = "\n".join(
        f"  {m.ticker}: ${m.price:.2f} ({m.change_pct:.2f}%)"
        for m in overview.losers[:5]
    )
    watchlist_lines = "\n".join(
        f"  {i+1}. {r.ticker} ({r.company_name}) – Score {r.combined_score:.0f}/100 | {r.reason}"
        for i, r in enumerate(top_stocks[:20])
    )

    user_prompt = f"""Write a professional morning market brief for {date_str}.

MAJOR INDICES (prior close / pre-market):
{index_lines}

SECTOR PERFORMANCE:
{sector_lines}

TOP GAINERS:
{gainer_lines}

TOP LOSERS:
{loser_lines}

TODAY'S WATCHLIST (top 20 screener picks):
{watchlist_lines}

MARKET STATUS: {overview.market_status}

Structure the brief as follows:
1. OPENING COMMENTARY (~100 words): Overall market tone, key overnight developments
2. MARKET SNAPSHOT: Commentary on index moves and what they signal
3. SECTOR ROTATION: Which sectors are leading/lagging and why it matters
4. TOP MOVERS: Brief narrative on notable gainers/losers
5. WATCHLIST HIGHLIGHTS: Pick the top 5 from the watchlist, explain WHY each is interesting today
6. KEY RISKS & CATALYSTS: 3 things to watch today (earnings, macro data, Fed, geopolitics)
7. TRADING STRATEGY: Actionable guidance — setups, levels, or themes to focus on

Aim for ~500-700 words. Be precise, insightful, and add value beyond the raw numbers."""

    try:
        return await _stream_response(system, user_prompt)
    except Exception as e:
        logger.error("Claude morning brief failed: %s", e)
        return f"Morning brief AI narrative unavailable: {e}"


# ── Quick Analysis ────────────────────────────────────────────────────────────

async def quick_analysis(ticker: str, snapshot: dict) -> str:
    """Quick 3-5 sentence take on a ticker based on snapshot data only."""
    day = snapshot.get("day", {})
    prev = snapshot.get("prevDay", {})
    price = float(day.get("c") or 0)
    change_pct = float(snapshot.get("todaysChangePerc") or 0)
    volume = float(day.get("v") or 0)
    prev_close = float(prev.get("c") or 0)

    system = "You are a concise equity analyst. Give a quick read in 3-5 sentences."
    user_prompt = (
        f"Quick analysis of {ticker}:\n"
        f"Current price: ${price:.2f}\n"
        f"Day change: {change_pct:+.2f}%\n"
        f"Volume: {volume:,.0f}\n"
        f"Previous close: ${prev_close:.2f}\n\n"
        f"What should a trader know about {ticker} right now? "
        f"Include price action, momentum, and one actionable observation."
    )
    try:
        return await _stream_response(system, user_prompt)
    except Exception as e:
        return f"Analysis unavailable: {e}"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fmt_large(v: float | None) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1e12:
        return f"${v/1e12:.2f}T"
    if abs(v) >= 1e9:
        return f"${v/1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"
