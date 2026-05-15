"""
data_loader.py – CSV I/O: universe, manual fixed income, portfolios.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def load_assets_universe() -> pd.DataFrame:
    """Load and type-cast assets_universe.csv."""
    path = DATA_DIR / "assets_universe.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str)
    # Cast boolean columns
    bool_cols = [
        "is_equity", "is_fixed_income", "is_etf", "is_adr",
        "is_inverse", "is_leveraged", "is_allowed", "requires_manual_data",
    ]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].map({"1": True, "0": False, "True": True, "False": False}).fillna(False)
    df["ticker"] = df["ticker"].str.strip()
    df["name"] = df["name"].str.strip()
    return df


def load_manual_fixed_income() -> pd.DataFrame:
    """Load manual_fixed_income.csv and return DataFrame."""
    path = DATA_DIR / "manual_fixed_income.csv"
    if not path.exists():
        return pd.DataFrame(columns=[
            "instrument_key", "name", "annual_yield", "duration",
            "maturity", "currency", "risk_level", "source_notes", "last_updated",
        ])
    df = pd.read_csv(path, dtype=str)
    df["annual_yield"] = pd.to_numeric(df["annual_yield"], errors="coerce")
    return df


def save_manual_fixed_income(df: pd.DataFrame) -> None:
    path = DATA_DIR / "manual_fixed_income.csv"
    df.to_csv(path, index=False)


def load_portfolios() -> pd.DataFrame:
    """Load all saved portfolios."""
    path = DATA_DIR / "portfolios.csv"
    if not path.exists() or path.stat().st_size < 10:
        return pd.DataFrame(columns=["portfolio_id", "portfolio_name", "ticker", "weight", "notes", "last_modified"])
    return pd.read_csv(path, dtype=str)


def save_portfolio(portfolio_name: str, portfolio: dict) -> None:
    """
    Save a portfolio dict {ticker: {weight, notes, ...}} to portfolios.csv.
    Replaces any existing rows for this portfolio_name.
    """
    path = DATA_DIR / "portfolios.csv"
    existing = load_portfolios()
    # Remove old rows for this portfolio
    existing = existing[existing["portfolio_name"] != portfolio_name].copy()
    rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for ticker, info in portfolio.items():
        rows.append({
            "portfolio_id": portfolio_name,
            "portfolio_name": portfolio_name,
            "ticker": ticker,
            "weight": info.get("weight", 0.0),
            "notes": info.get("notes", ""),
            "last_modified": now,
        })
    new_df = pd.DataFrame(rows)
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined.to_csv(path, index=False)


def load_portfolio_by_name(portfolio_name: str) -> dict:
    """
    Load a specific portfolio from portfolios.csv.
    Returns {ticker: {weight: float, notes: str}} or empty dict.
    """
    all_pf = load_portfolios()
    pf = all_pf[all_pf["portfolio_name"] == portfolio_name]
    result = {}
    for _, row in pf.iterrows():
        try:
            weight = float(row["weight"])
        except (ValueError, TypeError):
            weight = 0.0
        result[row["ticker"]] = {
            "weight": weight,
            "notes": str(row.get("notes", "")),
        }
    return result


def list_portfolio_names() -> list[str]:
    all_pf = load_portfolios()
    defaults = ["Portafolio A", "Portafolio B", "Portafolio C", "Portafolio Final"]
    saved = all_pf["portfolio_name"].dropna().unique().tolist()
    combined = defaults + [s for s in saved if s not in defaults]
    return combined


def get_cache_path(ticker: str, kind: str = "prices") -> Path:
    cache_dir = BASE_DIR / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe = ticker.replace(".", "_").replace("/", "_").replace("^", "_")
    ext = "csv" if kind == "prices" else "json"
    return cache_dir / f"{kind}_{safe}.{ext}"
