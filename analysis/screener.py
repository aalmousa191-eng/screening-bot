"""Daily stock screener: filters universe to top 20 watchlist candidates."""
import asyncio
import logging
from dataclasses import dataclass, field

from data.polygon_client import PolygonClient
from analysis.technical import calculate_indicators, build_snapshot, TechnicalSnapshot
from analysis.fundamental import parse_fundamentals, FundamentalSnapshot
from config import config

logger = logging.getLogger(__name__)


@dataclass
class ScreenerResult:
    ticker: str
    company_name: str
    price: float
    change_pct: float
    market_cap: float | None
    volume: float
    volume_ratio: float | None
    technical_score: float
    fundamental_score: float
    combined_score: float
    trend_signal: str
    overall_signal: str
    rsi: float | None
    pe_ratio: float | None
    revenue_growth: float | None
    reason: str = ""


async def _analyze_single(
    ticker: str,
    client: PolygonClient,
) -> ScreenerResult | None:
    """Full analysis pipeline for one ticker."""
    try:
        # Fetch data
        df, details, financials, snap = await asyncio.gather(
            client.get_aggregates(ticker, days=365),
            client.get_ticker_details(ticker),
            client.get_financials(ticker, limit=4),
            client.get_ticker_snapshot(ticker),
        )

        if df.empty or len(df) < 50:
            return None

        price = float(snap.get("day", {}).get("c") or df["close"].iloc[-1])
        if price < 5.0:
            return None

        volume = float(snap.get("day", {}).get("v") or df["volume"].iloc[-1])

        # Technical analysis
        df_ind = calculate_indicators(df)
        tech = build_snapshot(ticker, df_ind)

        # Fundamental analysis
        fund = parse_fundamentals(ticker, details, financials, price)

        # Average daily volume filter (last 20 days)
        avg_vol = float(df["volume"].tail(20).mean())
        if avg_vol < 300_000:
            return None

        # Combined score (60% technical, 40% fundamental)
        combined = tech.score * 0.6 + fund.quality_score * 0.4

        reason = _generate_reason(tech, fund)

        return ScreenerResult(
            ticker=ticker,
            company_name=fund.company_name or ticker,
            price=price,
            change_pct=tech.change_pct,
            market_cap=fund.market_cap,
            volume=volume,
            volume_ratio=tech.volume_ratio,
            technical_score=tech.score,
            fundamental_score=fund.quality_score,
            combined_score=round(combined, 1),
            trend_signal=tech.trend_signal,
            overall_signal=tech.overall_signal,
            rsi=tech.rsi,
            pe_ratio=fund.pe_ratio,
            revenue_growth=fund.revenue_growth_yoy,
            reason=reason,
        )
    except Exception as e:
        logger.warning("Screener failed for %s: %s", ticker, e)
        return None


def _generate_reason(tech: TechnicalSnapshot, fund: FundamentalSnapshot) -> str:
    """One-line rationale for including the stock."""
    reasons = []
    if tech.trend_signal in ("STRONG_BULLISH", "BULLISH"):
        reasons.append("Strong uptrend")
    if tech.rsi and 50 < tech.rsi < 70:
        reasons.append(f"RSI {tech.rsi:.0f}")
    if tech.macd_bullish:
        reasons.append("Bullish MACD")
    if tech.volume_ratio and tech.volume_ratio > 1.3:
        reasons.append(f"Vol {tech.volume_ratio:.1f}x avg")
    if fund.revenue_growth_yoy and fund.revenue_growth_yoy > 10:
        reasons.append(f"Rev growth {fund.revenue_growth_yoy:.0f}%")
    if fund.pe_ratio and fund.pe_ratio < 20:
        reasons.append(f"P/E {fund.pe_ratio:.1f}x (cheap)")
    return " | ".join(reasons) if reasons else "Meets criteria"


async def run_screener(client: PolygonClient | None = None) -> list[ScreenerResult]:
    """
    Screen the entire universe and return top 20 ranked candidates.
    If a client is not supplied, one will be created.
    """
    own_client = client is None
    if own_client:
        client = PolygonClient()
        await client.__aenter__()

    try:
        universe = config.SCREENER_UNIVERSE
        logger.info("Screening %d tickers...", len(universe))

        # Step 1: batch snapshot to pre-filter by price & volume
        snapshots = await client.get_multiple_snapshots(universe)

        # Pre-filter: price $5+ and min volume
        candidates = []
        for ticker in universe:
            snap = snapshots.get(ticker, {})
            day = snap.get("day", {})
            price = float(day.get("c") or 0)
            vol = float(day.get("v") or 0)
            if price >= 5.0 and vol >= 200_000:
                candidates.append(ticker)

        logger.info("%d candidates after pre-filter", len(candidates))

        # Step 2: full analysis on candidates in batches
        batch_size = 10
        results: list[ScreenerResult] = []
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i : i + batch_size]
            batch_results = await asyncio.gather(
                *[_analyze_single(t, client) for t in batch]
            )
            results.extend(r for r in batch_results if r is not None)
            if i + batch_size < len(candidates):
                await asyncio.sleep(1)  # slight delay between batches

        # Step 3: rank by combined score, take top 20
        results.sort(key=lambda r: r.combined_score, reverse=True)
        top20 = results[:20]
        logger.info("Screener done. Top 20 selected from %d candidates.", len(results))
        return top20

    finally:
        if own_client:
            await client.__aexit__(None, None, None)


def format_screener_report(results: list[ScreenerResult]) -> str:
    """Formatted HTML report of top 20 screener results."""
    if not results:
        return "<b>🔍 SCREENER</b>\n\nNo results found. Market may be closed or data unavailable."

    lines = [
        "<b>🔍 TOP 20 STOCKS TO WATCH</b>",
        f"<i>Based on technical + fundamental scoring</i>",
        "",
    ]

    for i, r in enumerate(results, 1):
        arrow = "▲" if r.change_pct >= 0 else "▼"
        sign = "+" if r.change_pct >= 0 else ""
        mc = _fmt_large(r.market_cap)
        pe_str = f"PE:{r.pe_ratio:.1f}" if r.pe_ratio else ""
        rev_str = f"RevG:{r.revenue_growth:+.0f}%" if r.revenue_growth is not None else ""
        score_bar = "█" * int(r.combined_score / 10)

        lines.append(
            f"<b>{i:2}. {r.ticker}</b>  ${r.price:.2f}  {arrow}{sign}{r.change_pct:.2f}%"
        )
        lines.append(
            f"    Score: {r.combined_score:.0f}/100 {score_bar}"
        )
        lines.append(
            f"    {r.trend_signal} | RSI:{r.rsi:.0f if r.rsi else 'N/A'} | {pe_str} {rev_str}"
        )
        lines.append(f"    💡 {r.reason}")
        lines.append("")

    return "\n".join(lines)


def _fmt_large(v: float | None) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1e12:
        return f"${v/1e12:.1f}T"
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    return f"${v:,.0f}"
