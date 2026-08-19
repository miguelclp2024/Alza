"""Analisis financiero para proyecciones de cartera.

Combina retorno historico a distintos plazos, volatilidad anualizada,
maxima caida historica (drawdown) y una señal de tendencia (medias moviles
50/200 dias) por ticker, con cache de 1 hora (mas pesado que el cache de
cotizaciones de app/market_data.py porque usa historial de 3 años). Es una
simulacion educativa: no es asesoria financiera real ni garantiza resultados.
"""

import time
from concurrent.futures import ThreadPoolExecutor

import yfinance as yf

from app.universe import UNIVERSO_POR_TICKER

_CACHE_TTL_SECONDS = 3600
_REQUEST_TIMEOUT_SECONDS = 10
_analisis_cache: dict[str, tuple[float, dict]] = {}

HORIZONTES = {
    "1s": {"label": "1 semana", "anios": 7 / 365},
    "1m": {"label": "1 mes", "anios": 1 / 12},
    "1a": {"label": "1 año", "anios": 1.0},
    "2a": {"label": "2 años", "anios": 2.0},
    "5a": {"label": "5 años", "anios": 5.0},
}

HORIZONTES_POR_PLAZO = {
    "corto": ["1s", "1m", "1a"],
    "medio": ["1m", "1a", "2a"],
    "largo": ["1a", "2a", "5a"],
}


def _clasificar_volatilidad(vol_pct: float) -> str:
    if vol_pct < 18:
        return "baja"
    if vol_pct < 35:
        return "media"
    return "alta"


def obtener_analisis_ticker(ticker: str) -> dict:
    now = time.time()
    cached = _analisis_cache.get(ticker)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    resultado = {
        "retorno_1y_pct": None,
        "retorno_3y_anualizado_pct": None,
        "volatilidad_pct": None,
        "volatilidad_label": "sin datos",
        "tendencia": "sin datos suficientes",
        "distancia_sma200_pct": None,
        "max_drawdown_3y_pct": None,
        "retorno_esperado_anual_pct": 0.0,
    }
    try:
        hist = yf.Ticker(ticker).history(period="3y", timeout=_REQUEST_TIMEOUT_SECONDS)
        if not hist.empty and len(hist) > 60:
            precios = hist["Close"]
            dias_totales = len(precios)

            precios_1y = precios.tail(252) if dias_totales >= 252 else precios
            retorno_1y = (precios_1y.iloc[-1] / precios_1y.iloc[0] - 1) * 100

            anios_totales = dias_totales / 252
            retorno_3y_anualizado = None
            if anios_totales > 0.5:
                retorno_total = precios.iloc[-1] / precios.iloc[0]
                if retorno_total > 0:
                    retorno_3y_anualizado = (retorno_total ** (1 / anios_totales) - 1) * 100

            retornos_diarios = precios.pct_change().dropna()
            volatilidad = retornos_diarios.std() * (252 ** 0.5) * 100

            sma50 = precios.tail(50).mean()
            sma200 = precios.tail(200).mean() if dias_totales >= 200 else precios.mean()
            precio_actual = precios.iloc[-1]
            distancia_sma200 = (precio_actual - sma200) / sma200 * 100 if sma200 else 0.0

            if sma50 > sma200 * 1.01:
                tendencia = "alcista"
            elif sma50 < sma200 * 0.99:
                tendencia = "bajista"
            else:
                tendencia = "lateral"

            maximo_acumulado = precios.cummax()
            drawdown = (precios - maximo_acumulado) / maximo_acumulado
            max_drawdown = float(drawdown.min()) * 100

            if retorno_3y_anualizado is not None:
                # 60% peso al historial de 3 años (mas estable), 40% al ultimo año (mas reciente)
                retorno_esperado = retorno_3y_anualizado * 0.6 + retorno_1y * 0.4
            else:
                retorno_esperado = retorno_1y

            resultado = {
                "retorno_1y_pct": round(float(retorno_1y), 2),
                "retorno_3y_anualizado_pct": round(float(retorno_3y_anualizado), 2)
                if retorno_3y_anualizado is not None
                else None,
                "volatilidad_pct": round(float(volatilidad), 2),
                "volatilidad_label": _clasificar_volatilidad(float(volatilidad)),
                "tendencia": tendencia,
                "distancia_sma200_pct": round(float(distancia_sma200), 2),
                "max_drawdown_3y_pct": round(max_drawdown, 2),
                "retorno_esperado_anual_pct": round(float(retorno_esperado), 2),
            }
    except Exception:
        pass

    _analisis_cache[ticker] = (now, resultado)
    return resultado


def refrescar_analisis_universo() -> None:
    from app.universe import UNIVERSO

    tickers = [a["ticker"] for a in UNIVERSO]
    with ThreadPoolExecutor(max_workers=min(len(tickers), 8) or 1) as executor:
        list(executor.map(obtener_analisis_ticker, tickers))


def _razon_detalle(d: dict) -> str:
    partes = []
    if d["retorno_1y_pct"] is not None:
        partes.append(f"subió {d['retorno_1y_pct']}% en el último año" if d["retorno_1y_pct"] >= 0 else f"cayó {abs(d['retorno_1y_pct'])}% en el último año")
    if d["retorno_3y_anualizado_pct"] is not None:
        partes.append(f"un promedio de {d['retorno_3y_anualizado_pct']}% anual en los últimos 3 años")
    frase_historial = ", con ".join(partes) if partes else "sin historial suficiente"

    frase_tendencia = {
        "alcista": f"su precio está {abs(d['distancia_sma200_pct'])}% por encima de su promedio de 200 días (tendencia alcista)",
        "bajista": f"su precio está {abs(d['distancia_sma200_pct'])}% por debajo de su promedio de 200 días (tendencia bajista)",
        "lateral": "su precio se mueve cerca de su promedio de 200 días (tendencia lateral)",
    }.get(d["tendencia"], "no hay suficiente historial para definir su tendencia")

    frase_riesgo = f"volatilidad {d['volatilidad_label']} ({d['volatilidad_pct']}% anual)" if d["volatilidad_pct"] is not None else "volatilidad desconocida"
    frase_drawdown = (
        f", y en su peor momento de los últimos 3 años llegó a caer {abs(d['max_drawdown_3y_pct'])}% desde su máximo"
        if d["max_drawdown_3y_pct"] is not None
        else ""
    )

    return f"{d['nombre']} {frase_historial}. Actualmente {frase_tendencia}, con {frase_riesgo}{frase_drawdown}."


def proyectar_cartera(posiciones: list[dict], codigo_horizonte: str) -> dict | None:
    """posiciones: lista de dicts con al menos 'ticker' y 'valor_actual' (S/)."""
    horizonte = HORIZONTES.get(codigo_horizonte)
    if not horizonte or not posiciones:
        return None

    valor_total = sum(p["valor_actual"] for p in posiciones)
    if valor_total <= 0:
        return None

    anios = horizonte["anios"]
    detalle = []
    retorno_ponderado = 0.0
    volatilidad_ponderada = 0.0
    for p in posiciones:
        analisis = obtener_analisis_ticker(p["ticker"])
        activo = UNIVERSO_POR_TICKER.get(p["ticker"], {})
        peso = p["valor_actual"] / valor_total
        retorno = analisis.get("retorno_esperado_anual_pct") or 0.0
        volatilidad = analisis.get("volatilidad_pct") or 0.0
        retorno_ponderado += peso * retorno
        volatilidad_ponderada += peso * volatilidad

        valor_proyectado_ticker = p["valor_actual"] * ((1 + retorno / 100) ** anios)

        d = {
            "ticker": p["ticker"],
            "nombre": activo.get("nombre", p["ticker"]),
            "sector": activo.get("sector"),
            "peso_pct": round(peso * 100, 1),
            "valor_hoy": round(p["valor_actual"], 2),
            "valor_proyectado": round(valor_proyectado_ticker, 2),
            "retorno_1y_pct": analisis.get("retorno_1y_pct"),
            "retorno_3y_anualizado_pct": analisis.get("retorno_3y_anualizado_pct"),
            "retorno_esperado_anual_pct": analisis.get("retorno_esperado_anual_pct"),
            "volatilidad_pct": analisis.get("volatilidad_pct"),
            "volatilidad_label": analisis.get("volatilidad_label"),
            "tendencia": analisis.get("tendencia"),
            "distancia_sma200_pct": analisis.get("distancia_sma200_pct"),
            "max_drawdown_3y_pct": analisis.get("max_drawdown_3y_pct"),
        }
        d["razon"] = _razon_detalle(d)
        detalle.append(d)

    r = retorno_ponderado / 100
    vol = volatilidad_ponderada / 100

    factor_esperado = (1 + r) ** anios
    factor_optimista = (1 + max(r + vol, -0.95)) ** anios
    factor_conservador = (1 + max(r - vol, -0.95)) ** anios

    valor_esperado = valor_total * factor_esperado
    valor_optimista = valor_total * max(factor_optimista, factor_esperado)
    valor_conservador = valor_total * min(factor_conservador, factor_esperado)

    return {
        "horizonte_codigo": codigo_horizonte,
        "horizonte_label": horizonte["label"],
        "valor_actual": round(valor_total, 2),
        "valor_esperado": round(valor_esperado, 2),
        "valor_optimista": round(valor_optimista, 2),
        "valor_conservador": round(valor_conservador, 2),
        "ganancia_esperada_soles": round(valor_esperado - valor_total, 2),
        "ganancia_esperada_pct": round((valor_esperado / valor_total - 1) * 100, 2),
        "retorno_esperado_anual_pct": round(retorno_ponderado, 2),
        "volatilidad_anual_pct": round(volatilidad_ponderada, 2),
        "detalle": detalle,
    }
