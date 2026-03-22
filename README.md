# AI Stock Analysis & Screening Bot

A professional AI-powered equity analysis bot for Telegram, backed by **Polygon.io** market data and **Claude Opus 4.6** analysis.

## Features

| Feature | Description |
|---|---|
| `/analyze TICKER` | Full analysis: technical indicators + fundamental metrics + Claude AI narrative |
| `/technical TICKER` | RSI, MACD, Bollinger Bands, SMAs, volume, stochastic, key levels |
| `/fundamental TICKER` | Revenue, margins, P/E, P/S, EV/EBITDA, debt ratios, FCF |
| `/movers` | Live top gainers, losers, most active + 11 sector ETFs + major indices |
| `/screen` | Daily screener on ~100 US stocks → top 20 ranked watchlist |
| `/brief` | Full morning market brief (auto-sent daily at 7:00 AM ET) |
| **Daily automation** | Screener at 6:30 AM ET, morning brief at 7:00 AM ET |

## Architecture

```
screening-bot/
├── main.py                   # Entry point (bot + scheduler)
├── config.py                 # Environment config + screening universe
├── data/
│   └── polygon_client.py     # Async Polygon.io REST client
├── analysis/
│   ├── technical.py          # Pure-pandas technical indicators
│   ├── fundamental.py        # Polygon financials parser + ratios
│   ├── screener.py           # Multi-factor stock screener
│   └── market_movers.py      # Gainers/losers/sectors/indices
├── ai/
│   └── claude_analyst.py     # Claude Opus 4.6 analysis + morning brief
├── bot/
│   ├── telegram_bot.py       # Telegram command handlers
│   └── scheduler.py          # APScheduler daily jobs
└── utils/
    └── formatters.py         # Message splitting, number formatting
```

## Setup

### 1. Prerequisites

- Python 3.11+
- A **Polygon.io** subscription (Starter or higher)
- An **Anthropic API key** (Claude Opus access)
- A **Telegram bot token** (create via @BotFather on Telegram)

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

Required variables:

```env
POLYGON_API_KEY=your_polygon_key
ANTHROPIC_API_KEY=your_anthropic_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ALLOWED_CHAT_IDS=your_chat_id
```

To find your Telegram chat ID, message @userinfobot on Telegram.

### 4. Run

```bash
python main.py
```

## Configuration

Edit `.env` to customise:

| Variable | Default | Description |
|---|---|---|
| `MORNING_BRIEF_HOUR` | `7` | Morning brief time (ET, 24h) |
| `MORNING_BRIEF_MINUTE` | `0` | |
| `SCREENER_HOUR` | `6` | Screener run time (ET) |
| `SCREENER_MINUTE` | `30` | |
| `POLYGON_MAX_CONCURRENT` | `5` | Max concurrent API requests |

## Screening Criteria

The screener evaluates ~100 large/mid-cap US stocks across all sectors using a **combined score (0-100)**:

- **Technical score (60%)**: Trend alignment (SMA20/50/200), RSI momentum, MACD direction, volume ratio, proximity to 52-week high
- **Fundamental score (40%)**: Revenue growth, net margin, debt/equity, P/E valuation

Pre-filters: price >= $5, average daily volume >= 300K shares.

## Technical Indicators

All computed with pure pandas/numpy (no external TA library required):

- **Trend**: SMA 20 / 50 / 200
- **Momentum**: RSI(14), MACD(12,26,9)
- **Volatility**: Bollinger Bands(20,2), ATR(14)
- **Volume**: 20-day average, volume ratio
- **Oscillator**: Stochastic %K/%D (14,3)
- **Levels**: Dynamic support/resistance from recent highs/lows

## Morning Brief Format

```
Morning Market Brief
- Major indices (SPY, QQQ, DIA, IWM)
- 11 sector ETFs ranked by performance
- Top 5 gainers + losers
- Top 20 stocks to watch (from screener)
- Claude AI analyst commentary (~600 words)
  - Market tone and opening commentary
  - Sector rotation analysis
  - Top mover narratives
  - Watchlist highlights (top 5 picks explained)
  - Key risks and catalysts for the day
  - Actionable trading strategy
```
