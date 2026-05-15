"""
validations.py – Portfolio rule validation. Returns structured result list.
Each rule: {rule, target, result, status} where status ∈ {Cumple, No cumple, Revisar, N/D}
"""
from __future__ import annotations

import pandas as pd


def validate_portfolio(
    portfolio: dict,
    universe: pd.DataFrame,
    config: dict | None = None,
    metrics: dict | None = None,
) -> list[dict]:
    """
    Validate portfolio against Actinver challenge rules.

    portfolio: {ticker: {weight: float, main_category: str, sector: str, ...}}
    universe: full assets_universe DataFrame
    Returns list of rule dicts: [{rule, target, result, status}]
    """
    config = config or {}
    port_cfg = config.get("portfolio", {})
    target_eq = port_cfg.get("target_equity_pct", 0.40)
    target_fi = port_cfg.get("target_fixed_income_pct", 0.60)

    rules = []

    if not portfolio:
        return [{
            "Regla": "Portafolio vacío",
            "Objetivo": "—",
            "Resultado actual": "Sin activos",
            "Estado": "N/D",
        }]

    # ── Build summary ──
    total_weight = sum(info.get("weight", 0) for info in portfolio.values())

    eq_weight = 0.0
    fi_weight = 0.0
    rv_sectors: set[str] = set()
    rv_regions: set[str] = set()
    prohibited_tickers: list[str] = []
    overweight_rv: list[str] = []
    negative_weights: list[str] = []

    universe_idx = universe.set_index("ticker") if "ticker" in universe.columns else pd.DataFrame()

    for ticker, info in portfolio.items():
        w = info.get("weight", 0.0)
        if w < 0:
            negative_weights.append(ticker)

        cat = info.get("main_category", "")
        sector = info.get("sector", "")
        region = info.get("region", "")
        is_allowed = info.get("is_allowed", True)
        is_inverse = info.get("is_inverse", False)

        # Supplement from universe if info is sparse
        if not cat and not universe_idx.empty and ticker in universe_idx.index:
            row = universe_idx.loc[ticker]
            cat = str(row.get("main_category", ""))
            sector = str(row.get("sector", ""))
            region = str(row.get("region", ""))
            is_allowed = bool(row.get("is_allowed", True))
            is_inverse = bool(row.get("is_inverse", False))
            is_leveraged = bool(row.get("is_leveraged", False))
        else:
            is_leveraged = info.get("is_leveraged", False)

        if is_inverse or is_leveraged or not is_allowed:
            prohibited_tickers.append(ticker)

        if "Renta Variable" in cat:
            eq_weight += w
            if sector and sector not in ("", "No aplica", "N/D"):
                rv_sectors.add(sector)
            if region and region not in ("", "N/D"):
                rv_regions.add(region)
            if w > 0.10:
                overweight_rv.append(f"{ticker} ({w*100:.1f}%)")

        elif "Renta Fija" in cat:
            fi_weight += w

    # ── Rules ──
    tol = 0.005  # 0.5% tolerance

    def pct(v):
        return f"{v*100:.2f}%"

    # 1. Total weight
    rules.append({
        "Regla": "Peso total del portafolio",
        "Objetivo": "100.00%",
        "Resultado actual": pct(total_weight),
        "Estado": "Cumple" if abs(total_weight - 1.0) < tol else "No cumple",
    })

    # 2. Renta Fija
    rules.append({
        "Regla": "Renta Fija = 60%",
        "Objetivo": pct(target_fi),
        "Resultado actual": pct(fi_weight),
        "Estado": "Cumple" if abs(fi_weight - target_fi) < tol else (
            "Revisar" if abs(fi_weight - target_fi) < 0.02 else "No cumple"
        ),
    })

    # 3. Renta Variable
    rules.append({
        "Regla": "Renta Variable = 40%",
        "Objetivo": pct(target_eq),
        "Resultado actual": pct(eq_weight),
        "Estado": "Cumple" if abs(eq_weight - target_eq) < tol else (
            "Revisar" if abs(eq_weight - target_eq) < 0.02 else "No cumple"
        ),
    })

    # 4. Max per RV asset
    rules.append({
        "Regla": "Máximo por activo de RV ≤ 10%",
        "Objetivo": "Ningún activo RV > 10.0%",
        "Resultado actual": ", ".join(overweight_rv) if overweight_rv else "OK",
        "Estado": "Cumple" if not overweight_rv else "No cumple",
    })

    # 5. Min 4 RV sectors
    n_sectors = len(rv_sectors)
    rules.append({
        "Regla": "Mínimo 4 sectores de RV",
        "Objetivo": "≥ 4 sectores",
        "Resultado actual": f"{n_sectors} sector(es): {', '.join(sorted(rv_sectors)) if rv_sectors else '—'}",
        "Estado": "Cumple" if n_sectors >= 4 else ("Revisar" if n_sectors >= 3 else "No cumple"),
    })

    # 6. No prohibited instruments
    rules.append({
        "Regla": "Sin instrumentos prohibidos",
        "Objetivo": "0 instrumentos inversos/short/apalancados (ej. DOG)",
        "Resultado actual": ", ".join(prohibited_tickers) if prohibited_tickers else "ninguno",
        "Estado": "Cumple" if not prohibited_tickers else "No cumple",
    })

    # 6b. Sector Tecnología obligatorio
    has_tech = any(s.lower() == "tecnología" for s in rv_sectors)
    rules.append({
        "Regla": "Sector Tecnología obligatorio",
        "Objetivo": "Incluir Tecnología en RV",
        "Resultado actual": "Incluido" if has_tech else "Falta",
        "Estado": "Cumple" if has_tech else "No cumple",
    })

    # 6c. Max 3 emisoras por sector
    from collections import defaultdict
    sector_counts = defaultdict(int)
    for ticker, info in portfolio.items():
        cat = info.get("main_category", "")
        # fallback to universe
        if not cat and not universe_idx.empty and ticker in universe_idx.index:
            row = universe_idx.loc[ticker]
            cat = str(row.get("main_category", ""))
        
        if "Renta Variable" in cat:
            sec = info.get("sector", "")
            if not sec and not universe_idx.empty and ticker in universe_idx.index:
                sec = str(universe_idx.loc[ticker].get("sector", ""))
            if sec and sec not in ("", "No aplica", "N/D"):
                sector_counts[sec] += 1
                
    over_limit_sectors = [s for s, count in sector_counts.items() if count > 3]
    rules.append({
        "Regla": "Máximo 3 emisoras por sector (RV)",
        "Objetivo": "≤ 3",
        "Resultado actual": ", ".join(f"{s} ({sector_counts[s]})" for s in over_limit_sectors) if over_limit_sectors else "OK",
        "Estado": "Cumple" if not over_limit_sectors else "No cumple",
    })

    # 6d. VaR 95% máximo -2.5%
    var_limit = 0.025  # VaR format is positive for loss
    if metrics and "var_95" in metrics and metrics["var_95"] is not None and not pd.isna(metrics["var_95"]):
        var_val = metrics["var_95"]
        estado = "Cumple" if var_val <= var_limit else "No cumple"
        resultado = f"{(var_val*100):.2f}%"
    else:
        estado = "N/D"
        resultado = "N/D"
        
    rules.append({
        "Regla": "VaR 95% máximo -2.5%",
        "Objetivo": "Pérdida max 2.50% (VaR 95%)",
        "Resultado actual": resultado,
        "Estado": estado,
    })


    # 7. Global diversification (proxy: ≥ 2 distinct regions in RV)
    n_regions = len(rv_regions)
    rules.append({
        "Regla": "Diversificación geográfica (RV)",
        "Objetivo": "≥ 2 regiones en Renta Variable",
        "Resultado actual": f"{n_regions} región(es): {', '.join(sorted(rv_regions)) if rv_regions else '—'}",
        "Estado": "Cumple" if n_regions >= 2 else ("Revisar" if n_regions == 1 else "N/D"),
    })

    # 8. No negative weights
    rules.append({
        "Regla": "Pesos no negativos",
        "Objetivo": "Todos los pesos ≥ 0%",
        "Resultado actual": ", ".join(negative_weights) if negative_weights else "OK",
        "Estado": "Cumple" if not negative_weights else "No cumple",
    })

    # 9. No duplicate tickers
    tickers_list = list(portfolio.keys())
    has_dupes = len(tickers_list) != len(set(tickers_list))
    rules.append({
        "Regla": "Sin tickers duplicados",
        "Objetivo": "Cada activo aparece una sola vez",
        "Resultado actual": "Sin duplicados" if not has_dupes else "Hay duplicados",
        "Estado": "Cumple" if not has_dupes else "No cumple",
    })

    # 10. Tickers con datos válidos o manuales
    invalid_tickers = [
        t for t in portfolio
        if not t or len(t.strip()) == 0
    ]
    rules.append({
        "Regla": "Tickers válidos o manuales",
        "Objetivo": "Todos los tickers tienen identificador",
        "Resultado actual": "OK" if not invalid_tickers else f"Inválidos: {invalid_tickers}",
        "Estado": "Cumple" if not invalid_tickers else "No cumple",
    })

    return rules
