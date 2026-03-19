"""
Core scanner logic — wraps tradingview-screener Query API.
"""

from __future__ import annotations

import pandas as pd
from tradingview_screener import Query, col

MARKET_MAP = {
    "us": "america",
    "tasi": "saudi_arabia",
    "both": None,  # handled separately
}


def run_screen(
    preset: dict,
    market: str = "us",
    limit: int = 50,
) -> pd.DataFrame:
    """
    Run a TradingView screen for the given preset and market.

    Args:
        preset:  A preset dict from presets.py
        market:  'us', 'tasi', or 'both'
        limit:   Max number of results to return

    Returns:
        DataFrame with screened results.
    """
    if market == "both":
        us_df = _query(preset, "america", limit)
        sa_df = _query(preset, "saudi_arabia", limit)
        if us_df.empty and sa_df.empty:
            return pd.DataFrame()
        us_df["market"] = "US"
        sa_df["market"] = "TASI"
        combined = pd.concat([us_df, sa_df], ignore_index=True)
        return combined
    else:
        tv_market = MARKET_MAP.get(market, "america")
        df = _query(preset, tv_market, limit)
        if not df.empty:
            df["market"] = market.upper()
        return df


def _query(preset: dict, tv_market: str, limit: int) -> pd.DataFrame:
    columns = preset["columns"]
    filters = preset["filters_fn"]()
    sort_by = preset.get("sort_by", "volume")
    sort_asc = preset.get("sort_asc", False)

    try:
        q = (
            Query()
            .select(*columns)
            .where(*filters)
            .set_markets(tv_market)
            .order_by(sort_by, ascending=sort_asc)
            .limit(limit)
        )
        count, df = q.get_scanner_data()
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception as exc:
        raise RuntimeError(
            f"TradingView query failed for market '{tv_market}': {exc}"
        ) from exc
