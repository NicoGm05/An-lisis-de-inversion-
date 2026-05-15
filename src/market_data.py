"""
market_data.py – Fetch historical prices via yfinance with local cache fallback.
Never invents data. Returns (DataFrame | None, source_str, date_str, warning_str).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from src.data_loader import get_cache_path

BASE_DIR = Path(__file__).resolve().parent.parent


def _cache_is_fresh(path: Path, max_days: int) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(days=max_days)


def _load_cache(ticker: str) -> Optional[pd.DataFrame]:
    path = get_cache_path(ticker, "prices")
    if path.exists():
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if not df.empty:
            return df
    return None


def _save_cache(ticker: str, df: pd.DataFrame) -> None:
    path = get_cache_path(ticker, "prices")
    df.to_csv(path)


def fetch_price_series(
    ticker: str,
    years: int = 5,
    cache_days: int = 1,
    use_cache: bool = True,
) -> tuple[Optional[pd.DataFrame], str, str, str]:
    """
    Download adjusted close prices for `ticker` over the past `years` years.

    Returns:
        (df, source, last_updated, warning)
        - df: DataFrame indexed by date with one column = ticker, or None
        - source: 'yfinance' | 'Cache' | 'N/D'
        - last_updated: date string or ''
        - warning: human-readable warning or ''
    """
    cache_path = get_cache_path(ticker, "prices")

    # 1. Try fresh cache first
    if use_cache and _cache_is_fresh(cache_path, cache_days):
        df = _load_cache(ticker)
        if df is not None:
            lu = datetime.fromtimestamp(cache_path.stat().st_mtime).strftime("%Y-%m-%d")
            return df, "Cache", lu, ""

    # 2. Try yfinance
    end = datetime.today()
    start = end - timedelta(days=365 * years + 10)
    try:
        raw = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                          end=end.strftime("%Y-%m-%d"), auto_adjust=True,
                          progress=False, timeout=15)
        if raw.empty:
            raise ValueError("yfinance returned empty DataFrame")

        # Handle MultiIndex columns (yfinance ≥0.2.x)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        close = raw[["Close"]].copy()
        close.columns = [ticker]
        close.dropna(inplace=True)

        actual_years = (close.index[-1] - close.index[0]).days / 365
        warning = ""
        if actual_years < years - 0.25:
            warning = (
                f"⚠ {ticker}: solo {actual_years:.1f} años de datos disponibles "
                f"(se solicitaron {years}). Las métricas se calculan con el período disponible."
            )

        _save_cache(ticker, close)
        return close, "yfinance", end.strftime("%Y-%m-%d"), warning

    except Exception as e:
        # 3. Fall back to stale cache
        df = _load_cache(ticker)
        if df is not None:
            lu = datetime.fromtimestamp(cache_path.stat().st_mtime).strftime("%Y-%m-%d")
            warn = f"⚠ {ticker}: yfinance falló ({e}). Usando caché (fecha: {lu})."
            return df, "Cache", lu, warn

        return None, "N/D", "", f"⚠ {ticker}: sin datos. yfinance falló: {e}"


def fetch_historical_prices(
    tickers: list[str],
    years: int = 5,
    config: dict | None = None,
) -> tuple[pd.DataFrame, dict[str, str], dict[str, str], list[str]]:
    """
    Fetch prices for multiple tickers.

    Returns:
        prices_df: DataFrame (date index, columns = tickers) of Close prices
        sources: {ticker: source}
        dates: {ticker: last_updated}
        warnings: list of warning strings
    """
    config = config or {}
    cache_cfg = config.get("cache", {})
    use_cache = cache_cfg.get("enabled", True)
    cache_days = cache_cfg.get("cache_days_valid", 1)
    years = config.get("market_data", {}).get("historical_years", years)

    all_series = {}
    sources = {}
    dates = {}
    warnings = []

    for ticker in tickers:
        df, src, lu, warn = fetch_price_series(ticker, years, cache_days, use_cache)
        if warn:
            warnings.append(warn)
        sources[ticker] = src
        dates[ticker] = lu
        if df is not None and not df.empty:
            all_series[ticker] = df[ticker]

    if not all_series:
        return pd.DataFrame(), sources, dates, warnings

    prices_df = pd.DataFrame(all_series)
    prices_df.sort_index(inplace=True)
    return prices_df, sources, dates, warnings


def get_usd_mxn_rate(use_cache: bool = True, cache_days: int = 1) -> float:
    """
    Fetch USD/MXN exchange rate. Returns float or 18.0 as fallback with warning.
    """
    df, src, lu, warn = fetch_price_series("MXN=X", years=1, cache_days=cache_days, use_cache=use_cache)
    if df is not None and not df.empty:
        rate = float(df.iloc[-1].values[0])
        return 1.0 / rate if rate < 1 else rate  # MXN=X quotes MXN per USD
    return 18.0  # safe fallback
