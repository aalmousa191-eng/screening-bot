"""
Full fundamental analysis report for a single ticker.
Generates a rich, structured report covering all key investment metrics.
"""
from __future__ import annotations

import yfinance as yf
import pandas as pd
from data.yahoo_client import get_fundamentals


def _pct_str(v) -> str:
    if v is None:
        return "N/A"
    return f"{v:+.2f}%"


def _fmt(v, prefix="", suffix="", decimals=2, billions=False, millions=False) -> str:
    if v is None:
        return "N/A"
    if billions:
        return f"{prefix}{v / 1e9:.2f}B{suffix}"
    if millions:
        return f"{prefix}{v / 1e6:.2f}M{suffix}"
    try:
        return f"{prefix}{v:.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(v)


def _grade(value, thresholds: list[tuple[float, str]]) -> str:
    """
    Assign a letter grade based on thresholds.
    thresholds: [(min_value, grade), ...] sorted ascending.
    """
    if value is None:
        return "N/A"
    for min_v, grade in sorted(thresholds, reverse=True):
        if value >= min_v:
            return grade
    return thresholds[0][1] if thresholds else "N/A"


def get_historical_financials(ticker: str) -> dict:
    """Fetch multi-year income statement, balance sheet, and cash flow data."""
    t = yf.Ticker(ticker)
    result = {}
    try:
        result["income_annual"] = t.financials
        result["income_quarterly"] = t.quarterly_financials
        result["balance_annual"] = t.balance_sheet
        result["balance_quarterly"] = t.quarterly_balance_sheet
        result["cashflow_annual"] = t.cashflow
        result["cashflow_quarterly"] = t.quarterly_cashflow
    except Exception:
        pass
    return result


def _safe_series(df: pd.DataFrame | None, row: str) -> pd.Series | None:
    if df is None or df.empty:
        return None
    if row in df.index:
        return df.loc[row].dropna()
    return None


def build_report(ticker: str) -> dict:
    """
    Build a comprehensive fundamental analysis report.

    Returns a structured dict with sections:
        overview, valuation, profitability, growth, health, cashflow, dividends,
        momentum, analyst, strengths, risks, summary
    """
    stock = get_fundamentals(ticker)
    if "error" in stock:
        return {"error": stock["error"], "ticker": ticker}

    hist = get_historical_financials(ticker)
    inc = hist.get("income_annual")
    bal = hist.get("balance_annual")
    cf = hist.get("cashflow_annual")

    # ---- Multi-year Revenue ----
    rev_series = _safe_series(inc, "Total Revenue")
    rev_history = {}
    if rev_series is not None:
        for date, val in rev_series.items():
            year = str(date)[:4]
            rev_history[year] = val

    # ---- Multi-year Net Income ----
    ni_series = _safe_series(inc, "Net Income")
    ni_history = {}
    if ni_series is not None:
        for date, val in ni_series.items():
            year = str(date)[:4]
            ni_history[year] = val

    # ---- Multi-year EPS ----
    eps_series = _safe_series(inc, "Diluted EPS")
    eps_history = {}
    if eps_series is not None:
        for date, val in eps_series.items():
            year = str(date)[:4]
            eps_history[year] = val

    # ---- Free Cash Flow history ----
    fcf_history = {}
    try:
        if cf is not None and not cf.empty:
            ocf_key = next((k for k in cf.index if "Operating" in k and "Cash" in k), None)
            capex_key = next((k for k in cf.index if "Capital" in k), None)
            if ocf_key and capex_key:
                for date in cf.columns:
                    year = str(date)[:4]
                    ocf = cf.loc[ocf_key, date]
                    capex = cf.loc[capex_key, date]
                    if pd.notna(ocf) and pd.notna(capex):
                        fcf_history[year] = ocf + capex
    except Exception:
        pass

    # ---- Debt history ----
    debt_history = {}
    try:
        if bal is not None and not bal.empty:
            debt_key = next((k for k in bal.index if "Total Debt" in k or "Long Term Debt" in k), None)
            if debt_key:
                for date, val in bal.loc[debt_key].dropna().items():
                    year = str(date)[:4]
                    debt_history[year] = val
    except Exception:
        pass

    # ---- Grading ----
    roe = stock.get("roe")
    roa = stock.get("roa")
    de = stock.get("debt_equity")
    cr = stock.get("current_ratio")
    nm = stock.get("net_margin")
    pe = stock.get("pe_trailing")

    roe_grade = _grade(roe, [(25, "A+"), (20, "A"), (15, "B+"), (10, "B"), (5, "C"), (0, "D")])
    roa_grade = _grade(roa, [(15, "A+"), (10, "A"), (7, "B+"), (5, "B"), (2, "C"), (0, "D")])
    margin_grade = _grade(nm, [(25, "A+"), (20, "A"), (15, "B+"), (10, "B"), (5, "C"), (0, "D")])
    debt_grade = _grade(-de if de is not None else None, [(-0.3, "A+"), (-0.5, "A"), (-1, "B"), (-2, "C"), (-5, "D")]) if de else "N/A"
    liquidity_grade = _grade(cr, [(3, "A+"), (2, "A"), (1.5, "B+"), (1.2, "B"), (1, "C"), (0, "D")]) if cr else "N/A"

    # ---- Strengths & Risks ----
    strengths = []
    risks = []

    if roe and roe >= 15:
        strengths.append(f"Strong return on equity ({roe:.1f}%)")
    if nm and nm >= 10:
        strengths.append(f"Healthy net profit margin ({nm:.1f}%)")
    if stock.get("revenue_growth") and stock["revenue_growth"] >= 10:
        strengths.append(f"Solid revenue growth ({stock['revenue_growth']:.1f}% YoY)")
    if stock.get("fcf_yield") and stock["fcf_yield"] >= 3:
        strengths.append(f"Positive free cash flow yield ({stock['fcf_yield']:.1f}%)")
    if cr and cr >= 2:
        strengths.append(f"Strong liquidity (current ratio {cr:.2f}x)")
    if de is not None and de < 0.5:
        strengths.append(f"Low leverage (D/E {de:.2f}x)")
    if stock.get("dividend_yield") and stock["dividend_yield"] >= 2:
        strengths.append(f"Attractive dividend yield ({stock['dividend_yield']:.1f}%)")
    if stock.get("gross_margin") and stock["gross_margin"] >= 40:
        strengths.append(f"High gross margins ({stock['gross_margin']:.1f}%)")

    if de is not None and de > 2:
        risks.append(f"High debt-to-equity ratio ({de:.2f}x)")
    if cr and cr < 1:
        risks.append(f"Liquidity concern – current ratio below 1 ({cr:.2f}x)")
    if pe and pe > 40:
        risks.append(f"Elevated valuation – P/E {pe:.1f}x")
    if nm and nm < 0:
        risks.append(f"Company is unprofitable (net margin {nm:.1f}%)")
    if stock.get("revenue_growth") and stock["revenue_growth"] < -5:
        risks.append(f"Revenue declining ({stock['revenue_growth']:.1f}% YoY)")
    if stock.get("payout_ratio") and stock["payout_ratio"] > 80:
        risks.append(f"High payout ratio may threaten dividend sustainability ({stock['payout_ratio']:.1f}%)")

    # ---- Upside to analyst target ----
    price = stock.get("price")
    target = stock.get("analyst_target")
    upside = round((target / price - 1) * 100, 1) if price and target else None

    return {
        "ticker": ticker,
        "overview": {
            "name":          stock.get("name", ticker),
            "sector":        stock.get("sector", "N/A"),
            "industry":      stock.get("industry", "N/A"),
            "country":       stock.get("country", "N/A"),
            "exchange":      stock.get("exchange", "N/A"),
            "currency":      stock.get("currency", "USD"),
            "description":   stock.get("description", ""),
            "shares_outstanding": stock.get("shares_outstanding"),
            "float_shares":  stock.get("float_shares"),
        },
        "price_info": {
            "price":          price,
            "market_cap":     stock.get("market_cap"),
            "enterprise_value": stock.get("enterprise_value"),
            "52w_low":        stock.get("52w_low"),
            "52w_high":       stock.get("52w_high"),
            "pct_from_low":   stock.get("pct_from_52w_low"),
            "pct_from_high":  stock.get("pct_from_52w_high"),
            "avg_volume":     stock.get("avg_volume"),
            "beta":           stock.get("beta"),
        },
        "valuation": {
            "pe_trailing":    stock.get("pe_trailing"),
            "pe_forward":     stock.get("pe_forward"),
            "pb":             stock.get("pb"),
            "ps_trailing":    stock.get("ps_trailing"),
            "ev_ebitda":      stock.get("ev_ebitda"),
            "ev_revenue":     stock.get("ev_revenue"),
            "peg":            stock.get("peg"),
        },
        "profitability": {
            "gross_margin":      stock.get("gross_margin"),
            "operating_margin":  stock.get("operating_margin"),
            "net_margin":        stock.get("net_margin"),
            "roe":               roe,
            "roa":               roa,
            "ebitda":            stock.get("ebitda"),
            "grades": {
                "roe":       roe_grade,
                "roa":       roa_grade,
                "margin":    margin_grade,
            },
        },
        "growth": {
            "revenue_growth":  stock.get("revenue_growth"),
            "earnings_growth": stock.get("earnings_growth"),
            "eps_growth":      stock.get("eps_growth"),
            "eps_trailing":    stock.get("eps_trailing"),
            "eps_forward":     stock.get("eps_forward"),
            "revenue_history": rev_history,
            "net_income_history": ni_history,
            "eps_history":     eps_history,
        },
        "financial_health": {
            "current_ratio":  cr,
            "quick_ratio":    stock.get("quick_ratio"),
            "debt_equity":    de,
            "total_debt":     stock.get("total_debt"),
            "total_cash":     stock.get("total_cash"),
            "debt_history":   debt_history,
            "grades": {
                "debt":       debt_grade,
                "liquidity":  liquidity_grade,
            },
        },
        "cashflow": {
            "operating_cf":    stock.get("operating_cf"),
            "capex":           stock.get("capital_expenditure"),
            "fcf":             stock.get("fcf"),
            "fcf_yield":       stock.get("fcf_yield"),
            "fcf_history":     fcf_history,
        },
        "dividends": {
            "yield":           stock.get("dividend_yield"),
            "rate":            stock.get("dividend_rate"),
            "payout_ratio":    stock.get("payout_ratio"),
            "ex_date":         stock.get("ex_dividend_date"),
        },
        "analyst": {
            "target_price":    target,
            "upside_pct":      upside,
            "recommendation":  stock.get("recommendation", "N/A"),
            "analyst_count":   stock.get("analyst_count"),
        },
        "strengths":  strengths,
        "risks":      risks,
        "score":      score_stock(stock),
    }


def score_stock(stock: dict) -> float:
    from screener.criteria import score_stock as _score
    return _score(stock)
