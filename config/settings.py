"""
Configuration and screening criteria settings.
Criteria can be set to None to disable that filter.
"""
import os
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")

# ---------------------------------------------------------------------------
# Predefined screening criteria
# All numeric comparisons are inclusive on the boundary.
# Set any value to None to skip that filter entirely.
# ---------------------------------------------------------------------------

SCREENING_CRITERIA = {
    # --- Valuation ---
    "max_pe":            25,    # Trailing P/E ratio
    "max_pb":             3,    # Price-to-Book
    "max_ps":             5,    # Price-to-Sales
    "max_ev_ebitda":     12,    # EV / EBITDA
    "max_peg":            2,    # PEG ratio

    # --- Profitability ---
    "min_roe":           10,    # Return on Equity (%)
    "min_roa":            5,    # Return on Assets (%)
    "min_gross_margin":  20,    # Gross margin (%)
    "min_operating_margin": 8,  # Operating margin (%)
    "min_net_margin":     5,    # Net profit margin (%)

    # --- Growth ---
    "min_revenue_growth": None, # YoY revenue growth (%) – disabled by default
    "min_eps_growth":    None,  # YoY EPS growth (%) – disabled by default

    # --- Financial Health ---
    "max_debt_equity":    1.0,  # Total debt / equity
    "min_current_ratio":  1.2,  # Current assets / current liabilities
    "min_quick_ratio":   None,  # (Current assets – inventory) / current liabilities

    # --- Dividends (optional) ---
    "min_dividend_yield": None, # Dividend yield (%) – set to e.g. 2 to filter for payers

    # --- Market Cap (USD or SAR) ---
    "min_market_cap":  100_000_000,  # 100 M minimum
    "max_market_cap":   None,        # No upper limit

    # --- Momentum / Price ---
    "min_52w_from_low":  None,  # Stock must be >= N% above 52-week low
    "max_52w_from_high": None,  # Stock must be within N% of 52-week high (e.g. 20 means ≤20% below high)
}

# Screening presets (overrides above)
PRESETS = {
    "value": {
        "max_pe": 15, "max_pb": 1.5, "max_ev_ebitda": 8,
        "min_roe": 12, "max_debt_equity": 0.5, "min_net_margin": 5,
    },
    "growth": {
        "min_revenue_growth": 15, "min_eps_growth": 15,
        "max_pe": 40, "min_gross_margin": 30, "min_roe": 15,
        "min_net_margin": 8,
    },
    "dividend": {
        "min_dividend_yield": 3, "max_pe": 20,
        "max_debt_equity": 0.8, "min_current_ratio": 1.5,
    },
    "quality": {
        "min_roe": 20, "min_roa": 10, "min_gross_margin": 35,
        "min_operating_margin": 15, "max_debt_equity": 0.3,
        "min_current_ratio": 2.0,
    },
}
