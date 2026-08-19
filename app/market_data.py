"""Acceso a datos reales de mercado (Yahoo Finance) con cache simple en memoria.

Este modulo solo LEE precios e indicadores publicos. No coloca ordenes en
ningun broker real: las compras/ventas de la plataforma son simuladas y se
registran en la base de datos local (ver portfolio_engine.py).
"""

import socket
import time
from concurrent.futures import ThreadPoolExecutor

import yfinance as yf

# En esta maquina las rutas IPv6 hacia Yahoo Finance se quedan colgadas en vez
# de fallar rapido (IPv6 roto a nivel de red), y Python intenta IPv6 primero.
# Forzamos resolucion DNS solo a IPv4 para todo el proceso.
_getaddrinfo_original = socket.getaddrinfo


def _getaddrinfo_solo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _getaddrinfo_original(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _getaddrinfo_solo_ipv4

_CACHE_TTL_SECONDS = 90
_REQUEST_TIMEOUT_SECONDS = 8
_quote_cache: dict[str, tuple[float, dict]] = {}
_history_cache: dict[str, tuple[float, list]] = {}


def get_quote(ticker: str) -> dict:
    """Devuelve precio actual + variacion de un ticker, con cache de 10 min."""
    now = time.time()
    cached = _quote_cache.get(ticker)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    data: dict = {"ticker": ticker, "precio": None, "variacion_pct": None, "nombre": ticker}
    try:
        hist = yf.Ticker(ticker).history(period="5d", timeout=_REQUEST_TIMEOUT_SECONDS)
        if not hist.empty:
            precio = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else precio
            data["precio"] = round(precio, 2)
            if prev_close:
                data["variacion_pct"] = round((precio - prev_close) / prev_close * 100, 2)
    except Exception:
        pass

    _quote_cache[ticker] = (now, data)
    return data


def get_indicators(ticker: str) -> dict:
    """Indicadores usados por el motor de recomendacion: retorno 1y y volatilidad anualizada."""
    now = time.time()
    cached = _history_cache.get(f"ind:{ticker}")
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    resultado = {"retorno_1y_pct": None, "volatilidad_pct": None}
    try:
        hist = yf.Ticker(ticker).history(period="1y", timeout=_REQUEST_TIMEOUT_SECONDS)
        if not hist.empty and len(hist) > 5:
            precios = hist["Close"]
            retorno = (precios.iloc[-1] / precios.iloc[0] - 1) * 100
            retornos_diarios = precios.pct_change().dropna()
            volatilidad = retornos_diarios.std() * (252 ** 0.5) * 100  # anualizada
            resultado["retorno_1y_pct"] = round(float(retorno), 2)
            resultado["volatilidad_pct"] = round(float(volatilidad), 2)
    except Exception:
        pass

    _history_cache[f"ind:{ticker}"] = (now, resultado)
    return resultado


def get_price_history(ticker: str, period: str = "6mo") -> list[dict]:
    now = time.time()
    key = f"hist:{ticker}:{period}"
    cached = _history_cache.get(key)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    puntos: list[dict] = []
    try:
        hist = yf.Ticker(ticker).history(period=period, timeout=_REQUEST_TIMEOUT_SECONDS)
        for fecha, fila in hist.iterrows():
            puntos.append({"fecha": fecha.strftime("%Y-%m-%d"), "precio": round(float(fila["Close"]), 2)})
    except Exception:
        pass

    _history_cache[key] = (now, puntos)
    return puntos


def refrescar_universo() -> None:
    """Recalienta el cache de cotizaciones/indicadores de todo el universo
    curado. Pensado para llamarse en un hilo de fondo cada ~60s (ver
    app/scheduler.py) para que las paginas casi nunca esperen a Yahoo Finance.
    """
    from app.universe import UNIVERSO

    tickers = [a["ticker"] for a in UNIVERSO]
    with ThreadPoolExecutor(max_workers=min(len(tickers), 8) or 1) as executor:
        list(executor.map(get_quote, tickers))
        list(executor.map(get_indicators, tickers))
