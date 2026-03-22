"""Fundamental analysis: parse Polygon financials and compute valuation metrics."""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FundamentalSnapshot:
    ticker: str
    company_name: str = ""
    description: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: float | None = None
    shares_outstanding: float | None = None
    employees: int | None = None

    # Income statement (TTM or latest annual)
    revenue: float | None = None
    revenue_growth_yoy: float | None = None
    gross_profit: float | None = None
    gross_margin: float | None = None
    operating_income: float | None = None
    operating_margin: float | None = None
    net_income: float | None = None
    net_margin: float | None = None
    ebitda: float | None = None
    eps_basic: float | None = None
    eps_diluted: float | None = None

    # Balance sheet
    total_assets: float | None = None
    total_liabilities: float | None = None
    equity: float | None = None
    cash: float | None = None
    total_debt: float | None = None
    debt_to_equity: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None
    current_ratio: float | None = None

    # Cash flow
    operating_cash_flow: float | None = None
    capex: float | None = None
    free_cash_flow: float | None = None

    # Valuation ratios (calculated)
    pe_ratio: float | None = None
    ps_ratio: float | None = None
    pb_ratio: float | None = None
    ev_ebitda: float | None = None
    ev: float | None = None   # enterprise value
    roe: float | None = None  # return on equity
    roa: float | None = None  # return on assets
    fcf_yield: float | None = None

    # Quality flags
    valuation_signal: str = "FAIR"   # CHEAP | FAIR | EXPENSIVE
    quality_score: float = 50.0


def parse_fundamentals(
    ticker: str,
    ticker_details: dict,
    financials_list: list[dict],
    current_price: float = 0.0,
) -> FundamentalSnapshot:
    """Build a FundamentalSnapshot from Polygon API responses."""
    snap = FundamentalSnapshot(ticker=ticker)

    # ── Reference data ─────────────────────────────────────────────────────
    snap.company_name = ticker_details.get("name", ticker)
    snap.description = ticker_details.get("description", "")[:500]
    snap.sector = ticker_details.get("sic_description", "") or ticker_details.get("market", "")
    snap.industry = ticker_details.get("sic_description", "")
    snap.market_cap = _safe_float(ticker_details.get("market_cap"))
    snap.shares_outstanding = _safe_float(ticker_details.get("share_class_shares_outstanding"))
    snap.employees = ticker_details.get("total_employees")

    # ── Financial statements ────────────────────────────────────────────────
    if not financials_list:
        _calculate_ratios(snap, current_price)
        return snap

    # Use most recent filing
    latest = financials_list[0]
    financials = latest.get("financials", {})

    # Income statement
    inc = financials.get("income_statement", {})
    snap.revenue = _fin_val(inc, "revenues") or _fin_val(inc, "net_revenues")
    snap.gross_profit = _fin_val(inc, "gross_profit")
    snap.operating_income = _fin_val(inc, "operating_income_loss")
    snap.net_income = _fin_val(inc, "net_income_loss") or _fin_val(inc, "net_income_loss_attributable_to_parent")
    snap.eps_basic = _fin_val(inc, "basic_earnings_per_share")
    snap.eps_diluted = _fin_val(inc, "diluted_earnings_per_share")

    # Margins
    if snap.revenue and snap.revenue > 0:
        if snap.gross_profit is not None:
            snap.gross_margin = snap.gross_profit / snap.revenue * 100
        if snap.operating_income is not None:
            snap.operating_margin = snap.operating_income / snap.revenue * 100
        if snap.net_income is not None:
            snap.net_margin = snap.net_income / snap.revenue * 100

    # Balance sheet
    bal = financials.get("balance_sheet", {})
    snap.total_assets = _fin_val(bal, "assets")
    snap.total_liabilities = _fin_val(bal, "liabilities")
    snap.equity = _fin_val(bal, "equity") or _fin_val(bal, "equity_attributable_to_parent")
    snap.cash = _fin_val(bal, "cash") or _fin_val(bal, "cash_and_cash_equivalents_including_discontinued_operations")
    snap.current_assets = _fin_val(bal, "current_assets")
    snap.current_liabilities = _fin_val(bal, "current_liabilities")
    snap.total_debt = _fin_val(bal, "long_term_debt") or _fin_val(bal, "long_term_debt_and_capital_lease_obligations")

    if snap.equity and snap.equity > 0:
        snap.debt_to_equity = (snap.total_debt or 0) / snap.equity
        if snap.current_liabilities and snap.current_liabilities > 0 and snap.current_assets:
            snap.current_ratio = snap.current_assets / snap.current_liabilities

    # Cash flow
    cf = financials.get("cash_flow_statement", {})
    snap.operating_cash_flow = _fin_val(cf, "net_cash_flow_from_operating_activities")
    snap.capex = _fin_val(cf, "capital_expenditure")
    if snap.operating_cash_flow is not None and snap.capex is not None:
        snap.free_cash_flow = snap.operating_cash_flow - abs(snap.capex)

    # Revenue growth YoY (compare latest vs. previous year)
    if len(financials_list) >= 2:
        prev_inc = financials_list[1].get("financials", {}).get("income_statement", {})
        prev_revenue = _fin_val(prev_inc, "revenues") or _fin_val(prev_inc, "net_revenues")
        if prev_revenue and prev_revenue > 0 and snap.revenue:
            snap.revenue_growth_yoy = (snap.revenue - prev_revenue) / abs(prev_revenue) * 100

    # EBITDA estimate: operating income + D&A (if not directly available)
    da = _fin_val(inc, "depreciation_and_amortization") or 0
    if snap.operating_income is not None:
        snap.ebitda = snap.operating_income + da

    _calculate_ratios(snap, current_price)
    return snap


def _calculate_ratios(snap: FundamentalSnapshot, price: float) -> None:
    """Calculate valuation ratios from market data and financial data."""
    mc = snap.market_cap

    if mc and mc > 0:
        # P/E
        if snap.net_income and snap.net_income > 0:
            snap.pe_ratio = mc / snap.net_income
        elif snap.eps_basic and snap.eps_basic > 0 and price > 0:
            snap.pe_ratio = price / snap.eps_basic

        # P/S
        if snap.revenue and snap.revenue > 0:
            snap.ps_ratio = mc / snap.revenue

        # P/B
        if snap.equity and snap.equity > 0:
            snap.pb_ratio = mc / snap.equity

        # EV = market_cap + debt - cash
        debt = snap.total_debt or 0
        cash = snap.cash or 0
        snap.ev = mc + debt - cash

        # EV/EBITDA
        if snap.ev and snap.ebitda and snap.ebitda > 0:
            snap.ev_ebitda = snap.ev / snap.ebitda

        # FCF yield
        if snap.free_cash_flow and snap.free_cash_flow > 0:
            snap.fcf_yield = snap.free_cash_flow / mc * 100

    # ROE / ROA
    if snap.net_income and snap.equity and snap.equity > 0:
        snap.roe = snap.net_income / snap.equity * 100
    if snap.net_income and snap.total_assets and snap.total_assets > 0:
        snap.roa = snap.net_income / snap.total_assets * 100

    # Quality score & valuation signal
    snap.quality_score, snap.valuation_signal = _score_fundamentals(snap)


def _score_fundamentals(snap: FundamentalSnapshot) -> tuple[float, str]:
    score = 50.0

    # Growth (20 pts)
    if snap.revenue_growth_yoy is not None:
        if snap.revenue_growth_yoy > 20:
            score += 20
        elif snap.revenue_growth_yoy > 10:
            score += 12
        elif snap.revenue_growth_yoy > 0:
            score += 5
        else:
            score -= 10

    # Profitability (20 pts)
    if snap.net_margin is not None:
        if snap.net_margin > 20:
            score += 15
        elif snap.net_margin > 10:
            score += 8
        elif snap.net_margin > 0:
            score += 3
        else:
            score -= 10

    # Balance sheet (15 pts)
    if snap.debt_to_equity is not None:
        if snap.debt_to_equity < 0.3:
            score += 15
        elif snap.debt_to_equity < 1.0:
            score += 8
        elif snap.debt_to_equity > 3.0:
            score -= 10

    # Valuation signal
    pe = snap.pe_ratio
    if pe is not None:
        if pe < 15:
            valuation = "CHEAP"
            score += 10
        elif pe < 25:
            valuation = "FAIR"
        elif pe < 40:
            valuation = "EXPENSIVE"
            score -= 5
        else:
            valuation = "VERY_EXPENSIVE"
            score -= 15
    elif snap.ps_ratio is not None:
        if snap.ps_ratio < 2:
            valuation = "CHEAP"
        elif snap.ps_ratio < 8:
            valuation = "FAIR"
        else:
            valuation = "EXPENSIVE"
    else:
        valuation = "FAIR"

    score = max(0.0, min(100.0, score))
    return round(score, 1), valuation


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fin_val(statement: dict, key: str) -> float | None:
    """Extract a numeric value from a Polygon financial statement dict."""
    node = statement.get(key)
    if node is None:
        return None
    if isinstance(node, dict):
        val = node.get("value")
        return float(val) if val is not None else None
    return _safe_float(node)


def _safe_float(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _fmt(v: float | None, prefix: str = "", suffix: str = "", decimals: int = 2) -> str:
    if v is None:
        return "N/A"
    return f"{prefix}{v:,.{decimals}f}{suffix}"


def _fmt_large(v: float | None) -> str:
    """Format large dollar amounts as $X.XB / $X.XM."""
    if v is None:
        return "N/A"
    abs_v = abs(v)
    if abs_v >= 1e12:
        return f"${v/1e12:.2f}T"
    if abs_v >= 1e9:
        return f"${v/1e9:.2f}B"
    if abs_v >= 1e6:
        return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"


def format_fundamental_report(snap: FundamentalSnapshot) -> str:
    """Return a formatted HTML fundamental analysis report for Telegram."""
    val_emoji = {"CHEAP": "💚", "FAIR": "🟡", "EXPENSIVE": "🟠", "VERY_EXPENSIVE": "🔴"}
    v_e = val_emoji.get(snap.valuation_signal, "🟡")

    lines = [
        f"<b>📈 FUNDAMENTAL ANALYSIS — {snap.ticker}</b>",
        f"<b>{snap.company_name}</b>",
        f"{snap.industry or snap.sector or 'N/A'}",
        f"",
        f"<b>Valuation:</b> {v_e} {snap.valuation_signal}  |  Score: <b>{snap.quality_score}/100</b>",
        f"",
        f"<b>── MARKET DATA</b>",
        f"Market Cap:       {_fmt_large(snap.market_cap)}",
        f"Enterprise Value: {_fmt_large(snap.ev)}",
        f"Shares Out:       {_fmt_large(snap.shares_outstanding)}",
        f"Employees:        {f'{snap.employees:,}' if snap.employees else 'N/A'}",
        f"",
        f"<b>── INCOME STATEMENT</b>",
        f"Revenue:          {_fmt_large(snap.revenue)}",
        f"Revenue Growth:   {_fmt(snap.revenue_growth_yoy, suffix='%')}",
        f"Gross Profit:     {_fmt_large(snap.gross_profit)}  ({_fmt(snap.gross_margin, suffix='%')} margin)",
        f"Operating Income: {_fmt_large(snap.operating_income)}  ({_fmt(snap.operating_margin, suffix='%')} margin)",
        f"Net Income:       {_fmt_large(snap.net_income)}  ({_fmt(snap.net_margin, suffix='%')} margin)",
        f"EBITDA:           {_fmt_large(snap.ebitda)}",
        f"EPS Basic:        {_fmt(snap.eps_basic, prefix='$')}",
        f"EPS Diluted:      {_fmt(snap.eps_diluted, prefix='$')}",
        f"",
        f"<b>── BALANCE SHEET</b>",
        f"Total Assets:     {_fmt_large(snap.total_assets)}",
        f"Total Debt:       {_fmt_large(snap.total_debt)}",
        f"Cash:             {_fmt_large(snap.cash)}",
        f"Equity:           {_fmt_large(snap.equity)}",
        f"Debt/Equity:      {_fmt(snap.debt_to_equity)}x",
        f"Current Ratio:    {_fmt(snap.current_ratio)}x",
        f"",
        f"<b>── CASH FLOW</b>",
        f"Operating CF:     {_fmt_large(snap.operating_cash_flow)}",
        f"CapEx:            {_fmt_large(snap.capex)}",
        f"Free Cash Flow:   {_fmt_large(snap.free_cash_flow)}",
        f"FCF Yield:        {_fmt(snap.fcf_yield, suffix='%')}",
        f"",
        f"<b>── VALUATION RATIOS</b>",
        f"P/E:      {_fmt(snap.pe_ratio)}x",
        f"P/S:      {_fmt(snap.ps_ratio)}x",
        f"P/B:      {_fmt(snap.pb_ratio)}x",
        f"EV/EBITDA:{_fmt(snap.ev_ebitda)}x",
        f"",
        f"<b>── RETURN METRICS</b>",
        f"ROE: {_fmt(snap.roe, suffix='%')}",
        f"ROA: {_fmt(snap.roa, suffix='%')}",
    ]

    return "\n".join(lines)
