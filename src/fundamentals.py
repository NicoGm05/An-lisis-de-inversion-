"""
fundamentals.py – Fetch fundamental ratios from FMP, Finnhub, Alpha Vantage or cache.
Returns N/D for all unavailable fields. Never invents data.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import requests

from src.data_loader import get_cache_path

TIMEOUT = 10


def _load_fund_cache(ticker: str) -> Optional[dict]:
    path = get_cache_path(ticker, "fundamentals")
    if path.exists():
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        if age < timedelta(days=1):
            with open(path, "r") as f:
                return json.load(f)
    return None


def _save_fund_cache(ticker: str, data: dict) -> None:
    path = get_cache_path(ticker, "fundamentals")
    with open(path, "w") as f:
        json.dump(data, f)


def _safe(d: dict, *keys: str, default="N/D") -> Any:
    """Safely navigate nested dict; return default if not found or None."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
        if d is None:
            return default
    return d if d not in (None, "", "None") else default


def _fmt(val: Any, pct: bool = False, mult: float = 1.0) -> str:
    if val == "N/D" or val is None:
        return "N/D"
    try:
        v = float(val) * mult
        return f"{v*100:.2f}%" if pct else f"{v:.4f}"
    except (TypeError, ValueError):
        return "N/D"


def _fetch_fmp(ticker: str, api_key: str) -> dict:
    """Fetch from Financial Modeling Prep /ratios-ttm endpoint."""
    base = "https://financialmodelingprep.com/api/v3"
    out = {}
    try:
        r = requests.get(f"{base}/ratios-ttm/{ticker}?apikey={api_key}", timeout=TIMEOUT)
        data = r.json()
        if isinstance(data, list) and data:
            d = data[0]
            out["pe_ratio"] = _safe(d, "peRatioTTM")
            out["peg_ratio"] = _safe(d, "pegRatioTTM")
            out["roe"] = _safe(d, "returnOnEquityTTM")
            out["roa"] = _safe(d, "returnOnAssetsTTM")
            out["debt_equity"] = _safe(d, "debtEquityRatioTTM")
            out["current_ratio"] = _safe(d, "currentRatioTTM")
            out["quick_ratio"] = _safe(d, "quickRatioTTM")
            out["operating_margin"] = _safe(d, "operatingProfitMarginTTM")
            out["gross_margin"] = _safe(d, "grossProfitMarginTTM")
            out["dividend_yield"] = _safe(d, "dividendYielTTM")
            out["interest_coverage"] = _safe(d, "interestCoverageTTM")
            out["inventory_turnover"] = _safe(d, "inventoryTurnoverTTM")
            out["asset_turnover"] = _safe(d, "assetTurnoverTTM")
    except Exception:
        pass

    # EPS + growth from income statement
    try:
        r2 = requests.get(f"{base}/income-statement/{ticker}?limit=2&apikey={api_key}", timeout=TIMEOUT)
        d2 = r2.json()
        if isinstance(d2, list) and len(d2) >= 1:
            latest = d2[0]
            out["eps"] = _safe(latest, "eps")
            out["revenue"] = _safe(latest, "revenue")
            out["net_income"] = _safe(latest, "netIncome")
            if len(d2) >= 2:
                prev = d2[1]
                try:
                    rev_g = (float(latest["revenue"]) / float(prev["revenue"])) - 1
                    out["revenue_growth"] = rev_g
                except Exception:
                    pass
                try:
                    ni_g = (float(latest["netIncome"]) / float(prev["netIncome"])) - 1
                    out["net_income_growth"] = ni_g
                except Exception:
                    pass
    except Exception:
        pass

    # Total debt
    try:
        r3 = requests.get(f"{base}/balance-sheet-statement/{ticker}?limit=1&apikey={api_key}", timeout=TIMEOUT)
        d3 = r3.json()
        if isinstance(d3, list) and d3:
            out["total_debt"] = _safe(d3[0], "totalDebt")
    except Exception:
        pass

    return out


def _fetch_finnhub(ticker: str, api_key: str) -> dict:
    """Fetch basic metrics from Finnhub as fallback."""
    out = {}
    try:
        r = requests.get(
            f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={api_key}",
            timeout=TIMEOUT,
        )
        d = r.json().get("metric", {})
        if d:
            out["pe_ratio"] = _safe(d, "peNormalizedAnnual")
            out["peg_ratio"] = _safe(d, "pegAnnual")
            out["eps"] = _safe(d, "epsNormalizedAnnual")
            out["roe"] = _safe(d, "roeRfy")
            out["roa"] = _safe(d, "roaRfy")
            out["debt_equity"] = _safe(d, "totalDebt/totalEquityAnnual")
            out["current_ratio"] = _safe(d, "currentRatioAnnual")
            out["dividend_yield"] = _safe(d, "dividendYieldIndicatedAnnual")
            out["gross_margin"] = _safe(d, "grossMarginAnnual")
            out["operating_margin"] = _safe(d, "operatingMarginAnnual")
            out["revenue_growth"] = _safe(d, "revenueGrowthAnnual")
    except Exception:
        pass
    return out


def get_fundamentals(tickers: list[str], config: dict) -> pd.DataFrame:
    """
    Return a DataFrame of fundamental indicators for each ticker.
    Columns: ticker, name, pe_ratio, peg_ratio, eps, revenue_growth,
             net_income_growth, debt_equity, total_debt, interest_coverage,
             current_ratio, quick_ratio, operating_margin, gross_margin,
             roe, roa, dividend_yield, inventory_turnover, asset_turnover,
             source, last_updated.
    All unavailable fields are "N/D".
    """
    import pandas as pd

    fmp_key = config.get("api_keys", {}).get("financial_modeling_prep", "")
    finnhub_key = config.get("api_keys", {}).get("finnhub", "")

    rows = []
    for ticker in tickers:
        # Try cache first
        cached = _load_fund_cache(ticker)
        if cached:
            cached["ticker"] = ticker
            rows.append(cached)
            continue

        data: dict = {}
        source = "N/D"

        # Try FMP
        if fmp_key:
            data = _fetch_fmp(ticker, fmp_key)
            if data:
                source = "FMP"

        # Fallback to Finnhub
        if not data and finnhub_key:
            data = _fetch_finnhub(ticker, finnhub_key)
            if data:
                source = "Finnhub"

        row = {
            "ticker": ticker,
            "pe_ratio": _fmt(data.get("pe_ratio", "N/D")),
            "peg_ratio": _fmt(data.get("peg_ratio", "N/D")),
            "eps": _fmt(data.get("eps", "N/D")),
            "revenue_growth": _fmt(data.get("revenue_growth", "N/D"), pct=True),
            "net_income_growth": _fmt(data.get("net_income_growth", "N/D"), pct=True),
            "debt_equity": _fmt(data.get("debt_equity", "N/D")),
            "total_debt": data.get("total_debt", "N/D"),
            "interest_coverage": _fmt(data.get("interest_coverage", "N/D")),
            "current_ratio": _fmt(data.get("current_ratio", "N/D")),
            "quick_ratio": _fmt(data.get("quick_ratio", "N/D")),
            "operating_margin": _fmt(data.get("operating_margin", "N/D"), pct=True),
            "gross_margin": _fmt(data.get("gross_margin", "N/D"), pct=True),
            "roe": _fmt(data.get("roe", "N/D"), pct=True),
            "roa": _fmt(data.get("roa", "N/D"), pct=True),
            "dividend_yield": _fmt(data.get("dividend_yield", "N/D"), pct=True),
            "inventory_turnover": _fmt(data.get("inventory_turnover", "N/D")),
            "asset_turnover": _fmt(data.get("asset_turnover", "N/D")),
            "source": source,
            "last_updated": datetime.now().strftime("%Y-%m-%d") if source != "N/D" else "N/D",
        }
        if source != "N/D":
            _save_fund_cache(ticker, {k: v for k, v in row.items() if k != "ticker"})
        rows.append(row)

    return pd.DataFrame(rows)
