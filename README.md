# Stock Screener & Fundamental Analyzer

A powerful CLI-based stock screener and fundamental analyzer supporting both **US markets** (via Polygon.io + Yahoo Finance) and **TASI / Saudi Exchange** (via Yahoo Finance).

---

## Features

- **Multi-market screening**: US (NASDAQ, NYSE) and TASI (Tadawul/Saudi Exchange)
- **Configurable criteria**: 20+ fundamental filters with sensible defaults
- **Named presets**: `value`, `growth`, `dividend`, `quality`
- **Full fundamental analysis**: Valuation, profitability, growth, financial health, cash flow, dividends, analyst consensus — all in one rich terminal report
- **Composite scoring**: Stocks ranked by a 0–100 quality/value score
- **CSV export**: Export screener results for further analysis
- **JSON export**: Export full analysis reports

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API key

```bash
cp .env.example .env
# Edit .env and add your Polygon.io API key:
# POLYGON_API_KEY=your_key_here
```

> **Note:** Polygon.io is only required for US screening (ticker universe). TASI screening works without it using Yahoo Finance.

---

## Usage

### Screen US Stocks

```bash
# Default criteria (up to 300 tickers)
python main.py screen us

# Value preset, limit to 100 tickers
python main.py screen us --preset value --max-tickers 100

# Custom criteria override
python main.py screen us --criteria '{"max_pe": 20, "min_roe": 15, "min_dividend_yield": 2}'

# Export results
python main.py screen us --preset value --export results.csv
```

### Screen TASI Stocks

```bash
# Screen all TASI stocks (no API key needed)
python main.py screen tasi

# Growth preset
python main.py screen tasi --preset growth

# Export results
python main.py screen tasi --preset dividend --export tasi_dividends.csv
```

### Screen Both Markets

```bash
python main.py screen both --preset value
python main.py screen both --us-max 200 --tasi-max 100
```

### Full Fundamental Analysis

```bash
# US stock
python main.py analyze AAPL
python main.py analyze MSFT
python main.py analyze NVDA

# Saudi stocks (Yahoo Finance .SR suffix)
python main.py analyze 2222.SR    # Saudi Aramco
python main.py analyze 1180.SR    # Al Rajhi Bank
python main.py analyze 4010.SR    # Saudi Telecom (STC)
python main.py analyze 2310.SR    # Maaden

# Export report as JSON
python main.py analyze AAPL --export aapl_report.json
```

### View Active Criteria

```bash
# Default criteria
python main.py criteria

# Preset criteria
python main.py criteria --preset value
python main.py criteria --preset growth
```

### List Available Tickers

```bash
python main.py tickers --market tasi
python main.py tickers --market us --limit 100
```

---

## Screening Presets

| Preset     | Focus                                      |
|------------|--------------------------------------------|
| `value`    | Low P/E, P/B, EV/EBITDA; solid ROE & margins |
| `growth`   | High revenue & EPS growth, strong margins  |
| `dividend` | Dividend yield >= 3%, sustainable payout   |
| `quality`  | High ROE/ROA, wide margins, low debt       |

---

## Screening Criteria Reference

| Parameter              | Default  | Description                        |
|------------------------|----------|------------------------------------|
| `max_pe`               | 25       | Max trailing P/E ratio             |
| `max_pb`               | 3        | Max price-to-book                  |
| `max_ps`               | 5        | Max price-to-sales                 |
| `max_ev_ebitda`        | 12       | Max EV/EBITDA multiple             |
| `max_peg`              | 2        | Max PEG ratio                      |
| `min_roe`              | 10%      | Min return on equity               |
| `min_roa`              | 5%       | Min return on assets               |
| `min_gross_margin`     | 20%      | Min gross profit margin            |
| `min_operating_margin` | 8%       | Min operating margin               |
| `min_net_margin`       | 5%       | Min net profit margin              |
| `min_revenue_growth`   | disabled | Min YoY revenue growth             |
| `min_eps_growth`       | disabled | Min YoY EPS growth                 |
| `max_debt_equity`      | 1.0x     | Max debt-to-equity ratio           |
| `min_current_ratio`    | 1.2x     | Min current ratio                  |
| `min_dividend_yield`   | disabled | Min dividend yield                 |
| `min_market_cap`       | 100M     | Min market cap (USD or SAR)        |

Edit `config/settings.py` to change defaults permanently.

---

## Fundamental Analysis Report Sections

Each `analyze` report covers:

1. **Company Overview** - Name, sector, industry, country, description
2. **Price & Market Data** - Price, market cap, EV, 52-week range, beta, volume
3. **Valuation Multiples** - P/E (trailing/forward), P/B, P/S, EV/EBITDA, EV/Revenue, PEG
4. **Profitability** - Gross/operating/net margins, ROE, ROA, EBITDA (with letter grades)
5. **Growth** - Revenue & EPS growth, multi-year income history
6. **Financial Health** - Current/quick ratio, debt/equity, total debt/cash, debt history (with grades)
7. **Cash Flow** - Operating CF, CapEx, FCF, FCF yield, multi-year FCF history
8. **Dividends** - Yield, rate, payout ratio, ex-dividend date
9. **Analyst Consensus** - Recommendation, price target, upside/downside
10. **Strengths** - Auto-detected positive signals
11. **Risks** - Auto-detected risk factors
12. **Overall Score** - Composite 0-100 quality/value score

---

## Data Sources

| Market | Ticker Universe    | Fundamental Data         |
|--------|--------------------|--------------------------|
| US     | Polygon.io API     | Yahoo Finance (yfinance) |
| TASI   | Built-in list      | Yahoo Finance (.SR suffix) |

TASI tickers follow Yahoo Finance format: `NNNN.SR` (e.g., `2222.SR` for Saudi Aramco).
