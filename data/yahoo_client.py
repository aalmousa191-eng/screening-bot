"""
Yahoo Finance data client – works for both US tickers and Saudi tickers (NNNN.SR).
"""
from __future__ import annotations

import math
import time
import yfinance as yf
import pandas as pd
from typing import Optional

# ---------------------------------------------------------------------------
# Plausible bounds for each metric.
# Values outside these ranges are treated as bad data and set to None.
# (lo, hi) – use None to skip that side of the check.
# ---------------------------------------------------------------------------
_BOUNDS: dict[str, tuple[Optional[float], Optional[float]]] = {
    "pe_trailing":       (-2000, 2000),   # negative = losses; above 2000 = noise
    "pe_forward":        (-2000, 2000),
    "pb":                (-100,  1000),   # negative = negative equity (flagged separately)
    "ps_trailing":       (0,     1000),
    "ev_ebitda":         (-500,  500),
    "ev_revenue":        (0,     1000),
    "peg":               (-100,  200),
    "gross_margin":      (-500,  100),    # cannot exceed 100 %
    "operating_margin":  (-500,  100),
    "net_margin":        (-500,  100),
    "roe":               (-1000, 1000),   # extreme leverage can cause huge ROE
    "roa":               (-200,  200),
    "dividend_yield":    (0,     100),    # >100 % is almost always stale/bad data
    "payout_ratio":      (0,     2000),
    "debt_equity":       (None,  2000),   # Yahoo can return negatives (neg. equity)
    "current_ratio":     (0,     200),
    "quick_ratio":       (0,     200),
    "revenue_growth":    (-100,  5000),   # cap runaway small-cap spikes
    "earnings_growth":   (-100,  5000),
    "eps_growth":        (-100,  5000),
    "fcf_yield":         (-500,  500),
    "beta":              (-10,   20),
}

# Fields where a negative value is suspicious enough to null out entirely
_MUST_BE_POSITIVE = {"ps_trailing", "ev_revenue", "dividend_yield",
                     "current_ratio", "quick_ratio"}


def _safe(info: dict, key: str, default=None):
    val = info.get(key, default)
    if val in (None, "N/A", "", "Infinity", float("inf"), float("-inf")):
        return default
    try:
        if math.isnan(float(val)):
            return default
    except (TypeError, ValueError):
        pass
    return val


def _clamp(val: float | None, key: str) -> float | None:
    """Return val if within _BOUNDS[key], else None."""
    if val is None:
        return None
    bounds = _BOUNDS.get(key)
    if bounds is None:
        return val
    lo, hi = bounds
    if lo is not None and val < lo:
        return None
    if hi is not None and val > hi:
        return None
    if key in _MUST_BE_POSITIVE and val < 0:
        return None
    return val


def _is_not_found(info: dict, ticker: str) -> bool:
    """
    Return True when Yahoo Finance returned a stub/empty record.
    Signals: no price data at all and no market cap.
    """
    if not info:
        return True
    # Yahoo returns {"quoteType": "NONE", "symbol": "..."} for delisted/invalid
    if info.get("quoteType", "").upper() == "NONE":
        return True
    # No price or market cap → not a real equity record
    has_price = any(info.get(k) for k in ("currentPrice", "regularMarketPrice",
                                           "previousClose", "open"))
    has_cap = bool(info.get("marketCap"))
    if not has_price and not has_cap:
        return True
    return False


def get_fundamentals(ticker: str) -> dict:
    """
    Return a flat dict of fundamental metrics for *ticker*.

    Returns {"ticker": ..., "error": ..., "not_found": True/False} on failure.
    All returned numeric fields are validated against plausible bounds; values
    outside those bounds are set to None rather than propagated as garbage.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        if _is_not_found(info, ticker):
            return {"ticker": ticker, "error": "ticker not found", "not_found": True}

        # ---- Helper: percentage from decimal ----
        def pct(v):
            if v is None:
                return None
            try:
                f = float(v)
                if math.isnan(f) or math.isinf(f):
                    return None
                # Yahoo returns fractions like 0.15 for 15%; values already > 10
                # are assumed to already be in percent form
                return round(f * 100, 2) if abs(f) <= 10 else round(f, 2)
            except (TypeError, ValueError):
                return None

        # ---- Revenue growth ----
        rev_growth = None
        try:
            fin = t.financials
            if fin is not None and not fin.empty and "Total Revenue" in fin.index:
                rev = fin.loc["Total Revenue"].dropna()
                if len(rev) >= 2:
                    prior = rev.iloc[1]
                    if prior and prior != 0:
                        rev_growth = round((rev.iloc[0] / prior - 1) * 100, 2)
        except Exception:
            pass

        # ---- EPS growth ----
        eps_growth = None
        try:
            fin = t.financials
            if fin is not None and not fin.empty and "Diluted EPS" in fin.index:
                eps = fin.loc["Diluted EPS"].dropna()
                if len(eps) >= 2:
                    prior_eps = eps.iloc[1]
                    if prior_eps and prior_eps != 0 and not math.isnan(float(prior_eps)):
                        eps_growth = round((eps.iloc[0] / prior_eps - 1) * 100, 2)
        except Exception:
            pass

        # ---- FCF & FCF yield ----
        fcf = None
        fcf_yield = None
        try:
            cf = t.cashflow
            if cf is not None and not cf.empty:
                ocf_key = next((k for k in cf.index if "Operating" in k and "Cash" in k), None)
                capex_key = next((k for k in cf.index if "Capital" in k), None)
                if ocf_key and capex_key:
                    ocf = cf.loc[ocf_key].iloc[0]
                    capex = cf.loc[capex_key].iloc[0]
                    if pd.notna(ocf) and pd.notna(capex):
                        fcf = float(ocf) + float(capex)
                        mc = _safe(info, "marketCap")
                        if mc and mc > 0 and not math.isnan(fcf):
                            fcf_yield = round(fcf / mc * 100, 2)
        except Exception:
            pass

        # ---- 52-week momentum ----
        price  = _safe(info, "currentPrice") or _safe(info, "regularMarketPrice")
        low52  = _safe(info, "fiftyTwoWeekLow")
        high52 = _safe(info, "fiftyTwoWeekHigh")

        pct_from_low  = None
        pct_from_high = None
        if price and low52 and low52 > 0:
            pct_from_low = round((price / low52 - 1) * 100, 2)
        if price and high52 and high52 > 0:
            pct_from_high = round((price / high52 - 1) * 100, 2)

        # ---- Raw metric extraction ----
        raw = {
            # Valuation
            "pe_trailing":    _safe(info, "trailingPE"),
            "pe_forward":     _safe(info, "forwardPE"),
            "pb":             _safe(info, "priceToBook"),
            "ps_trailing":    _safe(info, "priceToSalesTrailing12Months"),
            "ev_ebitda":      _safe(info, "enterpriseToEbitda"),
            "ev_revenue":     _safe(info, "enterpriseToRevenue"),
            "peg":            _safe(info, "pegRatio"),
            # Profitability
            "gross_margin":   pct(_safe(info, "grossMargins")),
            "operating_margin": pct(_safe(info, "operatingMargins")),
            "net_margin":     pct(_safe(info, "profitMargins")),
            "roe":            pct(_safe(info, "returnOnEquity")),
            "roa":            pct(_safe(info, "returnOnAssets")),
            # Growth
            "revenue_growth": rev_growth if rev_growth is not None
                              else pct(_safe(info, "revenueGrowth")),
            "earnings_growth": pct(_safe(info, "earningsGrowth")),
            "eps_growth":     eps_growth,
            # Health
            "current_ratio":  _safe(info, "currentRatio"),
            "quick_ratio":    _safe(info, "quickRatio"),
            "debt_equity":    _safe(info, "debtToEquity"),
            # Dividends
            "dividend_yield": pct(_safe(info, "dividendYield")),
            "payout_ratio":   pct(_safe(info, "payoutRatio")),
            # Momentum
            "fcf_yield":      fcf_yield,
            "beta":           _safe(info, "beta"),
        }

        # ---- Apply bounds validation to every ratio ----
        sanitized = {k: _clamp(v, k) for k, v in raw.items()}

        # ---- Flag anomalies (for transparency) ----
        warnings: list[str] = []
        for k, raw_v in raw.items():
            if raw_v is not None and sanitized[k] is None:
                warnings.append(f"{k}={raw_v} out of bounds")

        # Negative equity warning
        de = sanitized.get("debt_equity")
        if de is not None and de < 0:
            warnings.append(f"negative equity (D/E={de:.2f})")

        return {
            # Identity
            "ticker":            ticker,
            "name":              _safe(info, "longName") or _safe(info, "shortName", ticker),
            "sector":            _safe(info, "sector", "N/A"),
            "industry":          _safe(info, "industry", "N/A"),
            "country":           _safe(info, "country", "N/A"),
            "currency":          _safe(info, "currency", "USD"),
            "exchange":          _safe(info, "exchange", "N/A"),

            # Price & Market Cap
            "price":             price,
            "market_cap":        _safe(info, "marketCap"),
            "enterprise_value":  _safe(info, "enterpriseValue"),
            "52w_low":           low52,
            "52w_high":          high52,
            "pct_from_52w_low":  pct_from_low,
            "pct_from_52w_high": pct_from_high,
            "avg_volume":        _safe(info, "averageVolume"),

            # Validated ratios
            **sanitized,

            # Absolute financials (no clamping – raw scale)
            "ebitda":            _safe(info, "ebitda"),
            "revenue":           _safe(info, "totalRevenue"),
            "gross_profit":      _safe(info, "grossProfits"),
            "earnings":          _safe(info, "netIncomeToCommon"),
            "eps_trailing":      _safe(info, "trailingEps"),
            "eps_forward":       _safe(info, "forwardEps"),
            "total_debt":        _safe(info, "totalDebt"),
            "total_cash":        _safe(info, "totalCash"),
            "fcf":               fcf,
            "operating_cf":      _safe(info, "operatingCashflow"),
            "capital_expenditure": _safe(info, "capitalExpenditures"),
            "dividend_rate":     _safe(info, "dividendRate"),
            "ex_dividend_date":  _safe(info, "exDividendDate"),
            "shares_outstanding": _safe(info, "sharesOutstanding"),
            "float_shares":      _safe(info, "floatShares"),
            "short_ratio":       _safe(info, "shortRatio"),
            "analyst_target":    _safe(info, "targetMeanPrice"),
            "recommendation":    _safe(info, "recommendationKey", "N/A"),
            "analyst_count":     _safe(info, "numberOfAnalystOpinions"),
            "description":       _safe(info, "longBusinessSummary", ""),

            # Metadata
            "data_warnings":     warnings,
        }

    except Exception as e:
        return {"ticker": ticker, "error": str(e), "not_found": False}


def batch_fundamentals(tickers: list[str], delay: float = 0.3) -> list[dict]:
    """Fetch fundamentals for a list of tickers with rate-limit delay."""
    results = []
    for i, ticker in enumerate(tickers):
        data = get_fundamentals(ticker)
        if "error" not in data:
            results.append(data)
        if i < len(tickers) - 1:
            time.sleep(delay)
    return results
