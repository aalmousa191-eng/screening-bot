import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    POLYGON_API_KEY: str = os.environ["POLYGON_API_KEY"]
    ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
    TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

    ALLOWED_CHAT_IDS: list[int] = [
        int(x.strip())
        for x in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")
        if x.strip().lstrip("-").isdigit()
    ]

    MORNING_BRIEF_HOUR: int = int(os.getenv("MORNING_BRIEF_HOUR", "7"))
    MORNING_BRIEF_MINUTE: int = int(os.getenv("MORNING_BRIEF_MINUTE", "0"))
    SCREENER_HOUR: int = int(os.getenv("SCREENER_HOUR", "6"))
    SCREENER_MINUTE: int = int(os.getenv("SCREENER_MINUTE", "30"))

    POLYGON_MAX_CONCURRENT: int = int(os.getenv("POLYGON_MAX_CONCURRENT", "5"))
    POLYGON_BASE_URL: str = "https://api.polygon.io"

    # Screening universe: top ~100 liquid US stocks across sectors
    SCREENER_UNIVERSE: list[str] = [
        # Technology
        "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD", "ORCL",
        "CRM", "ADBE", "AVGO", "QCOM", "TXN", "MU", "AMAT", "LRCX", "PANW",
        "SNOW", "PLTR", "NET", "DDOG", "ZS", "CRWD", "FTNT", "NOW", "WDAY",
        # Healthcare
        "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT", "MDT",
        "BMY", "AMGN", "GILD", "REGN", "VRTX", "ISRG", "BSX", "ZTS", "DXCM",
        # Finance
        "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "BLK",
        "SCHW", "CB", "MMC", "PGR", "COF", "USB", "SPGI", "ICE", "CME",
        # Consumer Discretionary
        "HD", "MCD", "SBUX", "NKE", "LOW", "TGT", "COST", "BKNG", "MAR",
        "ABNB", "LVS", "ROST", "YUM", "DG", "EBAY",
        # Consumer Staples
        "WMT", "PG", "KO", "PEP", "PM", "EL", "CL", "GIS", "K",
        # Energy
        "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HAL",
        # Industrials
        "HON", "UPS", "CAT", "DE", "GE", "RTX", "LMT", "NOC", "BA",
        "ETN", "EMR", "PH", "ITW", "FDX", "CSX", "UNP",
        # Communications
        "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "EA", "TTWO",
        # Materials
        "LIN", "APD", "SHW", "NEM", "FCX", "NUE",
        # Utilities & REIT
        "NEE", "DUK", "AMT", "PLD", "EQIX",
    ]

    # Market indices (ETF proxies)
    INDEX_TICKERS: dict[str, str] = {
        "S&P 500": "SPY",
        "NASDAQ 100": "QQQ",
        "Dow Jones": "DIA",
        "Russell 2000": "IWM",
        "VIX": "VIXY",
    }

    # Sector ETFs
    SECTOR_TICKERS: dict[str, str] = {
        "Technology": "XLK",
        "Healthcare": "XLV",
        "Financials": "XLF",
        "Consumer Disc.": "XLY",
        "Consumer Staples": "XLP",
        "Energy": "XLE",
        "Industrials": "XLI",
        "Materials": "XLB",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Communications": "XLC",
    }


config = Config()
