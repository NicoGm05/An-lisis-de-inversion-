"""
portfolio_math.py – All financial calculations. No data invention. N/D on failure.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _nancheck(val):
    """Return None if nan/inf, else return the value."""
    if val is None:
        return None
    try:
        if not np.isfinite(val):
            return None
    except TypeError:
        return None
    return val


def calc_portfolio_returns(prices: pd.DataFrame, weights: dict[str, float]) -> Optional[pd.Series]:
    """
    Weighted daily portfolio returns.
    weights: {ticker: fraction_0_to_1}
    Only uses tickers present in prices. Ignores manual instruments (no price data).
    """
    tickers = [t for t in weights if t in prices.columns]
    if not tickers:
        return None
    w = np.array([weights[t] for t in tickers])
    total_w = w.sum()
    if total_w <= 0:
        return None
    w = w / total_w  # normalize to tickers with price data

    sub = prices[tickers].dropna()
    if len(sub) < 10:
        return None
    daily_ret = sub.pct_change().dropna()
    port_ret = daily_ret.dot(w)
    return port_ret


def calc_portfolio_value(
    prices: pd.DataFrame,
    weights: dict[str, float],
    capital: float = 1_000_000,
) -> Optional[pd.Series]:
    """Cumulative portfolio value starting from `capital`."""
    port_ret = calc_portfolio_returns(prices, weights)
    if port_ret is None:
        return None
    cum = (1 + port_ret).cumprod()
    return cum * capital


def calc_annualized_return(returns: pd.Series) -> Optional[float]:
    if returns is None or len(returns) < 5:
        return None
    return _nancheck(float(returns.mean() * TRADING_DAYS))


def calc_cagr(prices: pd.DataFrame, weights: dict[str, float]) -> tuple[Optional[float], str]:
    """
    CAGR over available period.
    Returns (cagr, warning_str). warning_str is non-empty if < 5 years data.
    """
    port_val = calc_portfolio_value(prices, weights)
    if port_val is None or len(port_val) < 2:
        return None, "Datos insuficientes"
    years = (port_val.index[-1] - port_val.index[0]).days / 365.25
    if years < 0.1:
        return None, "Período muy corto"
    cagr = (port_val.iloc[-1] / port_val.iloc[0]) ** (1 / years) - 1
    warn = ""
    if years < 4.75:
        warn = f"⚠ CAGR calculado con {years:.1f} años de datos (objetivo: 5 años)"
    return _nancheck(float(cagr)), warn


def calc_volatility(returns: pd.Series) -> Optional[float]:
    if returns is None or len(returns) < 5:
        return None
    return _nancheck(float(returns.std() * np.sqrt(TRADING_DAYS)))


def calc_sharpe(
    annualized_return: Optional[float],
    volatility: Optional[float],
    risk_free_rate: float = 0.0,
) -> Optional[float]:
    if annualized_return is None or volatility is None or volatility == 0:
        return None
    return _nancheck((annualized_return - risk_free_rate) / volatility)


def calc_sortino(returns: pd.Series, risk_free_rate: float = 0.0) -> Optional[float]:
    if returns is None or len(returns) < 5:
        return None
    daily_rf = risk_free_rate / TRADING_DAYS
    excess = returns - daily_rf
    downside = excess[excess < 0]
    if len(downside) < 2:
        return None
    downside_std = float(downside.std() * np.sqrt(TRADING_DAYS))
    if downside_std == 0:
        return None
    ann_ret = float(returns.mean() * TRADING_DAYS)
    return _nancheck((ann_ret - risk_free_rate) / downside_std)


def calc_beta_alpha(
    port_returns: pd.Series,
    bench_returns: pd.Series,
    risk_free_rate: float = 0.0,
) -> tuple[Optional[float], Optional[float]]:
    """
    Beta and alpha vs benchmark. Returns (beta, alpha).
    """
    if port_returns is None or bench_returns is None:
        return None, None
    aligned = pd.concat([port_returns, bench_returns], axis=1).dropna()
    if len(aligned) < 10:
        return None, None
    p = aligned.iloc[:, 0]
    b = aligned.iloc[:, 1]
    var_b = float(b.var())
    if var_b == 0:
        return None, None
    cov = float(np.cov(p.values, b.values)[0, 1])
    beta = cov / var_b
    ann_p = float(p.mean() * TRADING_DAYS)
    ann_b = float(b.mean() * TRADING_DAYS)
    alpha = ann_p - risk_free_rate - beta * (ann_b - risk_free_rate)
    return _nancheck(beta), _nancheck(alpha)


def calc_treynor(
    annualized_return: Optional[float],
    beta: Optional[float],
    risk_free_rate: float = 0.0,
) -> Optional[float]:
    if annualized_return is None or beta is None or beta == 0:
        return None
    return _nancheck((annualized_return - risk_free_rate) / beta)


def calc_var(returns: pd.Series, confidence: float = 0.95) -> Optional[float]:
    """Historical VaR at given confidence level (positive value = loss)."""
    if returns is None or len(returns) < 20:
        return None
    q = 1 - confidence
    return _nancheck(float(-np.percentile(returns.dropna(), q * 100)))


def calc_max_drawdown(port_values: pd.Series) -> tuple[Optional[float], Optional[pd.Series]]:
    """
    Max drawdown and drawdown series.
    Returns (max_drawdown, drawdown_series). max_drawdown is a positive value.
    """
    if port_values is None or len(port_values) < 2:
        return None, None
    running_max = port_values.cummax()
    drawdown = (port_values - running_max) / running_max
    max_dd = float(drawdown.min())
    return _nancheck(max_dd), drawdown


def calc_correlation_matrix(prices: pd.DataFrame, weights: dict[str, float]) -> Optional[pd.DataFrame]:
    """Correlation matrix for all tickers with price data in the portfolio."""
    tickers = [t for t in weights if t in prices.columns and weights[t] > 0]
    if len(tickers) < 2:
        return None
    returns = prices[tickers].pct_change().dropna()
    if len(returns) < 10:
        return None
    return returns.corr()


def calc_avg_correlation(corr_matrix: Optional[pd.DataFrame]) -> Optional[float]:
    if corr_matrix is None or corr_matrix.shape[0] < 2:
        return None
    # Average of upper triangle excluding diagonal
    mask = np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
    vals = corr_matrix.values[mask]
    if len(vals) == 0:
        return None
    return _nancheck(float(vals.mean()))


def full_portfolio_metrics(
    prices: pd.DataFrame,
    weights: dict[str, float],
    bench_prices: Optional[pd.DataFrame],
    bench_ticker: str,
    risk_free_rate: float = 0.0,
) -> dict:
    """
    Compute all metrics and return as a flat dict.
    Values are floats or None. Never raises; failures produce None.
    """
    result: dict = {
        "annualized_return": None,
        "cagr": None,
        "cagr_warning": "",
        "volatility": None,
        "sharpe": None,
        "sortino": None,
        "treynor": None,
        "var_95": None,
        "var_99": None,
        "max_drawdown": None,
        "beta": None,
        "alpha": None,
        "avg_correlation": None,
    }
    try:
        port_ret = calc_portfolio_returns(prices, weights)
        if port_ret is None:
            return result

        result["annualized_return"] = calc_annualized_return(port_ret)
        result["volatility"] = calc_volatility(port_ret)

        cagr, cw = calc_cagr(prices, weights)
        result["cagr"] = cagr
        result["cagr_warning"] = cw

        result["sharpe"] = calc_sharpe(result["annualized_return"], result["volatility"], risk_free_rate)
        result["sortino"] = calc_sortino(port_ret, risk_free_rate)
        result["var_95"] = calc_var(port_ret, 0.95)
        result["var_99"] = calc_var(port_ret, 0.99)

        port_val = calc_portfolio_value(prices, weights)
        if port_val is not None:
            md, _ = calc_max_drawdown(port_val)
            result["max_drawdown"] = md

        # Beta / Alpha vs benchmark
        if bench_prices is not None and bench_ticker in bench_prices.columns:
            bench_ret = bench_prices[bench_ticker].pct_change().dropna()
            beta, alpha = calc_beta_alpha(port_ret, bench_ret, risk_free_rate)
            result["beta"] = beta
            result["alpha"] = alpha
            result["treynor"] = calc_treynor(result["annualized_return"], beta, risk_free_rate)

        corr = calc_correlation_matrix(prices, weights)
        result["avg_correlation"] = calc_avg_correlation(corr)
    except Exception:
        pass
    return result
