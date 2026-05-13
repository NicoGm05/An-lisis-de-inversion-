"""
app.py – Actinver Portfolio Lab | Main Streamlit Application
Constructor dinámico de portafolios cuantitativos para el reto académico Actinver.
Capital: $1,000,000 MXN | 60% Renta Fija | 40% Renta Variable | Perfil: Conservador
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")

from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

# ── Internal modules ──
from src.utils import (
    load_config, inject_css,
    format_pct, format_mxn, format_num,
    status_badge, source_badge,
    render_metric_card, render_progress,
)
from src.data_loader import (
    load_assets_universe, load_manual_fixed_income,
    save_manual_fixed_income, load_portfolio_by_name,
    save_portfolio, list_portfolio_names,
)
from src.market_data import fetch_historical_prices, fetch_price_series
from src.fundamentals import get_fundamentals
from src.portfolio_math import (
    calc_portfolio_returns, calc_portfolio_value,
    calc_annualized_return, calc_cagr, calc_volatility,
    calc_sharpe, calc_sortino, calc_beta_alpha, calc_treynor,
    calc_var, calc_max_drawdown, calc_correlation_matrix,
    full_portfolio_metrics,
)
from src.validations import validate_portfolio
from src.charts import (
    chart_composition_type, chart_composition_sector,
    chart_composition_region, chart_composition_currency,
    chart_composition_treemap, chart_historical_performance,
    chart_drawdown, chart_correlation_heatmap,
    chart_individual_returns, chart_portfolio_comparison,
)

# ══════════════════════════════════════════════
# PAGE CONFIG (must be first Streamlit call)
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="Actinver | Portfolio Lab",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Actinver Portfolio Lab — Reto Académico 2025"},
)

inject_css()

# ══════════════════════════════════════════════
# LOAD STATIC DATA
# ══════════════════════════════════════════════
@st.cache_data(ttl=3600)
def _load_universe():
    return load_assets_universe()


@st.cache_data(ttl=60)
def _load_manual_fi():
    return load_manual_fixed_income()


config = load_config()
universe_df = _load_universe()
manual_fi_df = _load_manual_fi()

EQUITY_SECTORS = [
    "Núcleo global", "Salud", "Consumo básico", "Tecnología",
    "Utilities", "Construcción", "Consumo discrecional",
]

BENCHMARKS = {
    "ACWI": "ACWI — MSCI All Country World",
    "SPY": "SPY — S&P 500",
    "^MXX": "^MXX — IPC BMV (México)",
    "AGG": "AGG — US Aggregate Bond",
}

# ══════════════════════════════════════════════
# SESSION STATE INIT
# ══════════════════════════════════════════════
def _init_state():
    defaults = {
        "portfolio_name": "Portafolio A",
        "portfolio": {},            # {ticker: {weight, name, main_category, sector, ...}}
        "capital": float(config["portfolio"]["total_capital"]),
        "risk_free_rate": float(config["market_data"]["default_risk_free_rate"]),
        "benchmark": config["market_data"]["default_benchmark"],
        "prices_cache": {},         # DataFrame per portfolio name
        "warnings": [],
        "last_updated": None,
        "manual_fi": {},            # {key: annual_yield (float)}
        "saved_portfolios": {},     # {name: dict}
        "data_loaded": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ══════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════

def _meta(ticker: str) -> dict:
    """Get asset metadata from universe."""
    row = universe_df[universe_df["ticker"] == ticker]
    if row.empty:
        return {}
    return row.iloc[0].to_dict()


def _portfolio_as_df() -> pd.DataFrame:
    """Convert session portfolio to DataFrame for display."""
    rows = []
    for ticker, info in st.session_state.portfolio.items():
        rows.append({
            "ticker": ticker,
            "name": info.get("name", ticker),
            "weight": info.get("weight", 0.0),
            "weight_pct": info.get("weight", 0.0) * 100,
            "monto_mxn": info.get("weight", 0.0) * st.session_state.capital,
            "main_category": info.get("main_category", ""),
            "sector": info.get("sector", ""),
            "region": info.get("region", ""),
            "currency": info.get("currency", ""),
            "data_source": info.get("data_source", ""),
            "status": info.get("status", ""),
            "requires_manual_data": info.get("requires_manual_data", False),
            "is_allowed": info.get("is_allowed", True),
        })
    df = pd.DataFrame(rows)
    return df


def _add_asset(ticker: str, weight: float = 0.0):
    meta = _meta(ticker)
    st.session_state.portfolio[ticker] = {
        "weight": weight,
        "name": meta.get("name", ticker),
        "main_category": meta.get("main_category", ""),
        "sector": meta.get("sector", ""),
        "region": meta.get("region", ""),
        "currency": meta.get("currency", "USD"),
        "data_source": meta.get("data_source", ""),
        "status": meta.get("status", ""),
        "is_allowed": bool(meta.get("is_allowed", True)),
        "is_inverse": bool(meta.get("is_inverse", False)),
        "is_leveraged": bool(meta.get("is_leveraged", False)),
        "requires_manual_data": bool(meta.get("requires_manual_data", False)),
        "notes": meta.get("notes", ""),
    }


def _remove_asset(ticker: str):
    st.session_state.portfolio.pop(ticker, None)


def _total_weight() -> float:
    return sum(info.get("weight", 0) for info in st.session_state.portfolio.values())


def _rv_weight() -> float:
    return sum(
        info.get("weight", 0)
        for info in st.session_state.portfolio.values()
        if "Renta Variable" in info.get("main_category", "")
    )


def _rf_weight() -> float:
    return sum(
        info.get("weight", 0)
        for info in st.session_state.portfolio.values()
        if "Renta Fija" in info.get("main_category", "")
    )


def _fetch_prices() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch prices for all non-manual tickers. Returns (prices_df, bench_df)."""
    tickers_with_data = [
        t for t, info in st.session_state.portfolio.items()
        if not info.get("requires_manual_data", False) and info.get("data_source", "") != "Manual"
    ]
    bench = st.session_state.benchmark
    all_tickers = list(set(tickers_with_data + [bench]))

    prices_df, sources, dates, warnings = fetch_historical_prices(
        all_tickers,
        config=config,
    )
    st.session_state.warnings = warnings
    st.session_state.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")

    bench_df = pd.DataFrame()
    if bench in prices_df.columns:
        bench_df = prices_df[[bench]].copy()

    port_price_df = prices_df.drop(columns=[bench], errors="ignore")
    return port_price_df, bench_df


# ══════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════

with st.sidebar:
    st.markdown('<div class="app-headline">◈ ACTINVER</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-sub">Portfolio Lab · Reto Académico 2025</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Portfolio selector
    pf_names = list_portfolio_names()
    selected_pf = st.selectbox(
        "📁 Portafolio activo",
        options=pf_names,
        index=pf_names.index(st.session_state.portfolio_name)
        if st.session_state.portfolio_name in pf_names else 0,
        key="sel_portfolio",
    )
    if selected_pf != st.session_state.portfolio_name:
        st.session_state.portfolio_name = selected_pf
        loaded = load_portfolio_by_name(selected_pf)
        if loaded:
            # Re-enrich with universe metadata
            new_pf = {}
            for ticker, info in loaded.items():
                meta = _meta(ticker)
                new_pf[ticker] = {**meta, **info}
            st.session_state.portfolio = new_pf
        else:
            st.session_state.portfolio = {}

    col_sv, col_dup = st.columns(2)
    with col_sv:
        if st.button("💾 Guardar", use_container_width=True):
            save_portfolio(st.session_state.portfolio_name, st.session_state.portfolio)
            st.success("Portafolio guardado")
    with col_dup:
        if st.button("📋 Limpiar", use_container_width=True):
            st.session_state.portfolio = {}
            st.rerun()

    st.markdown("---")

    # Capital
    capital = st.number_input(
        "💰 Capital inicial (MXN)",
        min_value=100_000,
        max_value=100_000_000,
        value=int(st.session_state.capital),
        step=100_000,
        format="%d",
    )
    st.session_state.capital = float(capital)

    # Risk-free rate
    rf_raw = st.number_input(
        "📊 Tasa libre de riesgo (% anual)",
        min_value=0.0, max_value=30.0,
        value=float(st.session_state.risk_free_rate * 100),
        step=0.1, format="%.2f",
        help="Usar CETES 28 días vigentes. Si no se captura, los ratios se calculan con tasa = 0% (se indicará advertencia).",
    )
    st.session_state.risk_free_rate = rf_raw / 100.0
    if rf_raw == 0:
        st.markdown('<div class="alert-warn">⚠ Tasas libres de riesgo = 0%. Sharpe/Sortino/Treynor calculados con rf=0. Capturar tasa CETES actual.</div>', unsafe_allow_html=True)

    # Benchmark
    bench_key = st.selectbox(
        "📈 Benchmark",
        options=list(BENCHMARKS.keys()),
        format_func=lambda k: BENCHMARKS[k],
        index=list(BENCHMARKS.keys()).index(st.session_state.benchmark)
        if st.session_state.benchmark in BENCHMARKS else 0,
    )
    st.session_state.benchmark = bench_key

    st.markdown("---")

    # Update data
    if st.button("🔄 Actualizar datos de mercado", use_container_width=True, type="primary"):
        with st.spinner("Descargando datos…"):
            port_prices, bench_prices = _fetch_prices()
            st.session_state["_port_prices"] = port_prices
            st.session_state["_bench_prices"] = bench_prices
            st.session_state.data_loaded = True
        st.success(f"Datos actualizados: {st.session_state.last_updated}")

    if st.session_state.last_updated:
        st.caption(f"Última actualización: {st.session_state.last_updated}")
    else:
        st.caption("Presiona 'Actualizar datos' para descargar precios históricos.")

    st.markdown("---")

    # Portfolio summary in sidebar
    total_w = _total_weight()
    rv_w = _rv_weight()
    rf_w = _rf_weight()
    unassigned = max(0.0, 1.0 - total_w)

    st.markdown('<div class="sub-header">RESUMEN</div>', unsafe_allow_html=True)
    st.markdown(render_progress(rv_w, 0.40, "🔵 Renta Variable"), unsafe_allow_html=True)
    st.markdown(render_progress(rf_w, 0.60, "🟡 Renta Fija"), unsafe_allow_html=True)

    diff = total_w - 1.0
    total_color = "#00d26a" if abs(diff) < 0.005 else ("#ff4d4f" if diff > 0.005 else "#f0a500")
    st.markdown(
        f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;color:{total_color};margin-top:4px;">'
        f'Total asignado: {total_w*100:.2f}% | Sin asignar: {unassigned*100:.2f}%</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Activos: {len(st.session_state.portfolio)} | Capital: {format_mxn(capital)}")

# ══════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════
st.markdown(
    '<div class="app-headline" style="font-size:36px;">PORTAFOLIO LAB · ACTINVER</div>'
    '<div class="app-sub">Constructor cuantitativo de portafolios · Perfil conservador · $1,000,000 MXN · 60% RF / 40% RV</div>',
    unsafe_allow_html=True,
)
st.markdown("---")

# Show warnings if any
if st.session_state.warnings:
    for w in st.session_state.warnings[:3]:
        st.markdown(f'<div class="alert-warn">{w}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════
# MAIN TABS
# ══════════════════════════════════════════════
tabs = st.tabs([
    "🏗 Constructor",
    "📊 Resumen Cuant.",
    "✅ Validación",
    "🍩 Composición",
    "📈 Rendimiento",
    "⚡ Riesgo",
    "🔬 Fundamentales",
    "⚖ Comparación",
])

# ══════════════════════════════════════════════
# TAB 1 — CONSTRUCTOR
# ══════════════════════════════════════════════
with tabs[0]:
    st.markdown('<div class="section-header">Constructor de Portafolio</div>', unsafe_allow_html=True)
    st.markdown(
        "*Agrega activos al portafolio, asigna pesos (en % del portafolio total). "
        "Todo se recalcula automáticamente. Construye primero Renta Variable, luego Renta Fija.*"
    )

    # ── RENTA VARIABLE ──
    st.markdown('<div class="sub-header">🔵 RENTA VARIABLE — Objetivo: 40%</div>', unsafe_allow_html=True)
    st.markdown(render_progress(_rv_weight(), 0.40, "Renta Variable"), unsafe_allow_html=True)

    rv_universe = universe_df[
        (universe_df["main_category"] == "Renta Variable") &
        (universe_df["status"] != "No permitido")
    ].copy()

    for sector in EQUITY_SECTORS:
        sector_assets = rv_universe[rv_universe["sector"] == sector]
        if sector_assets.empty:
            continue

        sector_weight = sum(
            st.session_state.portfolio.get(t, {}).get("weight", 0)
            for t in sector_assets["ticker"].tolist()
        )
        with st.expander(
            f"**{sector}** — {sector_weight*100:.1f}% asignado ({len(sector_assets)} activos)",
            expanded=False,
        ):
            for _, asset_row in sector_assets.iterrows():
                ticker = asset_row["ticker"]
                name = asset_row["name"]
                status = asset_row.get("status", "")
                region = asset_row.get("region", "")
                asset_type = asset_row.get("asset_type", "")
                currency = asset_row.get("currency", "")
                in_portfolio = ticker in st.session_state.portfolio

                col_cb, col_name, col_badge, col_w, col_rm = st.columns([0.5, 3, 1.5, 2, 0.8])
                with col_cb:
                    checked = st.checkbox("", value=in_portfolio, key=f"cb_{ticker}",
                                          label_visibility="collapsed")
                with col_name:
                    status_emoji = {"Permitido": "✅", "Revisar": "🟡"}.get(status, "❓")
                    st.markdown(
                        f'<span style="font-size:12px;font-weight:600;">{status_emoji} {ticker}</span>'
                        f'<br><span style="font-size:11px;color:#6b7a8d;">{name}</span>'
                        f'<br><span style="font-size:10px;color:#4a6580;">{asset_type} | {region} | {currency}</span>',
                        unsafe_allow_html=True,
                    )
                with col_badge:
                    st.markdown(f'<br>{source_badge(asset_row.get("data_source",""))}<br>', unsafe_allow_html=True)
                with col_w:
                    if checked or in_portfolio:
                        current_w = st.session_state.portfolio.get(ticker, {}).get("weight", 0.0)
                        new_w = st.number_input(
                            "Peso %",
                            min_value=0.0, max_value=100.0,
                            value=round(current_w * 100, 2),
                            step=0.5, format="%.2f",
                            key=f"w_{ticker}",
                            label_visibility="collapsed",
                        )
                        if checked and not in_portfolio:
                            _add_asset(ticker, new_w / 100)
                        elif in_portfolio:
                            st.session_state.portfolio[ticker]["weight"] = new_w / 100
                    else:
                        st.markdown("—")
                with col_rm:
                    if in_portfolio and st.button("✕", key=f"rm_{ticker}", help="Quitar del portafolio"):
                        _remove_asset(ticker)
                        st.rerun()

                if not checked and in_portfolio:
                    _remove_asset(ticker)

            st.markdown(
                f'<div style="font-size:11px;color:#6b7a8d;margin-top:4px;">'
                f'Peso del sector: <b style="color:#f0a500;">{sector_weight*100:.2f}%</b> del portafolio total</div>',
                unsafe_allow_html=True,
            )

    # DOG — No permitido
    with st.expander("🚫 Activos NO PERMITIDOS (visible solo para referencia)", expanded=False):
        dog_row = universe_df[universe_df["ticker"] == "DOG"]
        if not dog_row.empty:
            st.markdown(
                '<div class="alert-error">🚫 <b>DOG — ProShares Short Dow30:</b> ETF inverso/short. '
                'Este instrumento NO cumple con el perfil conservador ni con las reglas del portafolio Actinver. '
                'No puede agregarse al portafolio.</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(
                dog_row[["ticker", "name", "asset_type", "status", "notes"]],
                use_container_width=True, hide_index=True,
            )

    st.markdown("---")

    # ── RENTA FIJA ──
    st.markdown('<div class="sub-header">🟡 RENTA FIJA — Objetivo: 60%</div>', unsafe_allow_html=True)
    st.markdown(render_progress(_rf_weight(), 0.60, "Renta Fija"), unsafe_allow_html=True)
    st.markdown(
        "*Los instrumentos marcados como 'Manual' no tienen datos históricos automáticos. "
        "Captura la tasa/rendimiento anual manualmente. Estos datos se marcarán como Manual.*"
    )

    rf_universe = universe_df[universe_df["main_category"] == "Renta Fija"].copy()

    cetes_assets = rf_universe[rf_universe["sector"] == "CETES"]
    other_rf_assets = rf_universe[rf_universe["sector"] != "CETES"]

    rf_groups = [
        ("📌 CETES (Gubernamental MX)", rf_universe[rf_universe["sector"] == "CETES"]),
        ("📌 BONDES / UDIBONOS (Gubernamental MX)", rf_universe[rf_universe["sector"].isin(["BONDES", "UDIBONOS"])]),
        ("📌 ETFs de Bonos Internacionales", rf_universe[rf_universe["sector"] == "Bonos internacionales"]),
        ("📌 Fondos Actinver (Placeholder)", rf_universe[rf_universe["sector"] == "Fondos Actinver"]),
    ]

    # Load manual yields from session
    if "manual_yields" not in st.session_state:
        st.session_state.manual_yields = {}
        for _, row in manual_fi_df.iterrows():
            key = str(row.get("instrument_key", ""))
            y = row.get("annual_yield", None)
            st.session_state.manual_yields[key] = float(y) if pd.notna(y) and y != "" else None

    for group_label, group_df in rf_groups:
        if group_df.empty:
            continue
        group_weight = sum(
            st.session_state.portfolio.get(t, {}).get("weight", 0)
            for t in group_df["ticker"].tolist()
        )
        with st.expander(
            f"**{group_label}** — {group_weight*100:.1f}% asignado",
            expanded=False,
        ):
            for _, asset_row in group_df.iterrows():
                ticker = asset_row["ticker"]
                name = asset_row["name"]
                is_manual = bool(asset_row.get("requires_manual_data", False))
                currency = asset_row.get("currency", "MXN")
                in_portfolio = ticker in st.session_state.portfolio

                col_cb, col_name, col_w, col_rate, col_rm = st.columns([0.5, 3, 1.5, 2, 0.8])
                with col_cb:
                    checked = st.checkbox("", value=in_portfolio, key=f"cb_rf_{ticker}",
                                          label_visibility="collapsed")
                with col_name:
                    manual_badge = source_badge("Manual") if is_manual else source_badge("yfinance")
                    st.markdown(
                        f'<span style="font-size:12px;font-weight:600;">📄 {ticker}</span>'
                        f'<br><span style="font-size:11px;color:#6b7a8d;">{name}</span>'
                        f'<br>{manual_badge} <span style="font-size:10px;color:#4a6580;">{currency}</span>',
                        unsafe_allow_html=True,
                    )
                with col_w:
                    if checked or in_portfolio:
                        current_w = st.session_state.portfolio.get(ticker, {}).get("weight", 0.0)
                        new_w = st.number_input(
                            "Peso %",
                            min_value=0.0, max_value=100.0,
                            value=round(current_w * 100, 2),
                            step=0.5, format="%.2f",
                            key=f"w_rf_{ticker}",
                            label_visibility="collapsed",
                        )
                        if checked and not in_portfolio:
                            _add_asset(ticker, new_w / 100)
                        elif in_portfolio:
                            st.session_state.portfolio[ticker]["weight"] = new_w / 100
                    else:
                        st.markdown("—")
                with col_rate:
                    if is_manual and (checked or in_portfolio):
                        current_rate = st.session_state.manual_yields.get(ticker, None)
                        rate_input = st.number_input(
                            "Tasa anual % (Manual)",
                            min_value=0.0, max_value=100.0,
                            value=float(current_rate) if current_rate is not None else 0.0,
                            step=0.01, format="%.4f",
                            key=f"rate_{ticker}",
                            help="Capturar desde Banxico, cetesdirecto.mx o Actinver. Dato Manual.",
                        )
                        st.session_state.manual_yields[ticker] = rate_input if rate_input > 0 else None
                        st.caption("📌 Manual")
                    elif not is_manual:
                        st.markdown('<span style="font-size:11px;color:#6b7a8d;">Datos automáticos</span>', unsafe_allow_html=True)
                    else:
                        st.markdown("—")
                with col_rm:
                    if in_portfolio and st.button("✕", key=f"rm_rf_{ticker}", help="Quitar"):
                        _remove_asset(ticker)
                        st.rerun()

                if not checked and in_portfolio:
                    _remove_asset(ticker)

    # Quick-add note
    st.info(
        "💡 Nota: Los fondos Actinver (ACTINVER_DEUDA_CP, ACTINVER_LIQUIDEZ, ACTINVER_UDIS) son **placeholders**. "
        "Edita el nombre/clave/tasa con la información oficial del prospecto del fondo."
    )


# ══════════════════════════════════════════════
# LAZY PRICE LOAD — if not loaded yet, show hint
PRICES_LOADED = st.session_state.get("data_loaded", False)
_port_prices: pd.DataFrame = st.session_state.get("_port_prices", pd.DataFrame())
_bench_prices: pd.DataFrame = st.session_state.get("_bench_prices", pd.DataFrame())

def _no_data_msg():
    st.markdown(
        '<div class="alert-info">ℹ Presiona <b>Actualizar datos de mercado</b> en el sidebar para descargar '
        'precios históricos y calcular métricas cuantitativas.</div>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════
# TAB 2 — RESUMEN CUANTITATIVO
# ══════════════════════════════════════════════
with tabs[1]:
    st.markdown('<div class="section-header">Resumen Cuantitativo</div>', unsafe_allow_html=True)

    port_df = _portfolio_as_df()
    n_assets = len(st.session_state.portfolio)
    rv_w_now = _rv_weight()
    rf_w_now = _rf_weight()
    total_w_now = _total_weight()
    unassigned_now = max(0.0, 1.0 - total_w_now)

    # ── Quick overview cards ──
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(render_metric_card("Capital inicial", format_mxn(st.session_state.capital)), unsafe_allow_html=True)
    with c2:
        st.markdown(render_metric_card("Activos en portafolio", str(n_assets)), unsafe_allow_html=True)
    with c3:
        st.markdown(render_metric_card("Renta Variable", format_pct(rv_w_now), f"Objetivo: 40%"), unsafe_allow_html=True)
    with c4:
        st.markdown(render_metric_card("Renta Fija", format_pct(rf_w_now), f"Objetivo: 60%"), unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(render_metric_card("Total asignado", format_pct(total_w_now)), unsafe_allow_html=True)
    with c6:
        st.markdown(render_metric_card("Monto sin asignar", format_mxn(unassigned_now * st.session_state.capital)), unsafe_allow_html=True)
    with c7:
        st.markdown(render_metric_card("Tasa libre de riesgo", format_pct(st.session_state.risk_free_rate)), unsafe_allow_html=True)
    with c8:
        st.markdown(render_metric_card("Benchmark", st.session_state.benchmark), unsafe_allow_html=True)

    if not PRICES_LOADED or _port_prices.empty:
        _no_data_msg()
    else:
        weights_dict = {
            t: info.get("weight", 0)
            for t, info in st.session_state.portfolio.items()
            if not info.get("requires_manual_data", False)
        }
        bench_ticker = st.session_state.benchmark
        m = full_portfolio_metrics(
            _port_prices, weights_dict,
            _bench_prices if not _bench_prices.empty else None,
            bench_ticker,
            risk_free_rate=st.session_state.risk_free_rate,
        )

        if m.get("cagr_warning"):
            st.markdown(f'<div class="alert-warn">{m["cagr_warning"]}</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div class="sub-header">MÉTRICAS DE RENDIMIENTO</div>', unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            st.markdown(render_metric_card("Rendimiento Anualizado", format_pct(m["annualized_return"]), "252 días"), unsafe_allow_html=True)
        with r2:
            st.markdown(render_metric_card("CAGR 5 años", format_pct(m["cagr"]), "período disponible"), unsafe_allow_html=True)
        with r3:
            st.markdown(render_metric_card("Volatilidad Anualizada", format_pct(m["volatility"]), ""), unsafe_allow_html=True)
        with r4:
            st.markdown(render_metric_card("Sharpe Ratio", format_num(m["sharpe"], 4)), unsafe_allow_html=True)

        r5, r6, r7, r8 = st.columns(4)
        with r5:
            st.markdown(render_metric_card("Sortino Ratio", format_num(m["sortino"], 4)), unsafe_allow_html=True)
        with r6:
            treynor_val = format_num(m["treynor"], 4) if m["treynor"] is not None else "N/D (β≈0)"
            st.markdown(render_metric_card("Treynor Ratio", treynor_val), unsafe_allow_html=True)
        with r7:
            st.markdown(render_metric_card("VaR Histórico 95%", format_pct(m["var_95"]), "1 día"), unsafe_allow_html=True)
        with r8:
            st.markdown(render_metric_card("VaR Histórico 99%", format_pct(m["var_99"]), "1 día"), unsafe_allow_html=True)

        r9, r10, r11, r12 = st.columns(4)
        with r9:
            st.markdown(render_metric_card("Max Drawdown", format_pct(m["max_drawdown"]), ""), unsafe_allow_html=True)
        with r10:
            st.markdown(render_metric_card("Beta vs Benchmark", format_num(m["beta"], 4)), unsafe_allow_html=True)
        with r11:
            st.markdown(render_metric_card("Alpha vs Benchmark", format_pct(m["alpha"]), ""), unsafe_allow_html=True)
        with r12:
            st.markdown(render_metric_card("Correlación Promedio", format_num(m["avg_correlation"], 4)), unsafe_allow_html=True)

        # Monto por activo
        st.markdown("---")
        st.markdown('<div class="sub-header">DISTRIBUCIÓN DEL CAPITAL</div>', unsafe_allow_html=True)
        if not port_df.empty:
            display_cols = ["ticker", "name", "weight_pct", "monto_mxn", "main_category", "sector", "region", "currency"]
            display_df = port_df[display_cols].copy()
            display_df.columns = ["Ticker", "Nombre", "Peso %", "Monto MXN", "Categoría", "Sector", "Región", "Moneda"]
            display_df["Peso %"] = display_df["Peso %"].map(lambda x: f"{x:.2f}%")
            display_df["Monto MXN"] = display_df["Monto MXN"].map(lambda x: f"${x:,.0f}")
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            # CSV export
            csv = port_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇ Descargar portafolio CSV", csv,
                               f"portafolio_{st.session_state.portfolio_name}.csv", "text/csv")


# ══════════════════════════════════════════════
# TAB 3 — VALIDACIÓN
# ══════════════════════════════════════════════
with tabs[2]:
    st.markdown('<div class="section-header">Tabla de Validación de Reglas</div>', unsafe_allow_html=True)
    st.markdown("*Semáforo de cumplimiento. Actualiza pesos en el Constructor para ver cambios en tiempo real.*")

    rules = validate_portfolio(
        st.session_state.portfolio,
        universe_df,
        config,
    )
    rules_df = pd.DataFrame(rules)
    if not rules_df.empty:
        # Add HTML badge column
        rules_df["Estado HTML"] = rules_df["Estado"].apply(status_badge)
        display_rules = rules_df[["Regla", "Objetivo", "Resultado actual", "Estado"]].copy()
        st.dataframe(
            display_rules,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Estado": st.column_config.TextColumn("Estado", width="small"),
            },
        )

        # Color summary
        cumple = (rules_df["Estado"] == "Cumple").sum()
        no_cumple = (rules_df["Estado"] == "No cumple").sum()
        revisar = (rules_df["Estado"] == "Revisar").sum()

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            st.markdown(
                f'<div class="metric-card" style="border-color:#00d26a;">'
                f'<div class="metric-label">Cumple</div>'
                f'<div class="metric-value" style="color:#00d26a;">{cumple}</div></div>',
                unsafe_allow_html=True,
            )
        with sc2:
            st.markdown(
                f'<div class="metric-card" style="border-color:#ff4d4f;">'
                f'<div class="metric-label">No cumple</div>'
                f'<div class="metric-value" style="color:#ff4d4f;">{no_cumple}</div></div>',
                unsafe_allow_html=True,
            )
        with sc3:
            st.markdown(
                f'<div class="metric-card" style="border-color:#f0a500;">'
                f'<div class="metric-label">Revisar</div>'
                f'<div class="metric-value" style="color:#f0a500;">{revisar}</div></div>',
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════
# TAB 4 — COMPOSICIÓN
# ══════════════════════════════════════════════
with tabs[3]:
    st.markdown('<div class="section-header">Composición del Portafolio</div>', unsafe_allow_html=True)
    port_df = _portfolio_as_df()

    if port_df.empty:
        st.info("Agrega activos en el Constructor para ver gráficas de composición.")
    else:
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            st.plotly_chart(chart_composition_type(port_df), use_container_width=True)
        with r1c2:
            st.plotly_chart(chart_composition_region(port_df), use_container_width=True)

        r2c1, r2c2 = st.columns(2)
        with r2c1:
            st.plotly_chart(chart_composition_sector(port_df), use_container_width=True)
        with r2c2:
            st.plotly_chart(chart_composition_currency(port_df), use_container_width=True)

        st.plotly_chart(chart_composition_treemap(port_df), use_container_width=True)


# ══════════════════════════════════════════════
# TAB 5 — RENDIMIENTO HISTÓRICO
# ══════════════════════════════════════════════
with tabs[4]:
    st.markdown('<div class="section-header">Rendimiento Histórico</div>', unsafe_allow_html=True)
    if not PRICES_LOADED or _port_prices.empty:
        _no_data_msg()
    else:
        weights_dict = {
            t: info.get("weight", 0)
            for t, info in st.session_state.portfolio.items()
            if not info.get("requires_manual_data", False)
        }
        port_val = None
        bench_val_series = None

        if weights_dict:
            port_val = calc_portfolio_value(_port_prices, weights_dict, st.session_state.capital)

        if not _bench_prices.empty and st.session_state.benchmark in _bench_prices.columns:
            bench_val_series = _bench_prices[st.session_state.benchmark]

        st.plotly_chart(
            chart_historical_performance(
                port_val, bench_val_series,
                bench_label=BENCHMARKS.get(st.session_state.benchmark, st.session_state.benchmark),
                capital=st.session_state.capital,
            ),
            use_container_width=True,
        )

        # Individual assets
        if not _port_prices.empty and weights_dict:
            st.markdown('<div class="sub-header">RENDIMIENTO ACUMULADO POR ACTIVO</div>', unsafe_allow_html=True)
            active_tickers = [t for t in weights_dict if t in _port_prices.columns]
            if active_tickers:
                st.plotly_chart(
                    chart_individual_returns(_port_prices, active_tickers),
                    use_container_width=True,
                )


# ══════════════════════════════════════════════
# TAB 6 — RIESGO
# ══════════════════════════════════════════════
with tabs[5]:
    st.markdown('<div class="section-header">Análisis de Riesgo</div>', unsafe_allow_html=True)
    if not PRICES_LOADED or _port_prices.empty:
        _no_data_msg()
    else:
        weights_dict = {
            t: info.get("weight", 0)
            for t, info in st.session_state.portfolio.items()
            if not info.get("requires_manual_data", False)
        }
        port_ret = calc_portfolio_returns(_port_prices, weights_dict) if weights_dict else None

        # Risk metrics cards
        if port_ret is not None:
            vrv95 = calc_var(port_ret, 0.95)
            vrv99 = calc_var(port_ret, 0.99)
            vol = calc_volatility(port_ret)
            port_val = calc_portfolio_value(_port_prices, weights_dict, st.session_state.capital)
            md, _ = calc_max_drawdown(port_val) if port_val is not None else (None, None)

            rc1, rc2, rc3, rc4 = st.columns(4)
            with rc1:
                st.markdown(render_metric_card("Volatilidad Anualiz.", format_pct(vol)), unsafe_allow_html=True)
            with rc2:
                st.markdown(render_metric_card("VaR Histórico 95%", format_pct(vrv95), "pérdida diaria máx."), unsafe_allow_html=True)
            with rc3:
                st.markdown(render_metric_card("VaR Histórico 99%", format_pct(vrv99), "pérdida diaria máx."), unsafe_allow_html=True)
            with rc4:
                st.markdown(render_metric_card("Max Drawdown", format_pct(md), "caída máx. desde pico"), unsafe_allow_html=True)

        # Drawdown chart
        st.plotly_chart(chart_drawdown(port_ret), use_container_width=True)

        # Correlation heatmap
        corr = calc_correlation_matrix(_port_prices, weights_dict)
        st.plotly_chart(chart_correlation_heatmap(corr), use_container_width=True)

        # Contribution by asset
        if port_ret is not None and not _port_prices.empty and weights_dict:
            st.markdown('<div class="sub-header">CONTRIBUCIÓN AL RIESGO POR ACTIVO</div>', unsafe_allow_html=True)
            contributions = []
            for ticker, w in weights_dict.items():
                if ticker in _port_prices.columns:
                    asset_ret = _port_prices[ticker].pct_change().dropna()
                    asset_vol = float(asset_ret.std() * np.sqrt(252))
                    contributions.append({
                        "Ticker": ticker,
                        "Peso %": f"{w*100:.2f}%",
                        "Volatilidad Activo": format_pct(asset_vol),
                        "Cont. Riesgo (aprox.)": format_pct(w * asset_vol),
                    })
            if contributions:
                st.dataframe(pd.DataFrame(contributions), use_container_width=True, hide_index=True)
            else:
                st.info("Sin datos suficientes para calcular contribución.")


# ══════════════════════════════════════════════
# TAB 7 — FUNDAMENTALES
# ══════════════════════════════════════════════
with tabs[6]:
    st.markdown('<div class="section-header">Datos Fundamentales</div>', unsafe_allow_html=True)
    st.markdown(
        "*Los fundamentales se obtienen de FMP o Finnhub (requiere API key en config.yaml). "
        "Sin API key, todos los campos mostrarán N/D. No se inventan datos.*"
    )

    if not st.session_state.portfolio:
        st.info("Agrega activos en el Constructor primero.")
    else:
        equity_tickers = [
            t for t, info in st.session_state.portfolio.items()
            if "Renta Variable" in info.get("main_category", "")
            and not info.get("requires_manual_data", False)
        ]

        if st.button("🔬 Cargar Fundamentales", type="primary"):
            with st.spinner("Consultando APIs de fundamentales…"):
                fund_df = get_fundamentals(equity_tickers, config)
                st.session_state["_fundamentals"] = fund_df

        fund_df: pd.DataFrame = st.session_state.get("_fundamentals", pd.DataFrame())
        if not fund_df.empty:
            display_cols = [
                "ticker", "pe_ratio", "peg_ratio", "eps",
                "revenue_growth", "net_income_growth",
                "debt_equity", "interest_coverage",
                "current_ratio", "quick_ratio",
                "operating_margin", "gross_margin",
                "roe", "roa", "dividend_yield",
                "inventory_turnover", "asset_turnover",
                "source", "last_updated",
            ]
            col_labels = {
                "ticker": "Ticker", "pe_ratio": "P/E", "peg_ratio": "PEG",
                "eps": "EPS", "revenue_growth": "Rev. Growth",
                "net_income_growth": "NI Growth", "debt_equity": "D/E",
                "interest_coverage": "Int. Coverage", "current_ratio": "Current R.",
                "quick_ratio": "Quick R.", "operating_margin": "Op. Margin",
                "gross_margin": "Gross Margin", "roe": "ROE", "roa": "ROA",
                "dividend_yield": "Div. Yield", "inventory_turnover": "Inv. Turn.",
                "asset_turnover": "Asset Turn.", "source": "Fuente", "last_updated": "Actualizado",
            }
            show_df = fund_df[[c for c in display_cols if c in fund_df.columns]].rename(columns=col_labels)
            st.dataframe(show_df, use_container_width=True, hide_index=True)
            csv = fund_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇ Descargar fundamentales CSV", csv, "fundamentales.csv", "text/csv")
        elif equity_tickers:
            st.info("Presiona 'Cargar Fundamentales' para obtener datos (requiere API key configurada).")
        else:
            st.info("No hay acciones/ETFs de Renta Variable en el portafolio actual.")


# ══════════════════════════════════════════════
# TAB 8 — COMPARACIÓN
# ══════════════════════════════════════════════
with tabs[7]:
    st.markdown('<div class="section-header">Comparación de Portafolios</div>', unsafe_allow_html=True)
    st.markdown("*Los datos son objetivos y cuantitativos. La herramienta no emite recomendaciones ni indica cuál portafolio es mejor.*")

    all_pf_names = list_portfolio_names()
    compare_sel = st.multiselect(
        "Selecciona portafolios para comparar:",
        options=all_pf_names,
        default=[st.session_state.portfolio_name],
        max_selections=4,
    )

    if st.button("📊 Generar comparación", type="primary"):
        rows = []
        for pf_name in compare_sel:
            pf = load_portfolio_by_name(pf_name)
            if pf_name == st.session_state.portfolio_name:
                pf = st.session_state.portfolio  # use live version

            if not pf:
                rows.append({"Portafolio": pf_name, "N activos": 0, "% RF": "N/D", "% RV": "N/D"})
                continue

            rv_w = sum(info.get("weight", 0) for info in pf.values() if "Renta Variable" in info.get("main_category", ""))
            rf_w = sum(info.get("weight", 0) for info in pf.values() if "Renta Fija" in info.get("main_category", ""))
            rv_sectors = {info.get("sector", "") for t, info in pf.items() if "Renta Variable" in info.get("main_category", "")}
            rv_regions = {info.get("region", "") for t, info in pf.items() if "Renta Variable" in info.get("main_category", "")}

            row = {
                "Portafolio": pf_name,
                "N° activos": len(pf),
                "% RF": format_pct(rf_w),
                "% RV": format_pct(rv_w),
                "Sectores RV": len(rv_sectors),
                "Regiones": len(rv_regions),
                "Rendim. Anualiz.": "N/D",
                "CAGR": "N/D",
                "Volatilidad": "N/D",
                "Sharpe": "N/D",
                "Sortino": "N/D",
                "Treynor": "N/D",
                "VaR 95%": "N/D",
                "Max Drawdown": "N/D",
                "Beta": "N/D",
                "Alpha": "N/D",
                "Cumple reglas": "—",
            }

            # Try to compute metrics if prices are available
            if PRICES_LOADED and not _port_prices.empty:
                wdict = {t: info.get("weight", 0) for t, info in pf.items() if not info.get("requires_manual_data", False)}
                m = full_portfolio_metrics(
                    _port_prices, wdict,
                    _bench_prices if not _bench_prices.empty else None,
                    st.session_state.benchmark,
                    risk_free_rate=st.session_state.risk_free_rate,
                )
                row.update({
                    "Rendim. Anualiz.": format_pct(m["annualized_return"]),
                    "CAGR": format_pct(m["cagr"]),
                    "Volatilidad": format_pct(m["volatility"]),
                    "Sharpe": format_num(m["sharpe"], 3),
                    "Sortino": format_num(m["sortino"], 3),
                    "Treynor": format_num(m["treynor"], 3) if m["treynor"] else "N/D",
                    "VaR 95%": format_pct(m["var_95"]),
                    "Max Drawdown": format_pct(m["max_drawdown"]),
                    "Beta": format_num(m["beta"], 3),
                    "Alpha": format_pct(m["alpha"]),
                })

            # Validation check
            rules = validate_portfolio(pf, universe_df, config)
            no_cumple_count = sum(1 for r in rules if r["Estado"] == "No cumple")
            row["Cumple reglas"] = "Sí" if no_cumple_count == 0 else f"No ({no_cumple_count} reglas)"

            rows.append(row)

        if rows:
            comp_df = pd.DataFrame(rows)
            st.dataframe(comp_df, use_container_width=True, hide_index=True)
            csv = comp_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇ Descargar comparación CSV", csv, "comparacion_portafolios.csv", "text/csv")
    else:
        st.info("Guarda tus portafolios en el sidebar, luego selecciónalos aquí y haz click en 'Generar comparación'.")

# ══════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════
st.markdown("---")
st.markdown(
    '<div style="font-size:11px;color:#4a6580;text-align:center;">'
    '◈ Actinver Portfolio Lab · Reto Académico 2025 · '
    'Herramienta cuantitativa objetiva — No constituye asesoría financiera ni recomendación de inversión · '
    'Los datos automáticos provienen de yfinance / FMP / Finnhub. Los datos manuales son responsabilidad del usuario.'
    '</div>',
    unsafe_allow_html=True,
)
