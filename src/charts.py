"""
charts.py – All Plotly chart functions. Returns go.Figure objects.
Uses dark Bloomberg-fintech theme throughout.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ── Shared theme ──
DARK_BG = "#080d16"
CARD_BG = "#0d1626"
BORDER = "#1a2f4a"
AMBER = "#f0a500"
AMBER_DIM = "#7a5200"
GREEN = "#00d26a"
RED = "#ff4d4f"
BLUE = "#60a5fa"
PURPLE = "#a78bfa"
TEXT = "#cdd5e0"
TEXT_DIM = "#6b7a8d"

PALETTE = [AMBER, BLUE, GREEN, "#34d399", PURPLE, "#fb923c",
           "#f472b6", "#22d3ee", "#a3e635", "#e879f9", "#fbbf24", "#818cf8"]

LAYOUT_BASE = dict(
    paper_bgcolor=DARK_BG,
    plot_bgcolor=CARD_BG,
    font=dict(family="JetBrains Mono, monospace", color=TEXT, size=12),
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(bgcolor=DARK_BG, bordercolor=BORDER, borderwidth=1, font=dict(size=11)),
    xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, linecolor=BORDER),
    yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, linecolor=BORDER),
)

def safe_update_layout(fig: go.Figure, **kwargs) -> go.Figure:
    import copy
    layout = copy.deepcopy(LAYOUT_BASE)
    for k, v in kwargs.items():
        if isinstance(v, dict) and k in layout and isinstance(layout[k], dict):
            layout[k].update(v)
        else:
            layout[k] = v
    fig.update_layout(**layout)
    return fig

def _apply_base(fig: go.Figure, title: str = "") -> go.Figure:
    return safe_update_layout(fig, title=dict(text=title, font=dict(color=AMBER, size=15, family="Barlow Condensed, sans-serif")))


# ──────────────────────────────────────────────
# Composition Charts
# ──────────────────────────────────────────────

def chart_composition_type(portfolio_df: pd.DataFrame) -> go.Figure:
    """Pie chart: Renta Variable vs Renta Fija (and others)."""
    if portfolio_df.empty or "main_category" not in portfolio_df.columns:
        return go.Figure()
    grp = portfolio_df.groupby("main_category")["weight"].sum().reset_index()
    fig = go.Figure(go.Pie(
        labels=grp["main_category"],
        values=grp["weight"],
        hole=0.55,
        marker=dict(colors=[AMBER, BLUE, GREEN, PURPLE], line=dict(color=DARK_BG, width=2)),
        textinfo="label+percent",
        textfont=dict(size=12, family="Barlow Condensed, sans-serif"),
        hovertemplate="<b>%{label}</b><br>Peso: %{percent}<extra></extra>",
    ))
    fig.add_annotation(text="Tipo", x=0.5, y=0.5, font=dict(size=13, color=TEXT_DIM), showarrow=False)
    return _apply_base(fig, "Composición por Tipo de Activo")


def chart_composition_sector(portfolio_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart by sector."""
    if portfolio_df.empty or "sector" not in portfolio_df.columns:
        return go.Figure()
    grp = portfolio_df.groupby("sector")["weight"].sum().reset_index().sort_values("weight")
    colors = [AMBER if idx % 2 == 0 else BLUE for idx in range(len(grp))]
    fig = go.Figure(go.Bar(
        x=grp["weight"] * 100,
        y=grp["sector"],
        orientation="h",
        marker=dict(color=colors, line=dict(color=BORDER, width=1)),
        text=[f"{v:.1f}%" for v in grp["weight"] * 100],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x:.2f}%<extra></extra>",
    ))
    safe_update_layout(fig,
        title=dict(text="Composición por Sector", font=dict(color=AMBER, size=15, family="Barlow Condensed, sans-serif")),
        xaxis_title="Peso (%)", yaxis_title="",
        xaxis=dict(ticksuffix="%", gridcolor=BORDER),
    )
    return fig


def chart_composition_region(portfolio_df: pd.DataFrame) -> go.Figure:
    """Pie chart by region."""
    if portfolio_df.empty or "region" not in portfolio_df.columns:
        return go.Figure()
    grp = portfolio_df.groupby("region")["weight"].sum().reset_index()
    fig = go.Figure(go.Pie(
        labels=grp["region"],
        values=grp["weight"],
        hole=0.55,
        marker=dict(colors=PALETTE[:len(grp)], line=dict(color=DARK_BG, width=2)),
        textinfo="label+percent",
        textfont=dict(size=11, family="Barlow Condensed, sans-serif"),
        hovertemplate="<b>%{label}</b><br>Peso: %{percent}<extra></extra>",
    ))
    fig.add_annotation(text="Región", x=0.5, y=0.5, font=dict(size=13, color=TEXT_DIM), showarrow=False)
    return _apply_base(fig, "Composición por Región")


def chart_composition_currency(portfolio_df: pd.DataFrame) -> go.Figure:
    """Pie chart by currency."""
    if portfolio_df.empty or "currency" not in portfolio_df.columns:
        return go.Figure()
    grp = portfolio_df.groupby("currency")["weight"].sum().reset_index()
    colors = {
        "MXN": AMBER, "USD": BLUE, "EUR": GREEN, "GBP": PURPLE, "HKD": "#fb923c",
    }
    c = [colors.get(x, TEXT_DIM) for x in grp["currency"]]
    fig = go.Figure(go.Pie(
        labels=grp["currency"],
        values=grp["weight"],
        hole=0.55,
        marker=dict(colors=c, line=dict(color=DARK_BG, width=2)),
        textinfo="label+percent",
        textfont=dict(size=12, family="Barlow Condensed, sans-serif"),
        hovertemplate="<b>%{label}</b><br>Peso: %{percent}<extra></extra>",
    ))
    fig.add_annotation(text="Moneda", x=0.5, y=0.5, font=dict(size=13, color=TEXT_DIM), showarrow=False)
    return _apply_base(fig, "Composición por Moneda")


def chart_composition_treemap(portfolio_df: pd.DataFrame) -> go.Figure:
    """Treemap by sector > instrument."""
    if portfolio_df.empty:
        return go.Figure()
    df = portfolio_df.copy()
    df = df[df["weight"] > 0]
    if df.empty:
        return go.Figure()
    fig = px.treemap(
        df,
        path=["main_category", "sector", "ticker"],
        values="weight",
        color="weight",
        color_continuous_scale=[[0, CARD_BG], [0.5, AMBER_DIM], [1, AMBER]],
        hover_data={"weight": ":.2%"},
    )
    fig.update_traces(
        textinfo="label+percent root",
        textfont=dict(family="Barlow Condensed, sans-serif", size=13),
        marker=dict(line=dict(width=2, color=DARK_BG)),
    )
    return _apply_base(fig, "Mapa de Pesos del Portafolio")


# ──────────────────────────────────────────────
# Historical Performance
# ──────────────────────────────────────────────

def chart_historical_performance(
    port_values: Optional[pd.Series],
    bench_values: Optional[pd.Series],
    bench_label: str = "Benchmark",
    capital: float = 1_000_000,
) -> go.Figure:
    """Growth of $1M chart with optional benchmark line."""
    fig = go.Figure()
    if port_values is None or port_values.empty:
        fig.add_annotation(text="Sin datos históricos suficientes", x=0.5, y=0.5,
                           xref="paper", yref="paper", showarrow=False,
                           font=dict(color=TEXT_DIM, size=14))
        return _apply_base(fig, "Rendimiento Histórico — Crecimiento de $1,000,000 MXN")

    fig.add_trace(go.Scatter(
        x=port_values.index, y=port_values,
        name="Portafolio",
        line=dict(color=AMBER, width=2.5),
        hovertemplate="<b>Portafolio</b><br>%{x|%Y-%m-%d}<br>$%{y:,.0f} MXN<extra></extra>",
        fill="tozeroy",
        fillcolor="rgba(240,165,0,0.05)",
    ))

    if bench_values is not None and not bench_values.empty:
        # Normalize benchmark to same starting capital
        bench_norm = bench_values / bench_values.iloc[0] * capital
        fig.add_trace(go.Scatter(
            x=bench_norm.index, y=bench_norm,
            name=bench_label,
            line=dict(color=BLUE, width=1.8, dash="dash"),
            hovertemplate=f"<b>{bench_label}</b><br>%{{x|%Y-%m-%d}}<br>$%{{y:,.0f}}<extra></extra>",
        ))

    safe_update_layout(fig,
        title=dict(text="Rendimiento Histórico — Crecimiento de $1,000,000 MXN",
                   font=dict(color=AMBER, size=15, family="Barlow Condensed, sans-serif")),
        yaxis_title="Valor (MXN)",
        xaxis_title="",
        yaxis=dict(tickprefix="$", tickformat=",.0f", gridcolor=BORDER),
        hovermode="x unified",
    )
    return fig


def chart_drawdown(port_returns: Optional[pd.Series]) -> go.Figure:
    """Drawdown area chart."""
    fig = go.Figure()
    if port_returns is None or port_returns.empty:
        fig.add_annotation(text="Sin datos de drawdown", x=0.5, y=0.5,
                           xref="paper", yref="paper", showarrow=False,
                           font=dict(color=TEXT_DIM, size=14))
        return _apply_base(fig, "Drawdown del Portafolio")

    cumret = (1 + port_returns).cumprod()
    running_max = cumret.cummax()
    drawdown = (cumret - running_max) / running_max * 100

    fig.add_trace(go.Scatter(
        x=drawdown.index, y=drawdown,
        fill="tozeroy",
        fillcolor="rgba(255,77,79,0.2)",
        line=dict(color=RED, width=1.5),
        name="Drawdown",
        hovertemplate="%{x|%Y-%m-%d}<br>Drawdown: %{y:.2f}%<extra></extra>",
    ))
    safe_update_layout(fig,
        title=dict(text="Drawdown del Portafolio",
                   font=dict(color=AMBER, size=15, family="Barlow Condensed, sans-serif")),
        yaxis_title="Drawdown (%)",
        yaxis=dict(ticksuffix="%", gridcolor=BORDER),
        hovermode="x unified",
    )
    return fig


def chart_correlation_heatmap(corr_matrix: Optional[pd.DataFrame]) -> go.Figure:
    """Annotated correlation heatmap."""
    fig = go.Figure()
    if corr_matrix is None or corr_matrix.empty:
        fig.add_annotation(text="Se necesitan ≥ 2 activos con datos históricos para calcular correlaciones",
                           x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                           font=dict(color=TEXT_DIM, size=13))
        return _apply_base(fig, "Matriz de Correlaciones")

    labels = corr_matrix.columns.tolist()
    z = corr_matrix.values

    fig.add_trace(go.Heatmap(
        z=z,
        x=labels,
        y=labels,
        colorscale=[[0, RED], [0.5, CARD_BG], [1.0, GREEN]],
        zmid=0,
        zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in z],
        texttemplate="%{text}",
        textfont=dict(size=11, family="JetBrains Mono"),
        hovertemplate="<b>%{y} / %{x}</b><br>Correlación: %{z:.4f}<extra></extra>",
        colorbar=dict(
            title=dict(text="ρ", font=dict(color=TEXT_DIM)),
            tickfont=dict(color=TEXT_DIM),
            bgcolor=CARD_BG,
            bordercolor=BORDER,
        ),
    ))
    safe_update_layout(fig,
        title=dict(text="Matriz de Correlaciones",
                   font=dict(color=AMBER, size=15, family="Barlow Condensed, sans-serif")),
        xaxis=dict(tickfont=dict(size=10), side="bottom"),
        yaxis=dict(tickfont=dict(size=10), autorange="reversed"),
    )
    return fig


def chart_individual_returns(prices: pd.DataFrame, tickers: list[str]) -> go.Figure:
    """Cumulative returns per asset (normalized to 100 at start)."""
    fig = go.Figure()
    if prices.empty or not tickers:
        return _apply_base(fig, "Rendimiento Acumulado por Activo")
    for i, ticker in enumerate(tickers):
        if ticker not in prices.columns:
            continue
        s = prices[ticker].dropna()
        if len(s) < 2:
            continue
        norm = s / s.iloc[0] * 100
        fig.add_trace(go.Scatter(
            x=norm.index, y=norm,
            name=ticker,
            line=dict(color=PALETTE[i % len(PALETTE)], width=1.8),
            hovertemplate=f"<b>{ticker}</b><br>%{{x|%Y-%m-%d}}<br>%{{y:.1f}}<extra></extra>",
        ))
    safe_update_layout(fig,
        title=dict(text="Rendimiento Acumulado por Activo (base 100)",
                   font=dict(color=AMBER, size=15, family="Barlow Condensed, sans-serif")),
        yaxis_title="Índice (base 100)",
        hovermode="x unified",
    )
    return fig


def chart_portfolio_comparison(comparison_df: pd.DataFrame) -> go.Figure:
    """Grouped bar chart comparing key metrics across portfolio versions."""
    if comparison_df.empty:
        return go.Figure()
    metrics = ["Rendimiento Anualizado", "Volatilidad", "Sharpe", "VaR 95%", "Max Drawdown"]
    fig = make_subplots(rows=1, cols=len(metrics), shared_yaxes=False,
                        subplot_titles=metrics)
    for i, metric in enumerate(metrics, 1):
        if metric not in comparison_df.columns:
            continue
        fig.add_trace(go.Bar(
            x=comparison_df["Portafolio"],
            y=comparison_df[metric],
            marker=dict(color=PALETTE[:len(comparison_df)], line=dict(color=DARK_BG, width=1)),
            showlegend=False,
            hovertemplate=f"<b>%{{x}}</b><br>{metric}: %{{y:.4f}}<extra></extra>",
        ), row=1, col=i)
    safe_update_layout(fig,
        title=dict(text="Comparación de Portafolios",
                   font=dict(color=AMBER, size=15, family="Barlow Condensed, sans-serif")),
        height=350,
    )
    return fig
