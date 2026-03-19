"""
Predefined screening presets for US and TASI markets.
Each preset defines a filter factory (callable) and display columns.
"""

# Columns always fetched
BASE_COLUMNS = [
    "name",
    "description",
    "close",
    "change",
    "volume",
    "average_volume_10d_calc",
    "market_cap_basic",
]


def _oversold_filters():
    from tradingview_screener import col
    return [
        col("RSI") <= 35,
        col("close") > col("EMA200"),
        col("Relative.Volume") >= 1.5,
    ]


def _breakout_filters():
    from tradingview_screener import col
    return [
        # near 52-week high: price within 3% of 52w high (via pct change from high)
        col("MACD.macd") > col("MACD.signal"),
        col("Relative.Volume") >= 1.5,
        col("RSI").between(50, 75),
        col("close") > col("EMA50"),
    ]


def _trend_filters():
    from tradingview_screener import col
    return [
        col("close") > col("EMA20"),
        col("EMA20") > col("EMA50"),
        col("EMA50") > col("EMA200"),
        col("RSI").between(50, 70),
    ]


def _value_filters():
    from tradingview_screener import col
    return [
        col("price_earnings_ttm").between(5, 20),
        col("earnings_per_share_basic_ttm") > 0,
        col("close") > col("EMA200"),
    ]


def _volume_spike_filters():
    from tradingview_screener import col
    return [
        col("Relative.Volume") >= 3.0,
    ]


def _macd_cross_filters():
    from tradingview_screener import col
    return [
        col("MACD.macd") > col("MACD.signal"),
        col("MACD.macd") > 0,
        col("RSI") < 65,
        col("close") > col("EMA50"),
    ]


PRESETS = {
    # ──────────────────────────────────────────────────────────────
    # 1. OVERSOLD REVERSAL
    # ──────────────────────────────────────────────────────────────
    "oversold": {
        "label": "Oversold Reversal",
        "description": "RSI ≤ 35, price above EMA200, relative volume ≥ 1.5x",
        "columns": BASE_COLUMNS + ["RSI", "EMA200", "Relative.Volume"],
        "filters_fn": _oversold_filters,
        "sort_by": "RSI",
        "sort_asc": True,
    },

    # ──────────────────────────────────────────────────────────────
    # 2. MOMENTUM BREAKOUT
    # ──────────────────────────────────────────────────────────────
    "breakout": {
        "label": "Momentum Breakout",
        "description": "MACD bullish, RSI 50–75, price > EMA50, volume ≥ 1.5x",
        "columns": BASE_COLUMNS + ["RSI", "EMA50", "MACD.macd", "MACD.signal", "Relative.Volume"],
        "filters_fn": _breakout_filters,
        "sort_by": "Relative.Volume",
        "sort_asc": False,
    },

    # ──────────────────────────────────────────────────────────────
    # 3. STRONG UPTREND (Golden Cross)
    # ──────────────────────────────────────────────────────────────
    "trend": {
        "label": "Strong Uptrend",
        "description": "Price > EMA20 > EMA50 > EMA200, RSI 50–70",
        "columns": BASE_COLUMNS + ["RSI", "EMA20", "EMA50", "EMA200"],
        "filters_fn": _trend_filters,
        "sort_by": "change",
        "sort_asc": False,
    },

    # ──────────────────────────────────────────────────────────────
    # 4. VALUE STOCKS
    # ──────────────────────────────────────────────────────────────
    "value": {
        "label": "Value Stocks",
        "description": "P/E 5–20, positive EPS, price above EMA200",
        "columns": BASE_COLUMNS + ["price_earnings_ttm", "earnings_per_share_basic_ttm", "EMA200"],
        "filters_fn": _value_filters,
        "sort_by": "price_earnings_ttm",
        "sort_asc": True,
    },

    # ──────────────────────────────────────────────────────────────
    # 5. UNUSUAL VOLUME SPIKE
    # ──────────────────────────────────────────────────────────────
    "volume_spike": {
        "label": "Unusual Volume",
        "description": "Relative volume ≥ 3x 10-day average",
        "columns": BASE_COLUMNS + ["Relative.Volume", "RSI", "change"],
        "filters_fn": _volume_spike_filters,
        "sort_by": "Relative.Volume",
        "sort_asc": False,
    },

    # ──────────────────────────────────────────────────────────────
    # 6. MACD BULLISH CROSSOVER
    # ──────────────────────────────────────────────────────────────
    "macd_cross": {
        "label": "MACD Bullish Cross",
        "description": "MACD > Signal, MACD > 0, RSI < 65, price > EMA50",
        "columns": BASE_COLUMNS + ["MACD.macd", "MACD.signal", "RSI", "EMA50"],
        "filters_fn": _macd_cross_filters,
        "sort_by": "RSI",
        "sort_asc": False,
    },
}
