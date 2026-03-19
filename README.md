# Stock Screening Bot

A CLI-based AI-assisted stock screener for **US markets** (NYSE/NASDAQ) and **TASI** (Saudi Tadawul), powered by the [TradingView Screener API](https://github.com/shner-elmo/tradingview-screener).

No API key required.

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Usage

### Interactive mode (no arguments)

```bash
python main.py
```

You'll be prompted to pick a preset, market, and result limit.

### Direct commands

```bash
# List all available presets
python main.py list

# Run a specific preset
python main.py run --preset oversold              # US oversold stocks
python main.py run --preset breakout --market tasi
python main.py run --preset trend --market both --limit 30
python main.py run --preset value --market tasi
python main.py run --preset volume_spike --market us
python main.py run --preset macd_cross --market both
```

---

## Screening Presets

| Key | Name | Criteria |
|-----|------|----------|
| `oversold` | Oversold Reversal | RSI ≤ 35, price > EMA200, rel. volume ≥ 1.5x |
| `breakout` | Momentum Breakout | MACD bullish, RSI 50–75, price > EMA50, rel. volume ≥ 1.5x |
| `trend` | Strong Uptrend | Price > EMA20 > EMA50 > EMA200, RSI 50–70 |
| `value` | Value Stocks | P/E 5–20, positive EPS, price > EMA200 |
| `volume_spike` | Unusual Volume | Relative volume ≥ 3x 10-day average |
| `macd_cross` | MACD Bullish Cross | MACD > Signal, MACD > 0, RSI < 65, price > EMA50 |

---

## Markets

| Flag | Description |
|------|-------------|
| `us` | NYSE + NASDAQ (default) |
| `tasi` | Saudi Tadawul (TASI) |
| `both` | Both markets combined |

---

## Adding Custom Presets

Edit `screener/presets.py`. Each preset needs:

```python
"my_preset": {
    "label": "Human-Readable Name",
    "description": "Short description of the strategy",
    "columns": BASE_COLUMNS + ["RSI", "EMA50"],   # columns to fetch & display
    "filters_fn": lambda: [                         # TradingView filter conditions
        col("RSI") < 40,
        col("close") > col("EMA50"),
    ],
    "sort_by": "RSI",    # column to sort results by
    "sort_asc": True,    # True = ascending, False = descending
}
```

Valid column names come from TradingView's scanner fields. Common ones:
`RSI`, `MACD.macd`, `MACD.signal`, `EMA20`, `EMA50`, `EMA200`, `Relative.Volume`,
`price_earnings_ttm`, `earnings_per_share_basic_ttm`, `High.All`, `Low.All`
