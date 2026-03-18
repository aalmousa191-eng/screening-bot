"""
US stock screener – uses Polygon.io for the ticker universe + Yahoo Finance for fundamentals.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from data.polygon_client import get_all_us_tickers
from data.yahoo_client import get_fundamentals
from screener.criteria import apply_criteria, score_stock
from config.settings import SCREENING_CRITERIA, PRESETS


def screen_us(
    criteria: dict | None = None,
    preset: str | None = None,
    max_tickers: int = 500,
    exchanges: list[str] | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> list[dict]:
    """
    Screen US stocks.

    Args:
        criteria:     Override dict of screening criteria.
        preset:       Named preset ('value', 'growth', 'dividend', 'quality').
        max_tickers:  Cap how many tickers to evaluate (for speed).
        exchanges:    Polygon exchange MIC codes, e.g. ['XNAS', 'XNYS'].
        progress_cb:  Optional callback(current, total, ticker) for progress updates.

    Returns:
        List of passing stock dicts sorted by composite score (desc).
    """
    active_criteria = dict(SCREENING_CRITERIA)
    if preset and preset in PRESETS:
        active_criteria.update(PRESETS[preset])
    if criteria:
        active_criteria.update(criteria)

    # Fetch ticker universe
    tickers = get_all_us_tickers(
        market="stocks",
        active=True,
        max_tickers=max_tickers,
    )

    results = []
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        if progress_cb:
            progress_cb(i + 1, total, ticker)

        stock = get_fundamentals(ticker)
        if "error" in stock or not stock.get("market_cap"):
            time.sleep(0.1)
            continue

        passed, _ = apply_criteria(stock, active_criteria)
        if passed:
            stock["score"] = score_stock(stock)
            results.append(stock)

        time.sleep(0.15)  # gentle rate limiting

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results
