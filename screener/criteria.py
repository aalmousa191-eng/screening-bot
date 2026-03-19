"""
Applies screening criteria to a fundamentals dict.
Returns True if the stock passes all active filters.
"""
from __future__ import annotations
from typing import Optional


def _passes(value, min_val=None, max_val=None) -> bool:
    """Check a numeric value against optional min/max bounds."""
    if value is None:
        return False  # Missing data = skip this stock
    if min_val is not None and value < min_val:
        return False
    if max_val is not None and value > max_val:
        return False
    return True


def apply_criteria(stock: dict, criteria: dict) -> tuple[bool, list[str]]:
    """
    Evaluate *stock* against *criteria*.

    Returns:
        (passed: bool, reasons: list[str])  – reasons lists any failed checks.
    """
    failures = []

    checks = [
        # (criteria_key,        stock_key,             mode)
        # mode: "max" or "min"
        ("max_pe",           "pe_trailing",        "max"),
        ("max_pb",           "pb",                 "max"),
        ("max_ps",           "ps_trailing",        "max"),
        ("max_ev_ebitda",    "ev_ebitda",          "max"),
        ("max_peg",          "peg",                "max"),
        ("min_roe",          "roe",                "min"),
        ("min_roa",          "roa",                "min"),
        ("min_gross_margin", "gross_margin",       "min"),
        ("min_operating_margin", "operating_margin", "min"),
        ("min_net_margin",   "net_margin",         "min"),
        ("min_revenue_growth","revenue_growth",    "min"),
        ("min_eps_growth",   "eps_growth",         "min"),
        ("max_debt_equity",  "debt_equity",        "max"),
        ("min_current_ratio","current_ratio",      "min"),
        ("min_quick_ratio",  "quick_ratio",        "min"),
        ("min_dividend_yield","dividend_yield",    "min"),
        ("min_market_cap",   "market_cap",         "min"),
        ("max_market_cap",   "market_cap",         "max"),
    ]

    for crit_key, stock_key, mode in checks:
        threshold = criteria.get(crit_key)
        if threshold is None:
            continue  # Filter disabled

        value = stock.get(stock_key)
        if value is None:
            # Skip this filter if data is unavailable (lenient mode)
            continue

        if mode == "max" and value > threshold:
            failures.append(f"{stock_key}={value:.2f} > max {threshold}")
        elif mode == "min" and value < threshold:
            failures.append(f"{stock_key}={value:.2f} < min {threshold}")

    # 52-week momentum filters
    min_low = criteria.get("min_52w_from_low")
    if min_low is not None:
        val = stock.get("pct_from_52w_low")
        if val is not None and val < min_low:
            failures.append(f"52w_from_low={val:.1f}% < min {min_low}%")

    max_high = criteria.get("max_52w_from_high")
    if max_high is not None:
        val = stock.get("pct_from_52w_high")
        if val is not None and abs(val) > max_high:
            failures.append(f"52w_from_high={val:.1f}% (>{max_high}% below high)")

    return len(failures) == 0, failures


def score_stock(stock: dict) -> float:
    """
    Compute a composite quality/value score (0–100) for ranking results.
    Higher is better.
    """
    score = 0.0
    weights = {
        "roe":               (15, True,  20),   # (weight, higher_is_better, ideal_value)
        "roa":               (10, True,  10),
        "net_margin":        (10, True,  15),
        "operating_margin":  (8,  True,  20),
        "current_ratio":     (7,  True,  2.5),
        "debt_equity":       (10, False, 0),    # lower is better
        "pe_trailing":       (10, False, 10),
        "pb":                (5,  False, 1.5),
        "ev_ebitda":         (5,  False, 8),
        "revenue_growth":    (10, True,  20),
        "fcf_yield":         (10, True,  8),
    }
    # Only sum weights for metrics where data is actually present,
    # so missing fields don't deflate the score.
    active_weight = sum(
        w for key, (w, _, _) in weights.items()
        if stock.get(key) is not None
    )
    if active_weight == 0:
        return 0.0

    for key, (weight, higher_better, ideal) in weights.items():
        val = stock.get(key)
        if val is None:
            continue
        if higher_better:
            normalized = min(val / (ideal * 2), 1.0) if ideal > 0 else 0
        else:
            if ideal == 0:
                # Lower is better, ideal = 0 (e.g. debt_equity): penalise proportionally
                normalized = max(0, 1 - abs(val) / 3)
            elif ideal > 0:
                normalized = max(0, 1 - val / (ideal * 4))
            else:
                normalized = max(0, 1 - abs(val) / 10)

        score += normalized * weight

    return round(score / active_weight * 100, 1)
