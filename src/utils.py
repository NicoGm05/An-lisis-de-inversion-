"""
utils.py – Helpers: config loader, CSS injection, formatters.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
import yaml

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    """Load config.yaml; fall back to defaults if missing."""
    cfg_path = BASE_DIR / "config.yaml"
    defaults = {
        "api_keys": {"financial_modeling_prep": "", "alpha_vantage": "", "finnhub": ""},
        "portfolio": {
            "total_capital": 1_000_000,
            "base_currency": "MXN",
            "target_equity_pct": 0.40,
            "target_fixed_income_pct": 0.60,
        },
        "market_data": {
            "historical_years": 5,
            "default_risk_free_rate": 0.0,
            "default_benchmark": "ACWI",
        },
        "cache": {"enabled": True, "cache_days_valid": 1, "cache_dir": "data/cache"},
    }
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        # Deep merge
        for k, v in user_cfg.items():
            if isinstance(v, dict) and k in defaults:
                defaults[k].update(v)
            else:
                defaults[k] = v
    # Override with environment variables if set
    for key in ("FMP_API_KEY", "ALPHA_VANTAGE_KEY", "FINNHUB_KEY"):
        env_val = os.environ.get(key, "")
        if env_val:
            mapping = {
                "FMP_API_KEY": "financial_modeling_prep",
                "ALPHA_VANTAGE_KEY": "alpha_vantage",
                "FINNHUB_KEY": "finnhub",
            }
            defaults["api_keys"][mapping[key]] = env_val
    return defaults


# ──────────────────────────────────────────────
# Formatters
# ──────────────────────────────────────────────

def format_pct(value, decimals: int = 2) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return "N/D"
    return f"{value * 100:.{decimals}f}%"


def format_mxn(value) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return "N/D"
    return f"${value:,.0f} MXN"


def format_num(value, decimals: int = 4) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return "N/D"
    return f"{value:.{decimals}f}"


def status_badge(status: str) -> str:
    """Return HTML badge for a status string."""
    colors = {
        "Cumple": ("#00d26a", "#0a1f14"),
        "No cumple": ("#ff4d4f", "#1f0a0a"),
        "Revisar": ("#f0a500", "#1f1400"),
        "N/D": ("#6b7280", "#111827"),
    }
    color, bg = colors.get(status, ("#6b7280", "#111827"))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color};'
        f'padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;">'
        f"{status}</span>"
    )


def source_badge(source: str) -> str:
    colors = {
        "yfinance": ("#60a5fa", "#0d1f3c"),
        "Manual": ("#f0a500", "#1f1400"),
        "FMP": ("#a78bfa", "#1a0d3c"),
        "Cache": ("#6b7280", "#111827"),
        "N/D": ("#6b7280", "#111827"),
    }
    color, bg = colors.get(source, ("#6b7280", "#111827"))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color};'
        f'padding:1px 6px;border-radius:3px;font-size:11px;">{source}</span>'
    )


# ──────────────────────────────────────────────
# CSS Injection
# ──────────────────────────────────────────────

def inject_css():
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500;600&family=Barlow:wght@300;400;500&display=swap" rel="stylesheet">

        <style>
        /* ── Root ── */
        :root {
            --navy: #080d16;
            --card: #0d1626;
            --card2: #111f36;
            --border: #1a2f4a;
            --amber: #f0a500;
            --amber-dim: #7a5200;
            --text: #cdd5e0;
            --text-dim: #6b7a8d;
            --green: #00d26a;
            --red: #ff4d4f;
            --blue: #60a5fa;
            --font-display: 'Barlow Condensed', sans-serif;
            --font-body: 'Barlow', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }

        /* ── Global ── */
        html, body, [class*="css"] {
            font-family: var(--font-body) !important;
            background-color: var(--navy) !important;
            color: var(--text) !important;
        }

        /* ── Sidebar ── */
        [data-testid="stSidebar"] {
            background: var(--card) !important;
            border-right: 1px solid var(--border) !important;
        }

        /* ── Cards / Containers ── */
        .metric-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 8px;
        }
        .metric-label {
            font-family: var(--font-body);
            font-size: 11px;
            font-weight: 500;
            letter-spacing: 0.08em;
            color: var(--text-dim);
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        .metric-value {
            font-family: var(--font-mono);
            font-size: 22px;
            font-weight: 600;
            color: var(--amber);
            line-height: 1.2;
        }
        .metric-sub {
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--text-dim);
            margin-top: 2px;
        }

        /* ── Section Headers ── */
        .section-header {
            font-family: var(--font-display);
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 0.04em;
            color: var(--amber);
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
            margin-bottom: 16px;
            text-transform: uppercase;
        }
        .sub-header {
            font-family: var(--font-display);
            font-size: 18px;
            font-weight: 600;
            color: var(--text);
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin: 12px 0 8px 0;
        }

        /* ── Sector Block ── */
        .sector-block {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 10px;
        }
        .sector-label {
            font-family: var(--font-display);
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--blue);
            margin-bottom: 8px;
        }

        /* ── Alert boxes ── */
        .alert-error {
            background: #1f0a0a;
            border: 1px solid var(--red);
            border-left: 4px solid var(--red);
            color: #fca5a5;
            padding: 10px 14px;
            border-radius: 4px;
            font-size: 13px;
            margin: 8px 0;
        }
        .alert-warn {
            background: #1f1400;
            border: 1px solid var(--amber);
            border-left: 4px solid var(--amber);
            color: #fcd34d;
            padding: 10px 14px;
            border-radius: 4px;
            font-size: 13px;
            margin: 8px 0;
        }
        .alert-info {
            background: #0d1f3c;
            border: 1px solid var(--blue);
            border-left: 4px solid var(--blue);
            color: #93c5fd;
            padding: 10px 14px;
            border-radius: 4px;
            font-size: 13px;
            margin: 8px 0;
        }
        .alert-ok {
            background: #0a1f14;
            border: 1px solid var(--green);
            border-left: 4px solid var(--green);
            color: #6ee7b7;
            padding: 10px 14px;
            border-radius: 4px;
            font-size: 13px;
            margin: 8px 0;
        }

        /* ── Progress bar ── */
        .progress-wrap {
            background: var(--card2);
            border-radius: 4px;
            height: 8px;
            margin: 4px 0 8px 0;
            overflow: hidden;
        }
        .progress-bar {
            height: 8px;
            border-radius: 4px;
            background: var(--amber);
            transition: width 0.4s ease;
        }
        .progress-bar.ok { background: var(--green); }
        .progress-bar.over { background: var(--red); }

        /* ── Tables ── */
        .stDataFrame { border: 1px solid var(--border) !important; border-radius: 8px; }

        /* ── Tabs ── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            border-bottom: 1px solid var(--border);
        }
        .stTabs [data-baseweb="tab"] {
            font-family: var(--font-display) !important;
            font-weight: 600;
            letter-spacing: 0.06em;
            padding: 8px 16px;
            border-radius: 4px 4px 0 0;
            color: var(--text-dim) !important;
            background: transparent !important;
        }
        .stTabs [aria-selected="true"] {
            color: var(--amber) !important;
            border-bottom: 2px solid var(--amber) !important;
        }

        /* ── Number inputs ── */
        input[type="number"] { font-family: var(--font-mono) !important; }

        /* ── Headline ── */
        .app-headline {
            font-family: var(--font-display);
            font-size: 42px;
            font-weight: 700;
            letter-spacing: 0.06em;
            color: var(--amber);
            text-transform: uppercase;
            margin: 0;
            line-height: 1;
        }
        .app-sub {
            font-family: var(--font-body);
            font-size: 14px;
            color: var(--text-dim);
            margin-top: 4px;
        }

        /* ── Divider ── */
        hr { border-color: var(--border) !important; }

        /* ── Scrollbar ── */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--navy); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="metric-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {sub_html}
    </div>
    """


def render_progress(current_pct: float, target_pct: float, label: str = "") -> str:
    pct = min(current_pct / target_pct * 100, 120) if target_pct > 0 else 0
    css_class = "ok" if abs(current_pct - target_pct) < 0.005 else ("over" if current_pct > target_pct else "")
    return f"""
    <div style="font-size:12px;color:var(--text-dim);margin-bottom:2px;">{label}<span style="float:right;font-family:var(--font-mono);">{current_pct*100:.1f}% / {target_pct*100:.0f}%</span></div>
    <div class="progress-wrap"><div class="progress-bar {css_class}" style="width:{pct}%;"></div></div>
    """
