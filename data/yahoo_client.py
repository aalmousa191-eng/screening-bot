"""
Yahoo Finance data client – works for both US tickers and Saudi tickers (NNNN.SR).
"""
from __future__ import annotations

import time
import yfinance as yf
import pandas as pd
from typing import Optional


def _safe(info: dict, key: str, default=None):
    val = info.get(key, default)
    return val if val not in (None, "N/A", "", "Infinity") else default


def get_fundamentals(ticker: str) -> dict:
    """
    Return a flat dict of fundamental metrics for *ticker*.
    Returns an empty dict if data is unavailable.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        if not info or info.get("trailingPE") is None and info.get("marketCap") is None:
            # Fallback: some tickers return minimal info; try fast_info
            pass

        # ---- Helper for percentage conversion ----
        def pct(v):
            if v is None:
                return None
            return round(v * 100, 2) if abs(v) < 10 else round(v, 2)

        # ---- Revenue growth (trailing 12m vs prior year) ----
        rev_growth = None
        try:
            fin = t.financials  # annual income statement, columns = dates descending
            if fin is not None and not fin.empty and "Total Revenue" in fin.index:
                rev = fin.loc["Total Revenue"].dropna()
                if len(rev) >= 2:
                    rev_growth = round((rev.iloc[0] / rev.iloc[1] - 1) * 100, 2)
        except Exception:
            pass

        # ---- EPS growth ----
        eps_growth = None
        try:
            fin = t.financials
            if fin is not None and not fin.empty and "Diluted EPS" in fin.index:
                eps = fin.loc["Diluted EPS"].dropna()
                if len(eps) >= 2 and eps.iloc[1] and eps.iloc[1] != 0:
                    eps_growth = round((eps.iloc[0] / eps.iloc[1] - 1) * 100, 2)
        except Exception:
            pass

        # ---- FCF ----
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
                    fcf = ocf + capex  # capex is usually negative
                    mc = _safe(info, "marketCap")
                    if mc and mc > 0:
                        fcf_yield = round(fcf / mc * 100, 2)
        except Exception:
            pass

        # ---- 52-week stats ----
        price = _safe(info, "currentPrice") or _safe(info, "regularMarketPrice")
        low52 = _safe(info, "fiftyTwoWeekLow")
        high52 = _safe(info, "fiftyTwoWeekHigh")
        pct_from_low = round((price / low52 - 1) * 100, 2) if price and low52 else None
        pct_from_high = round((price / high52 - 1) * 100, 2) if price and high52 else None  # negative = below high

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
            "beta":              _safe(info, "beta"),

            # Valuation
            "pe_trailing":       _safe(info, "trailingPE"),
            "pe_forward":        _safe(info, "forwardPE"),
            "pb":                _safe(info, "priceToBook"),
            "ps_trailing":       _safe(info, "priceToSalesTrailing12Months"),
            "ev_ebitda":         _safe(info, "enterpriseToEbitda"),
            "ev_revenue":        _safe(info, "enterpriseToRevenue"),
            "peg":               _safe(info, "pegRatio"),

            # Profitability
            "gross_margin":      pct(_safe(info, "grossMargins")),
            "operating_margin":  pct(_safe(info, "operatingMargins")),
            "net_margin":        pct(_safe(info, "profitMargins")),
            "roe":               pct(_safe(info, "returnOnEquity")),
            "roa":               pct(_safe(info, "returnOnAssets")),
            "ebitda":            _safe(info, "ebitda"),

            # Growth
            "revenue_growth":    rev_growth if rev_growth is not None else pct(_safe(info, "revenueGrowth")),
            "earnings_growth":   pct(_safe(info, "earningsGrowth")),
            "eps_growth":        eps_growth,

            # Financial Health
            "current_ratio":     _safe(info, "currentRatio"),
            "quick_ratio":       _safe(info, "quickRatio"),
            "debt_equity":       _safe(info, "debtToEquity"),
            "total_debt":        _safe(info, "totalDebt"),
            "total_cash":        _safe(info, "totalCash"),
            "interest_coverage": None,  # Calculated separately if needed

            # Cash Flow
            "fcf":               fcf,
            "fcf_yield":         fcf_yield,
            "operating_cf":      _safe(info, "operatingCashflow"),
            "capital_expenditure": _safe(info, "capitalExpenditures"),

            # Revenue & Earnings
            "revenue":           _safe(info, "totalRevenue"),
            "gross_profit":      _safe(info, "grossProfits"),
            "ebitda":            _safe(info, "ebitda"),
            "earnings":          _safe(info, "netIncomeToCommon"),
            "eps_trailing":      _safe(info, "trailingEps"),
            "eps_forward":       _safe(info, "forwardEps"),

            # Dividends
            "dividend_yield":    pct(_safe(info, "dividendYield")),
            "dividend_rate":     _safe(info, "dividendRate"),
            "payout_ratio":      pct(_safe(info, "payoutRatio")),
            "ex_dividend_date":  _safe(info, "exDividendDate"),

            # Shares
            "shares_outstanding": _safe(info, "sharesOutstanding"),
            "float_shares":      _safe(info, "floatShares"),
            "short_ratio":       _safe(info, "shortRatio"),

            # Analyst
            "analyst_target":    _safe(info, "targetMeanPrice"),
            "recommendation":    _safe(info, "recommendationKey", "N/A"),
            "analyst_count":     _safe(info, "numberOfAnalystOpinions"),

            # Description
            "description":       _safe(info, "longBusinessSummary", ""),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


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
