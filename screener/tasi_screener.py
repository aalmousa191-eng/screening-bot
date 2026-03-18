"""
TASI (Saudi Stock Exchange) screener.
Uses Yahoo Finance (.SR suffix) for fundamental data.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from data.tasi_client import get_tasi_tickers
from data.yahoo_client import get_fundamentals
from screener.criteria import apply_criteria, score_stock
from config.settings import SCREENING_CRITERIA, PRESETS


def screen_tasi(
    criteria: dict | None = None,
    preset: str | None = None,
    max_tickers: int | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
    use_static_list: bool = True,
) -> list[dict]:
    """
    Screen TASI stocks.

    Args:
        criteria:         Override dict of screening criteria.
        preset:           Named preset ('value', 'growth', 'dividend', 'quality').
        max_tickers:      Optional cap on number of tickers evaluated.
        progress_cb:      Optional callback(current, total, ticker).
        use_static_list:  Use bundled ticker list (faster, more reliable).

    Returns:
        List of passing stock dicts sorted by composite score (desc).
    """
    active_criteria = dict(SCREENING_CRITERIA)
    if preset and preset in PRESETS:
        active_criteria.update(PRESETS[preset])
    if criteria:
        active_criteria.update(criteria)

    tickers = get_tasi_tickers(use_static=use_static_list)
    if max_tickers:
        tickers = tickers[:max_tickers]

    results = []
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        if progress_cb:
            progress_cb(i + 1, total, ticker)

        stock = get_fundamentals(ticker)
        if stock.get("not_found"):
            continue  # invalid ticker – no delay needed
        if "error" in stock or not stock.get("market_cap"):
            time.sleep(0.1)
            continue

        passed, _ = apply_criteria(stock, active_criteria)
        if passed:
            stock["score"] = score_stock(stock)
            results.append(stock)

        time.sleep(0.2)

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results
