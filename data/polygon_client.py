"""Async Polygon.io REST API client."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp
import pandas as pd

from config import config

logger = logging.getLogger(__name__)


class PolygonClient:
    BASE_URL = config.POLYGON_BASE_URL

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._semaphore = asyncio.Semaphore(config.POLYGON_MAX_CONCURRENT)

    async def __aenter__(self) -> "PolygonClient":
        self._session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {config.POLYGON_API_KEY}"},
            timeout=aiohttp.ClientTimeout(total=30),
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session:
            await self._session.close()

    async def _get(self, path: str, params: dict | None = None) -> dict:
        """Make a GET request with rate-limiting semaphore."""
        async with self._semaphore:
            url = f"{self.BASE_URL}{path}"
            try:
                assert self._session is not None
                async with self._session.get(url, params=params or {}) as resp:
                    if resp.status == 429:
                        logger.warning("Rate limited by Polygon, waiting 12s")
                        await asyncio.sleep(12)
                        async with self._session.get(url, params=params or {}) as retry:
                            retry.raise_for_status()
                            return await retry.json()
                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientResponseError as e:
                logger.error("Polygon API error %s for %s: %s", e.status, path, e.message)
                return {}
            except Exception as e:
                logger.error("Network error for %s: %s", path, e)
                return {}

    # ── Snapshots ────────────────────────────────────────────────────────────

    async def get_ticker_snapshot(self, ticker: str) -> dict:
        """Current price, volume, day change for a single ticker."""
        data = await self._get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker.upper()}")
        return data.get("ticker", {})

    async def get_multiple_snapshots(self, tickers: list[str]) -> dict[str, dict]:
        """Batch snapshot for multiple tickers. Returns {ticker: snapshot_dict}."""
        chunk_size = 100
        results: dict[str, dict] = {}
        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i : i + chunk_size]
            params = {"tickers": ",".join(chunk)}
            data = await self._get("/v2/snapshot/locale/us/markets/stocks/tickers", params)
            for snap in data.get("tickers", []):
                t = snap.get("ticker", "")
                if t:
                    results[t] = snap
        return results

    async def get_gainers(self, direction: str = "gainers") -> list[dict]:
        """Top market movers. direction = 'gainers' | 'losers'."""
        data = await self._get(f"/v2/snapshot/locale/us/markets/stocks/{direction}")
        return data.get("tickers", [])

    async def get_most_active(self) -> list[dict]:
        """Top tickers by volume using snapshot with include_otc=false filter."""
        # Polygon doesn't have a dedicated "most active" endpoint, so we fetch
        # a broad snapshot of all tickers and sort by volume
        params = {"include_otc": "false"}
        data = await self._get("/v2/snapshot/locale/us/markets/stocks/tickers", params)
        tickers = data.get("tickers", [])
        # Sort by day volume descending
        tickers.sort(key=lambda x: x.get("day", {}).get("v", 0), reverse=True)
        return tickers[:20]

    # ── Historical Aggregates ────────────────────────────────────────────────

    async def get_aggregates(
        self,
        ticker: str,
        days: int = 365,
        timespan: str = "day",
        multiplier: int = 1,
    ) -> pd.DataFrame:
        """Fetch OHLCV history. Returns a DataFrame with columns: date, open, high, low, close, volume."""
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 5000,
        }
        data = await self._get(
            f"/v2/aggs/ticker/{ticker.upper()}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
            params,
        )
        results = data.get("results", [])
        if not results:
            return pd.DataFrame()
        df = pd.DataFrame(results)
        df.rename(
            columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "t": "timestamp"},
            inplace=True,
        )
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("date", inplace=True)
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df.tail(days)

    async def get_previous_close(self, ticker: str) -> dict:
        """Previous trading day's OHLCV for a ticker."""
        data = await self._get(f"/v2/aggs/ticker/{ticker.upper()}/prev")
        results = data.get("results", [])
        return results[0] if results else {}

    # ── Reference Data ───────────────────────────────────────────────────────

    async def get_ticker_details(self, ticker: str) -> dict:
        """Company info: name, description, sector, market cap, shares outstanding, etc."""
        data = await self._get(f"/v3/reference/tickers/{ticker.upper()}")
        return data.get("results", {})

    async def get_financials(self, ticker: str, limit: int = 5) -> list[dict]:
        """Financial statements (income, balance sheet, cash flow). Returns list sorted newest first."""
        params = {
            "ticker": ticker.upper(),
            "limit": limit,
            "sort": "period_of_report_date",
            "order": "desc",
            "include_sources": "false",
        }
        data = await self._get("/vX/reference/financials", params)
        return data.get("results", [])

    # ── Market Status ────────────────────────────────────────────────────────

    async def get_market_status(self) -> dict:
        """Whether the US stock market is open/closed."""
        return await self._get("/v1/marketstatus/now")

    # ── Convenience helpers ───────────────────────────────────────────────────

    async def get_ticker_snapshot_safe(self, ticker: str) -> dict | None:
        """Returns None instead of {} on failure so callers can distinguish."""
        snap = await self.get_ticker_snapshot(ticker)
        return snap if snap else None
