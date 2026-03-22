"""Technical analysis: indicators computed with pure pandas/numpy."""
import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TechnicalSnapshot:
    ticker: str
    price: float
    change_pct: float

    # Trend
    sma20: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    above_sma20: bool | None = None
    above_sma50: bool | None = None
    above_sma200: bool | None = None
    trend_signal: str = "NEUTRAL"

    # Momentum
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    macd_bullish: bool | None = None
    momentum_signal: str = "NEUTRAL"

    # Volatility
    bb_upper: float | None = None
    bb_lower: float | None = None
    bb_pct: float | None = None
    atr: float | None = None
    atr_pct: float | None = None

    # Volume
    volume: float | None = None
    avg_volume_20d: float | None = None
    volume_ratio: float | None = None

    # Stochastic
    stoch_k: float | None = None
    stoch_d: float | None = None

    # 52-week range
    week52_high: float | None = None
    week52_low: float | None = None
    pct_from_52w_high: float | None = None

    # Overall
    overall_signal: str = "NEUTRAL"
    score: float = 50.0
    key_levels: dict[str, float] = field(default_factory=dict)


# ── Pure-pandas indicator calculations ───────────────────────────────────────

def _sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n).mean()


def _ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def _rsi(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(n).mean()
    loss = (-delta.clip(upper=0)).rolling(n).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def _bollinger(series: pd.Series, n: int = 20, std: float = 2.0):
    mid = _sma(series, n)
    sigma = series.rolling(n).std()
    upper = mid + std * sigma
    lower = mid - std * sigma
    return upper, mid, lower


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                k_period: int = 14, d_period: int = 3) -> tuple[pd.Series, pd.Series]:
    low_min = low.rolling(k_period).min()
    high_max = high.rolling(k_period).max()
    stoch_k = 100 * (close - low_min) / (high_max - low_min).replace(0, np.nan)
    stoch_d = stoch_k.rolling(d_period).mean()
    return stoch_k, stoch_d


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to an OHLCV DataFrame in-place copy."""
    if df.empty or len(df) < 20:
        return df
    df = df.copy()
    c = df["close"]
    h, l, v = df["high"], df["low"], df["volume"]

    df["SMA_20"] = _sma(c, 20)
    df["SMA_50"] = _sma(c, 50)
    df["SMA_200"] = _sma(c, 200)
    df["RSI_14"] = _rsi(c, 14)

    macd_line, signal_line, hist = _macd(c)
    df["MACD"] = macd_line
    df["MACD_signal"] = signal_line
    df["MACD_hist"] = hist

    bb_upper, bb_mid, bb_lower = _bollinger(c, 20, 2.0)
    df["BB_upper"] = bb_upper
    df["BB_mid"] = bb_mid
    df["BB_lower"] = bb_lower

    df["ATR_14"] = _atr(h, l, c, 14)
    df["vol_sma20"] = _sma(v, 20)
    df["vol_ratio"] = v / df["vol_sma20"]

    stoch_k, stoch_d = _stochastic(h, l, c)
    df["STOCH_K"] = stoch_k
    df["STOCH_D"] = stoch_d

    return df


def build_snapshot(ticker: str, df: pd.DataFrame) -> TechnicalSnapshot:
    """Build a TechnicalSnapshot from a calculated DataFrame."""
    if df.empty:
        return TechnicalSnapshot(ticker=ticker, price=0.0, change_pct=0.0)

    row = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else row
    price = float(row["close"])
    prev_close = float(prev["close"])
    change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0

    snap = TechnicalSnapshot(ticker=ticker, price=price, change_pct=change_pct)

    def _v(col: str) -> float | None:
        val = row.get(col)
        return float(val) if val is not None and not (isinstance(val, float) and np.isnan(val)) else None

    # Trend
    snap.sma20 = _v("SMA_20")
    snap.sma50 = _v("SMA_50")
    snap.sma200 = _v("SMA_200")
    if snap.sma20 is not None:
        snap.above_sma20 = price > snap.sma20
    if snap.sma50 is not None:
        snap.above_sma50 = price > snap.sma50
    if snap.sma200 is not None:
        snap.above_sma200 = price > snap.sma200
    snap.trend_signal = _trend_signal(snap)

    # Momentum
    snap.rsi = _v("RSI_14")
    snap.macd = _v("MACD")
    snap.macd_signal = _v("MACD_signal")
    snap.macd_hist = _v("MACD_hist")
    if snap.macd_hist is not None:
        prev_hist = df["MACD_hist"].iloc[-2] if len(df) > 1 else None
        prev_hist_f = float(prev_hist) if prev_hist is not None and not (isinstance(prev_hist, float) and np.isnan(prev_hist)) else None
        snap.macd_bullish = snap.macd_hist > 0 and (prev_hist_f is None or snap.macd_hist > prev_hist_f)
    snap.momentum_signal = _momentum_signal(snap)

    # Volatility
    snap.bb_upper = _v("BB_upper")
    snap.bb_lower = _v("BB_lower")
    if snap.bb_upper and snap.bb_lower and snap.bb_upper != snap.bb_lower:
        snap.bb_pct = (price - snap.bb_lower) / (snap.bb_upper - snap.bb_lower)
    snap.atr = _v("ATR_14")
    if snap.atr:
        snap.atr_pct = snap.atr / price * 100

    # Volume
    snap.volume = float(row["volume"])
    snap.avg_volume_20d = _v("vol_sma20")
    snap.volume_ratio = _v("vol_ratio")

    # Stochastic
    snap.stoch_k = _v("STOCH_K")
    snap.stoch_d = _v("STOCH_D")

    # 52-week range
    n_days = min(252, len(df))
    snap.week52_high = float(df["high"].tail(n_days).max())
    snap.week52_low = float(df["low"].tail(n_days).min())
    if snap.week52_high:
        snap.pct_from_52w_high = (price - snap.week52_high) / snap.week52_high * 100

    snap.key_levels = _find_key_levels(df)
    snap.score, snap.overall_signal = _overall_score(snap)

    return snap


def _trend_signal(snap: TechnicalSnapshot) -> str:
    flags = [snap.above_sma20, snap.above_sma50, snap.above_sma200]
    valid = [f for f in flags if f is not None]
    if not valid:
        return "NEUTRAL"
    bull = sum(valid)
    total = len(valid)
    if bull == total:
        return "STRONG_BULLISH"
    if bull >= total - 1:
        return "BULLISH"
    if bull == 1:
        return "BEARISH"
    return "STRONG_BEARISH"


def _momentum_signal(snap: TechnicalSnapshot) -> str:
    rsi = snap.rsi
    if rsi is None:
        return "NEUTRAL"
    if rsi > 70:
        return "OVERBOUGHT"
    if rsi < 30:
        return "OVERSOLD"
    if rsi > 55 and snap.macd_bullish:
        return "BULLISH"
    if rsi < 45 and snap.macd_bullish is False:
        return "BEARISH"
    return "NEUTRAL"


def _overall_score(snap: TechnicalSnapshot) -> tuple[float, str]:
    score = 50.0
    trend_map = {"STRONG_BULLISH": 40, "BULLISH": 30, "NEUTRAL": 20, "BEARISH": 10, "STRONG_BEARISH": 0}
    score += trend_map.get(snap.trend_signal, 20) - 20

    if snap.rsi is not None:
        if 50 <= snap.rsi <= 70:
            score += 15
        elif snap.rsi < 50:
            score -= 10
    if snap.macd_bullish:
        score += 10
    elif snap.macd_bullish is False:
        score -= 10

    if snap.volume_ratio is not None:
        if snap.volume_ratio > 1.5:
            score += 10
        elif snap.volume_ratio > 1.0:
            score += 5
        elif snap.volume_ratio < 0.5:
            score -= 10

    if snap.pct_from_52w_high is not None:
        if snap.pct_from_52w_high >= -10:
            score += 15
        elif snap.pct_from_52w_high >= -25:
            score += 7
        else:
            score -= 5

    score = max(0.0, min(100.0, score))
    if score >= 75:
        signal = "STRONG_BUY"
    elif score >= 60:
        signal = "BUY"
    elif score >= 45:
        signal = "NEUTRAL"
    elif score >= 30:
        signal = "SELL"
    else:
        signal = "STRONG_SELL"
    return round(score, 1), signal


def _find_key_levels(df: pd.DataFrame) -> dict[str, float]:
    levels: dict[str, float] = {}
    if len(df) < 20:
        return levels
    price = float(df["close"].iloc[-1])
    recent = df.tail(60)
    resistances = [h for h in recent["high"].nlargest(5).values if h > price]
    supports = [l for l in recent["low"].nsmallest(5).values if l < price]
    if resistances:
        levels["resistance1"] = round(min(resistances), 2)
    if supports:
        levels["support1"] = round(max(supports), 2)
    return levels


def format_technical_report(snap: TechnicalSnapshot) -> str:
    """Formatted HTML technical analysis report for Telegram."""
    def pct_str(v: float | None) -> str:
        return f"{v:+.2f}%" if v is not None else "N/A"
    def p(v: float | None) -> str:
        return f"${v:,.2f}" if v is not None else "N/A"
    def f1(v: float | None) -> str:
        return f"{v:.1f}" if v is not None else "N/A"
    def f3(v: float | None) -> str:
        return f"{v:+.3f}" if v is not None else "N/A"

    sig_e = {"STRONG_BUY": "🟢🟢", "BUY": "🟢", "NEUTRAL": "🟡", "SELL": "🔴", "STRONG_SELL": "🔴🔴"}
    trend_e = {"STRONG_BULLISH": "📈📈", "BULLISH": "📈", "NEUTRAL": "➡️", "BEARISH": "📉", "STRONG_BEARISH": "📉📉"}
    mom_e = {"BULLISH": "⬆️", "OVERBOUGHT": "⚠️", "OVERSOLD": "⚠️", "BEARISH": "⬇️", "NEUTRAL": "➡️"}

    ch = "▲" if snap.change_pct >= 0 else "▼"
    lines = [
        f"<b>📊 TECHNICAL ANALYSIS — {snap.ticker}</b>",
        "",
        f"<b>Price:</b> {p(snap.price)}  {ch} {snap.change_pct:+.2f}%",
        f"<b>Signal:</b> {sig_e.get(snap.overall_signal,'🟡')} {snap.overall_signal}  |  Score: <b>{snap.score}/100</b>",
        "",
        f"<b>── TREND {trend_e.get(snap.trend_signal,'')}</b>",
        f"20-Day SMA:  {p(snap.sma20)}  {'✅' if snap.above_sma20 else '❌'}",
        f"50-Day SMA:  {p(snap.sma50)}  {'✅' if snap.above_sma50 else '❌'}",
        f"200-Day SMA: {p(snap.sma200)}  {'✅' if snap.above_sma200 else '❌'}",
        "",
        f"<b>── MOMENTUM {mom_e.get(snap.momentum_signal,'')}</b>",
        f"RSI (14):    {f1(snap.rsi)}",
        f"MACD:        {f3(snap.macd)}  Signal: {f3(snap.macd_signal)}",
        f"MACD Hist:   {f3(snap.macd_hist)}  {'🟢 Bullish' if snap.macd_bullish else '🔴 Bearish' if snap.macd_bullish is False else ''}",
        f"Stoch %K/%D: {f1(snap.stoch_k)} / {f1(snap.stoch_d)}",
        "",
        f"<b>── VOLATILITY</b>",
        f"Bollinger:   {p(snap.bb_lower)} — {p(snap.bb_upper)}",
        f"BB %B:       {f'{snap.bb_pct:.2f}' if snap.bb_pct is not None else 'N/A'}",
        f"ATR (14):    {f'{snap.atr:.2f}' if snap.atr else 'N/A'}  ({pct_str(snap.atr_pct)} of price)",
        "",
        f"<b>── VOLUME</b>",
        f"Today:       {f'{snap.volume:,.0f}' if snap.volume else 'N/A'}",
        f"20d Avg:     {f'{snap.avg_volume_20d:,.0f}' if snap.avg_volume_20d else 'N/A'}",
        f"Ratio:       {f'{snap.volume_ratio:.2f}x' if snap.volume_ratio else 'N/A'}  {'🔥 Heavy' if snap.volume_ratio and snap.volume_ratio > 1.5 else '📉 Light' if snap.volume_ratio and snap.volume_ratio < 0.7 else ''}",
        "",
        f"<b>── 52-WEEK RANGE</b>",
        f"High: {p(snap.week52_high)}   Low: {p(snap.week52_low)}",
        f"From 52w High: {pct_str(snap.pct_from_52w_high)}",
    ]
    if snap.key_levels:
        lines += ["", "<b>── KEY LEVELS</b>"]
        if "resistance1" in snap.key_levels:
            lines.append(f"Resistance: {p(snap.key_levels['resistance1'])}")
        if "support1" in snap.key_levels:
            lines.append(f"Support:    {p(snap.key_levels['support1'])}")
    return "\n".join(lines)
