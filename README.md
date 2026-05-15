# Actinver Portfolio Lab

Constructor cuantitativo dinámico de portafolios para el reto académico Actinver.

> **Herramienta objetiva**: no emite recomendaciones, no inventa datos. Muestra N/D cuando no hay datos disponibles.

---

## Características

- **Constructor dinámico**: selecciona activos por sector, asigna pesos, y todas las métricas se recalculan en tiempo real.
- **49 activos precargados**: 38 Renta Variable (7 sectores) + 11 Renta Fija (CETES, BONDES, UDIBONOS, ETFs bonos, Fondos Actinver).
- **Validación de reglas**: semáforo Cumple/No cumple/Revisar para todas las restricciones del reto (60% RF / 40% RV, máx 10% por activo RV, mín 4 sectores, etc.).
- **Métricas cuantitativas**: Rendimiento anualizado, CAGR, Volatilidad, Sharpe, Sortino, Treynor, VaR 95% y 99%, Max Drawdown, Beta, Alpha, Correlación.
- **Datos históricos**: yfinance (5 años), con caché local y advertencia si hay menos datos disponibles.
- **Fundamentales**: FMP / Finnhub (requiere API key), N/D para campos no disponibles.
- **Multi-portafolio**: crea y compara Portafolio A, B, C y Final.
- **Instrumentos manuales**: CETES, BONDES, UDIBONOS y fondos Actinver con captura manual de tasa/rendimiento, marcados claramente como "Manual".

---

## Instalación

```bash
# 1. Clona / accede a la carpeta del proyecto
cd "/Users/nicolasgalvez/Desktop/Análisis de inversion "

# 2. (Recomendado) Crea un entorno virtual
python3 -m venv venv
source venv/bin/activate      # Mac/Linux
# venv\Scripts\activate       # Windows

# 3. Instala dependencias
pip install -r requirements.txt

# 4. Ejecutar la aplicación
streamlit run app.py
```

La aplicación se abre automáticamente en `http://localhost:8501`.

---

## Configuración (config.yaml)

Edita `config.yaml` para:
- Agregar tus API keys (FMP, Finnhub, Alpha Vantage)
- Ajustar capital, moneda, años históricos, tasa libre de riesgo, caché

También puedes usar variables de entorno: `FMP_API_KEY`, `ALPHA_VANTAGE_KEY`, `FINNHUB_KEY`.

### APIs gratuitas disponibles

| API | URL | Uso |
|-----|-----|-----|
| Financial Modeling Prep | https://financialmodelingprep.com | Fundamentales (P/E, ROE, etc.) |
| Finnhub | https://finnhub.io | Fundamentales alternativos |
| yfinance | Incluido | Precios históricos (sin API key) |

---

## Estructura del proyecto

```
Análisis de inversion /
├── app.py                    # Aplicación principal Streamlit
├── config.yaml               # Configuración (API keys, capital, caché)
├── requirements.txt          # Dependencias Python
├── README.md                 # Este archivo
├── .streamlit/
│   └── config.toml           # Tema oscuro Streamlit
├── data/
│   ├── assets_universe.csv   # Universo de 49 activos candidatos
│   ├── manual_fixed_income.csv # Datos manuales de renta fija
│   ├── portfolios.csv        # Portafolios guardados
│   └── cache/               # Caché de precios (auto-generado)
└── src/
    ├── utils.py              # CSS, formatters, config loader
    ├── data_loader.py        # Carga/guardado de CSVs
    ├── market_data.py        # yfinance + caché
    ├── fundamentals.py       # FMP + Finnhub
    ├── portfolio_math.py     # Todos los cálculos financieros
    ├── validations.py        # Validación de reglas del reto
    └── charts.py             # Gráficas Plotly
```

---

## Instrumentos manuales

CETES, BONDES F, UDIBONOS y fondos Actinver **no tienen feed automático de precios históricos**. Para estos:
1. Agrégralos en el Constructor (pestaña RF)
2. Captura la tasa/rendimiento anual manualmente
3. La app los marcará como "Manual" y no inventará datos históricos

Fuentes oficiales:
- CETES: [cetesdirecto.mx](https://cetesdirecto.mx) o [Banxico](https://www.banxico.org.mx)
- BONDES / UDIBONOS: [Banxico — Tasas](https://www.banxico.org.mx/SieInternet/)
- Fondos Actinver: [actinver.com](https://www.actinver.com)

---

## Notas importantes

- **DOG (ProShares Short Dow30)** aparece en el universo marcado como "No permitido". La app bloqueará su inclusión en el portafolio.
- **COST = Costco** | **COST.L = Costain Group (RU)** — tickers distintos, no confundir.
- **ACTINVER_DEUDA_CP / ACTINVER_LIQUIDEZ / ACTINVER_UDIS** son placeholders. Edita el nombre/clave según el prospecto oficial del fondo.
- Los datos en caché se guardan en `data/cache/`. Borra los archivos de caché o usa "Actualizar datos" para refrescar.

## Exportar Reportes

- Puedes exportar las métricas y la distribución a **CSV** en varios lugares de la interfaz.
- En la barra lateral (Sidebar), presiona **Generar HTML** y luego **Descargar resumen HTML** para recopilar métricas, cálculos y gráficas interactivas Plotly en un reporte estático independiente.

---

## Publicar en GitHub / Streamlit Cloud

Para desplegar este dashboard en la nube para el equipo Actinver:
1. Sube los archivos a un repositorio de **GitHub**.
2. Ingresa a [share.streamlit.io](https://share.streamlit.io/) e inicia sesión.
3. Haz clic en "Create app" y vincula tu repositorio, la rama base y **`app.py`** como archivo principal.
4. Opcional: Ve a "Advanced settings" e introduce tus Secret keys de APIs (las mismas del config.yaml).
5. Haz clic en **Deploy**.

---

## Disclaimer

Esta herramienta es exclusivamente para uso académico en el reto Actinver. No constituye asesoría financiera, recomendación de inversión ni análisis financiero profesional. Los datos automáticos provienen de yfinance, FMP y Finnhub. El usuario es responsable de verificar la precisión de los datos manuales capturados.
