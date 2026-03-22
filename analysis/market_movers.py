"""Market movers: gainers, losers, most active, indices, and sectors."""
import asyncio
import logging
from dataclasses import dataclass

from data.polygon_client import PolygonClient
from config import config

logger = logging.getLogger(__name__)


@dataclass
class MoverEntry:
    ticker: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: float


@dataclass
class MarketOverview:
    indices: list[dict]
    sectors: list[dict]
    gainers: list[MoverEntry]
    losers: list[MoverEntry]
    most_active: list[MoverEntry]
    market_status: str = "unknown"


def _snap_to_mover(snap: dict) -> MoverEntry | None:
    """Convert a Polygon snapshot dict to a MoverEntry."""
    try:
        day = snap.get("day", {})
        prev = snap.get("prevDay", {})
        price = float(day.get("c") or snap.get("lastTrade", {}).get("p") or 0)
        prev_close = float(prev.get("c") or 0)
        change = price - prev_close if prev_close else 0.0
        change_pct = float(snap.get("todaysChangePerc") or 0)
        volume = float(day.get("v") or 0)
        ticker = snap.get("ticker", "")
        return MoverEntry(
            ticker=ticker,
            name=ticker,
            price=price,
            change=change,
            change_pct=change_pct,
            volume=volume,
        )
    except Exception:
        return None


async def get_market_overview(client: PolygonClient) -> MarketOverview:
    """Fetch all market overview data concurrently."""
    index_tickers = list(config.INDEX_TICKERS.values())
    sector_tickers = list(config.SECTOR_TICKERS.values())
    all_ref_tickers = index_tickers + sector_tickers

    # Parallel fetch
    snaps_task = client.get_multiple_snapshots(all_ref_tickers)
    gainers_task = client.get_gainers("gainers")
    losers_task = client.get_losers("losers")
    active_task = client.get_most_active()
    status_task = client.get_market_status()

    snaps, raw_gainers, raw_losers, raw_active, status_data = await asyncio.gather(
        snaps_task, gainers_task, losers_task, active_task, status_task
    )

    # Build indices list
    indices = []
    for name, sym in config.INDEX_TICKERS.items():
        snap = snaps.get(sym, {})
        day = snap.get("day", {})
        prev = snap.get("prevDay", {})
        price = float(day.get("c") or 0)
        prev_close = float(prev.get("c") or 0)
        change_pct = float(snap.get("todaysChangePerc") or 0)
        indices.append({"name": name, "ticker": sym, "price": price,
                        "change_pct": change_pct, "prev_close": prev_close})

    # Build sectors list
    sectors = []
    for name, sym in config.SECTOR_TICKERS.items():
        snap = snaps.get(sym, {})
        day = snap.get("day", {})
        prev = snap.get("prevDay", {})
        price = float(day.get("c") or 0)
        change_pct = float(snap.get("todaysChangePerc") or 0)
        sectors.append({"name": name, "ticker": sym, "price": price,
                        "change_pct": change_pct})
    sectors.sort(key=lambda x: x["change_pct"], reverse=True)

    gainers = [m for m in (_snap_to_mover(s) for s in raw_gainers[:10]) if m]
    losers = [m for m in (_snap_to_mover(s) for s in raw_losers[:10]) if m]
    most_active = [m for m in (_snap_to_mover(s) for s in raw_active[:10]) if m]

    market_status = status_data.get("market", "unknown")

    return MarketOverview(
        indices=indices,
        sectors=sectors,
        gainers=gainers,
        losers=losers,
        most_active=most_active,
        market_status=market_status,
    )


def format_movers_report(overview: MarketOverview) -> str:
    """Formatted HTML report of market movers."""
    lines = ["<b>📊 MARKET MOVERS</b>", ""]

    # Market status
    status_emoji = {"open": "🟢 OPEN", "closed": "🔴 CLOSED", "extended-hours": "🟡 EXTENDED"}
    lines.append(f"Market: <b>{status_emoji.get(overview.market_status, overview.market_status.upper())}</b>")
    lines.append("")

    # Indices
    lines.append("<b>── MAJOR INDICES</b>")
    for idx in overview.indices:
        arrow = "▲" if idx["change_pct"] >= 0 else "▼"
        sign = "+" if idx["change_pct"] >= 0 else ""
        price_str = f"${idx['price']:,.2f}" if idx["price"] else "N/A"
        lines.append(f"{idx['name']:15} {price_str:>10}  {arrow} {sign}{idx['change_pct']:.2f}%")
    lines.append("")

    # Sectors
    lines.append("<b>── SECTOR PERFORMANCE</b>")
    for sec in overview.sectors:
        arrow = "▲" if sec["change_pct"] >= 0 else "▼"
        sign = "+" if sec["change_pct"] >= 0 else ""
        bar = "█" * min(abs(int(sec["change_pct"] * 5)), 5)
        lines.append(f"{sec['name']:18} {arrow} {sign}{sec['change_pct']:.2f}%  {bar}")
    lines.append("")

    # Gainers
    lines.append("<b>── 🏆 TOP GAINERS</b>")
    for i, m in enumerate(overview.gainers[:5], 1):
        lines.append(f"{i}. <b>{m.ticker}</b>  ${m.price:.2f}  ▲ +{m.change_pct:.2f}%  vol:{m.volume/1e6:.1f}M")
    lines.append("")

    # Losers
    lines.append("<b>── 💔 TOP LOSERS</b>")
    for i, m in enumerate(overview.losers[:5], 1):
        lines.append(f"{i}. <b>{m.ticker}</b>  ${m.price:.2f}  ▼ {m.change_pct:.2f}%  vol:{m.volume/1e6:.1f}M")
    lines.append("")

    # Most Active
    lines.append("<b>── ⚡ MOST ACTIVE</b>")
    for i, m in enumerate(overview.most_active[:5], 1):
        sign = "+" if m.change_pct >= 0 else ""
        lines.append(f"{i}. <b>{m.ticker}</b>  ${m.price:.2f}  {sign}{m.change_pct:.2f}%  vol:{m.volume/1e6:.1f}M")

    return "<pre>" + "\n".join(lines) + "</pre>"
