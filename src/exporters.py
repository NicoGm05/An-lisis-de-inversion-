import datetime
import pandas as pd

def _to_html_table(df: pd.DataFrame, classes: str = "styled-table") -> str:
    """Safely converts a DataFrame to an HTML table string."""
    if df is None or df.empty:
        return "<p>N/D</p>"
    return df.to_html(index=False, classes=classes, border=0, escape=False)

def export_html_report(
    portfolio_name: str,
    portfolio_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    metrics_dict: dict,
    figures_dict: dict,
    fundamentals_df: pd.DataFrame,
    capital: float,
) -> str:
    """Generates a complete standalone HTML report with Plotly charts embedded."""
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # CSS Theme matching Streamlit (Dark/Amber/Blue)
    css = """
    <style>
        body { font-family: 'Inter', -apple-system, sans-serif; background-color: #080d16; color: #cdd5e0; margin: 0; padding: 40px; }
        .container { max-width: 1200px; margin: 0 auto; background-color: #0d1626; padding: 40px; border-radius: 12px; border: 1px solid #1a2f4a; }
        h1, h2, h3 { color: #f0a500; font-family: 'Barlow Condensed', sans-serif; }
        h1 { border-bottom: 2px solid #1a2f4a; padding-bottom: 10px; }
        h2 { margin-top: 40px; border-bottom: 1px solid #1a2f4a; padding-bottom: 5px; }
        .meta { color: #6b7a8d; font-size: 14px; margin-bottom: 30px; }
        
        .styled-table { width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 13px; text-align: left; }
        .styled-table thead tr { background-color: #1a2f4a; color: #cdd5e0; text-align: left; }
        .styled-table th, .styled-table td { padding: 12px 15px; border-bottom: 1px solid #1a2f4a; }
        .styled-table tbody tr:hover { background-color: #111d33; }
        
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .metric-card { background-color: #111d33; padding: 15px; border-radius: 8px; border: 1px solid #1a2f4a; }
        .metric-label { font-size: 12px; color: #6b7a8d; text-transform: uppercase; }
        .metric-value { font-size: 24px; font-weight: bold; color: #60a5fa; margin-top: 5px; }
        
        .chart-container { margin: 30px 0; background-color: #080d16; padding: 10px; border-radius: 8px; border: 1px solid #1a2f4a; }
        
        .disclaimer { margin-top: 50px; padding: 20px; font-size: 12px; color: #6b7a8d; background-color: #080d16; border-radius: 8px; border-left: 4px solid #f0a500; }
        
        .badge-cumple { color: #00d26a; font-weight: bold; }
        .badge-nocumple { color: #ff4d4f; font-weight: bold; }
        .badge-revisar { color: #f0a500; font-weight: bold; }
    </style>
    """
    
    # Activos Table
    display_df = portfolio_df.copy()
    if not display_df.empty:
        display_cols = ["ticker", "name", "main_category", "sector", "region", "currency", "weight_pct", "monto_mxn", "status", "data_source"]
        col_labels = ["Ticker", "Nombre", "Tipo", "Sector", "Región", "Moneda", "Peso (%)", "Monto (MXN)", "Estatus", "Fuente"]
        display_df = display_df[display_cols].copy()
        display_df.columns = col_labels
        display_df["Peso (%)"] = display_df["Peso (%)"].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/D")
        display_df["Monto (MXN)"] = display_df["Monto (MXN)"].apply(lambda x: f"${x:,.0f}" if pd.notnull(x) else "N/D")
    
    assets_html = _to_html_table(display_df)
    
    # Validations Table
    val_df = validation_df.copy()
    if not val_df.empty:
        def badge(s):
            if s == "Cumple": return "<span class='badge-cumple'>Cumple</span>"
            if s == "No cumple": return "<span class='badge-nocumple'>No cumple</span>"
            if s in ["Revisar", "Advertencia"]: return "<span class='badge-revisar'>Revisar</span>"
            return s
        if "Estado" in val_df.columns:
            val_df["Estado"] = val_df["Estado"].apply(badge)
    
    val_html = _to_html_table(val_df)
    
    # Fundamentals Table
    fund_df = fundamentals_df.copy()
    if not fund_df.empty:
        cols = ["ticker", "pe_ratio", "peg_ratio", "eps", "revenue_growth", "debt_equity", "operating_margin", "roe", "dividend_yield", "source"]
        valid_cols = [c for c in cols if c in fund_df.columns]
        show_fdf = fund_df[valid_cols].copy()
        fund_html = _to_html_table(show_fdf)
    else:
        fund_html = "<p>N/D (No hay métricas fundamentales disponibles)</p>"

    # Metrics
    def mfmt(val, t="num"):
        if val is None or pd.isna(val): return "N/D"
        if t == "pct": return f"{(val*100):.2f}%"
        if t == "num2": return f"{val:.2f}"
        return f"{val:.4f}"

    metrics_html = ""
    if metrics_dict:
        m = metrics_dict
        cards = [
            ("Rendim. Anualiz.", mfmt(m.get("annualized_return"), "pct")),
            ("CAGR", mfmt(m.get("cagr"), "pct")),
            ("Volatilidad", mfmt(m.get("volatility"), "pct")),
            ("Sharpe", mfmt(m.get("sharpe"), "num2")),
            ("Sortino", mfmt(m.get("sortino"), "num2")),
            ("Treynor", mfmt(m.get("treynor"), "num2") if m.get("treynor") else "N/D"),
            ("VaR 95%", mfmt(m.get("var_95"), "pct")),
            ("VaR 99%", mfmt(m.get("var_99"), "pct")),
            ("Max Drawdown", mfmt(m.get("max_drawdown"), "pct")),
            ("Beta", mfmt(m.get("beta"), "num2")),
            ("Alpha", mfmt(m.get("alpha"), "pct")),
            ("Correlación", mfmt(m.get("avg_correlation"), "num2")),
        ]
        grid = "<div class='metrics-grid'>"
        for title, val in cards:
            grid += f"<div class='metric-card'><div class='metric-label'>{title}</div><div class='metric-value'>{val}</div></div>"
        grid += "</div>"
        metrics_html = grid
    else:
        metrics_html = "<p>N/D (Sin datos históricos)</p>"

    # Charts
    charts_html = ""
    import plotly.io as pio
    for title, fig in figures_dict.items():
        if fig:
            div = pio.to_html(fig, full_html=False, include_plotlyjs="cdn" if title == list(figures_dict.keys())[0] else False)
            charts_html += f"<div class='chart-container'><h3>{title}</h3>{div}</div>"
        else:
            charts_html += f"<div class='chart-container'><h3>{title}</h3><p>Gráfica no disponible por falta de datos</p></div>"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Actinver Portfolio Lab - {portfolio_name}</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        {css}
    </head>
    <body>
        <div class="container">
            <h1>Actinver Portfolio Lab</h1>
            <div class="meta">
                <b>Portafolio:</b> {portfolio_name}<br>
                <b>Capital Inicial:</b> ${capital:,.0f} MXN<br>
                <b>Generado:</b> {now_str}
            </div>
            
            <h2>1. Distribución del Capital</h2>
            {assets_html}
            
            <h2>2. Validación de Reglas del Reto</h2>
            {val_html}
            
            <h2>3. Métricas Cuantitativas</h2>
            {metrics_html}
            
            <h2>4. Gráficas y Visualizaciones</h2>
            {charts_html}
            
            <h2>5. Datos Fundamentales (RV)</h2>
            {fund_html}
            
            <div class="disclaimer">
                <b>Aviso Académico:</b>
                Esta herramienta es exclusivamente para uso académico en el reto Actinver. No constituye asesoría financiera, recomendación de inversión ni análisis profesional. Los datos deben ser verificados por el usuario antes de ser utilizados.
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content
