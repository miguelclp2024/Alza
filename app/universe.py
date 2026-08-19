"""Universo curado de acciones/ETFs reales sobre los que el motor de
recomendacion arma la cartera sugerida. nivel_riesgo va de 1 (mas defensivo)
a 5 (mas volatil). region: "peru" (empresas peruanas / con fuerte exposicion
a Peru) o "global" (resto), usado para el filtro geografico opcional del
cuestionario detallado.
"""

UNIVERSO = [
    # --- Defensivos / bajo riesgo ---
    {"ticker": "BIL", "nombre": "SPDR Bloomberg 1-3 Month T-Bill ETF", "sector": "Renta fija corto plazo", "nivel_riesgo": 1, "region": "global"},
    {"ticker": "AGG", "nombre": "iShares Core U.S. Aggregate Bond ETF", "sector": "Renta fija", "nivel_riesgo": 1, "region": "global"},
    {"ticker": "VYM", "nombre": "Vanguard High Dividend Yield ETF", "sector": "Dividendos", "nivel_riesgo": 2, "region": "global"},
    {"ticker": "JNJ", "nombre": "Johnson & Johnson", "sector": "Salud", "nivel_riesgo": 2, "region": "global"},
    {"ticker": "PG", "nombre": "Procter & Gamble", "sector": "Consumo defensivo", "nivel_riesgo": 2, "region": "global"},
    {"ticker": "KO", "nombre": "Coca-Cola", "sector": "Consumo defensivo", "nivel_riesgo": 2, "region": "global"},
    {"ticker": "PEP", "nombre": "PepsiCo", "sector": "Consumo defensivo", "nivel_riesgo": 2, "region": "global"},
    {"ticker": "WMT", "nombre": "Walmart", "sector": "Retail", "nivel_riesgo": 2, "region": "global"},
    # --- Moderado ---
    {"ticker": "SPY", "nombre": "SPDR S&P 500 ETF", "sector": "Mercado amplio EE.UU.", "nivel_riesgo": 3, "region": "global"},
    {"ticker": "VTI", "nombre": "Vanguard Total Stock Market ETF", "sector": "Mercado amplio EE.UU.", "nivel_riesgo": 3, "region": "global"},
    {"ticker": "JPM", "nombre": "JPMorgan Chase", "sector": "Financiero", "nivel_riesgo": 3, "region": "global"},
    {"ticker": "V", "nombre": "Visa", "sector": "Financiero / pagos", "nivel_riesgo": 3, "region": "global"},
    {"ticker": "HD", "nombre": "Home Depot", "sector": "Retail", "nivel_riesgo": 3, "region": "global"},
    {"ticker": "BAP", "nombre": "Credicorp (Peru)", "sector": "Financiero Peru", "nivel_riesgo": 3, "region": "peru"},
    {"ticker": "SCCO", "nombre": "Southern Copper (mineria Peru)", "sector": "Mineria Peru", "nivel_riesgo": 3, "region": "peru"},
    # --- Crecimiento / mayor riesgo ---
    {"ticker": "AAPL", "nombre": "Apple", "sector": "Tecnologia", "nivel_riesgo": 4, "region": "global"},
    {"ticker": "MSFT", "nombre": "Microsoft", "sector": "Tecnologia", "nivel_riesgo": 4, "region": "global"},
    {"ticker": "GOOGL", "nombre": "Alphabet (Google)", "sector": "Tecnologia", "nivel_riesgo": 4, "region": "global"},
    {"ticker": "AMZN", "nombre": "Amazon", "sector": "Tecnologia / retail", "nivel_riesgo": 4, "region": "global"},
    {"ticker": "BVN", "nombre": "Buenaventura (mineria Peru)", "sector": "Mineria Peru", "nivel_riesgo": 4, "region": "peru"},
    # --- Agresivo / alto riesgo ---
    {"ticker": "NVDA", "nombre": "NVIDIA", "sector": "Tecnologia / semiconductores", "nivel_riesgo": 5, "region": "global"},
    {"ticker": "META", "nombre": "Meta Platforms", "sector": "Tecnologia", "nivel_riesgo": 5, "region": "global"},
    {"ticker": "TSLA", "nombre": "Tesla", "sector": "Automotriz / tecnologia", "nivel_riesgo": 5, "region": "global"},
]

UNIVERSO_POR_TICKER = {a["ticker"]: a for a in UNIVERSO}
