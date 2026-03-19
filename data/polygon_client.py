"""
Polygon.io client for US market data.
Used for: ticker universe fetching and supplementary financial data.
"""
from __future__ import annotations

import time
import requests
from typing import Iterator
from config.settings import POLYGON_API_KEY

BASE = "https://api.polygon.io"


def _get(endpoint: str, params: dict | None = None, retries: int = 3) -> dict:
    params = params or {}
    params["apiKey"] = POLYGON_API_KEY
    for attempt in range(retries):
        try:
            r = requests.get(f"{BASE}{endpoint}", params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            if r.status_code == 429:
                time.sleep(2 ** attempt * 5)
            else:
                raise
        except requests.exceptions.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return {}


def get_all_us_tickers(
    market: str = "stocks",
    exchange: str | None = None,
    active: bool = True,
    limit: int = 1000,
    max_tickers: int | None = None,
) -> list[str]:
    """
    Return a list of US stock tickers from Polygon.
    Paginates automatically through all results.
    """
    tickers = []
    params: dict = {
        "market": market,
        "active": str(active).lower(),
        "limit": limit,
    }
    if exchange:
        params["exchange"] = exchange

    cursor = None
    while True:
        if cursor:
            params["cursor"] = cursor
        data = _get("/v3/reference/tickers", params)
        results = data.get("results", [])
        tickers.extend(r["ticker"] for r in results if r.get("ticker"))
        if max_tickers and len(tickers) >= max_tickers:
            tickers = tickers[:max_tickers]
            break
        cursor = data.get("next_url", "").split("cursor=")[-1] if data.get("next_url") else None
        if not cursor:
            break
        time.sleep(0.12)  # stay under rate limits

    return tickers


def get_ticker_details(ticker: str) -> dict:
    """Fetch reference/details for a single ticker."""
    data = _get(f"/v3/reference/tickers/{ticker}")
    return data.get("results", {})


def get_financials(ticker: str, limit: int = 4) -> list[dict]:
    """
    Fetch financial statements from Polygon (experimental endpoint).
    Returns list of filing objects ordered latest first.
    """
    data = _get(
        "/vX/reference/financials",
        {"ticker": ticker, "limit": limit, "sort": "filing_date", "order": "desc"},
    )
    return data.get("results", [])


def get_last_quote(ticker: str) -> dict | None:
    """Fetch last trade/quote for ticker."""
    try:
        data = _get(f"/v2/last/trade/{ticker}")
        return data.get("results")
    except Exception:
        return None


def get_aggregates(ticker: str, from_date: str, to_date: str, multiplier: int = 1, timespan: str = "day") -> list[dict]:
    """Fetch OHLCV bars for a ticker."""
    data = _get(
        f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
        {"adjusted": "true", "sort": "asc", "limit": 5000},
    )
    return data.get("results", [])
