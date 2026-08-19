"""Motor de perfilamiento y recomendacion.

Convierte las respuestas del cuestionario en un perfil de riesgo, y ese
perfil en alternativas de cartera a partir del universo curado de
app/universe.py y datos reales de mercado (retorno historico / volatilidad)
de app/market_data.py.

Esto es un modelo simplificado con fines educativos/demostrativos, no
constituye asesoria financiera profesional.
"""

from concurrent.futures import ThreadPoolExecutor

from app.market_data import get_indicators
from app.universe import UNIVERSO

_PUNTOS_TOLERANCIA = {"conservador": 2, "moderado": 5, "agresivo": 8}
_PUNTOS_HORIZONTE = {"corto": 1, "medio": 3, "largo": 5}
_PUNTOS_OBJETIVO = {"preservacion": 1, "ingresos": 2, "jubilacion": 3, "crecimiento": 5}
_PUNTOS_EDAD = {"55+": 1, "40-55": 2, "25-40": 4, "<25": 5}
_PUNTOS_EXPERIENCIA = {"ninguna": 1, "basica": 2, "intermedia": 3, "avanzada": 4}

PERFILES = [
    # (score_min, nombre, riesgo_min, riesgo_max, num_posiciones)
    (0, "conservador", 1, 2, 4),
    (9, "moderado", 1, 3, 5),
    (15, "crecimiento", 2, 4, 5),
    (21, "agresivo", 3, 5, 6),
]

ALTERNATIVA_RECOMENDADA_POR_PERFIL = {
    "conservador": "Defensiva",
    "moderado": "Balanceada",
    "crecimiento": "Balanceada",
    "agresivo": "Crecimiento",
}


def calcular_perfil(respuestas: dict) -> dict:
    tolerancia_pts = _PUNTOS_TOLERANCIA.get(respuestas["tolerancia_riesgo"], 2)
    escenario_extremo = respuestas.get("escenario_extremo")
    if escenario_extremo:
        # El cuestionario detallado repite la pregunta de tolerancia con un
        # escenario mas extremo; se promedia con la respuesta original para
        # afinar el perfil en vez de reemplazarla.
        tolerancia_pts = round((tolerancia_pts + _PUNTOS_TOLERANCIA.get(escenario_extremo, tolerancia_pts)) / 2)

    score = (
        tolerancia_pts
        + _PUNTOS_HORIZONTE.get(respuestas["horizonte"], 1)
        + _PUNTOS_OBJETIVO.get(respuestas["objetivo"], 1)
        + _PUNTOS_EDAD.get(respuestas["rango_edad"], 1)
        + _PUNTOS_EXPERIENCIA.get(respuestas["experiencia"], 1)
    )
    if respuestas.get("necesita_liquidez"):
        score -= 3
    if respuestas.get("tiene_deudas"):
        score -= 2
    score = max(score, 0)

    perfil = PERFILES[0]
    for candidato in PERFILES:
        if score >= candidato[0]:
            perfil = candidato

    return {
        "score": score,
        "perfil_resultado": perfil[1],
        "riesgo_min": perfil[2],
        "riesgo_max": perfil[3],
        "num_posiciones": perfil[4],
    }


def _enriquecer_candidatos(riesgo_min: int, riesgo_max: int, region: str | None = None) -> list[dict]:
    candidatos = [a for a in UNIVERSO if riesgo_min <= a["nivel_riesgo"] <= riesgo_max]
    if region in ("peru", "global"):
        filtrados = [a for a in candidatos if a["region"] == region]
        if len(filtrados) >= 3:
            candidatos = filtrados

    with ThreadPoolExecutor(max_workers=min(len(candidatos), 8) or 1) as executor:
        indicadores = list(executor.map(lambda a: get_indicators(a["ticker"]), candidatos))

    enriquecidos = []
    for activo, ind in zip(candidatos, indicadores):
        retorno = ind.get("retorno_1y_pct") or 0
        volatilidad = ind.get("volatilidad_pct") or 1
        calidad = retorno / volatilidad if volatilidad else 0
        enriquecidos.append({**activo, **ind, "calidad": calidad})

    enriquecidos.sort(key=lambda a: a["calidad"], reverse=True)
    return enriquecidos


def _distribuir_montos(pesos: list[float], monto_total: float) -> list[float]:
    if not pesos:
        return []
    total_peso = sum(pesos) or 1
    montos = [round(p / total_peso * monto_total / 10) * 10 for p in pesos]
    diferencia = round(monto_total - sum(montos), 2)
    idx_mayor = montos.index(max(montos))
    montos[idx_mayor] = round(max(montos[idx_mayor] + diferencia, 0), 2)
    return montos


def _razon_ticker(activo: dict) -> str:
    retorno = activo.get("retorno_1y_pct")
    volatilidad = activo.get("volatilidad_pct")
    if activo["nivel_riesgo"] <= 2:
        rol = "aporta estabilidad a la cartera"
    elif activo["nivel_riesgo"] >= 4:
        rol = "aporta potencial de crecimiento"
    else:
        rol = "equilibra riesgo y retorno"

    detalle = []
    if retorno is not None:
        detalle.append(f"retorno de {retorno}% en el ultimo año")
    if volatilidad is not None:
        detalle.append(f"volatilidad de {volatilidad}%")
    detalle_txt = " y ".join(detalle) if detalle else "sin datos historicos suficientes por ahora"

    return f"{detalle_txt.capitalize()}; {rol}."


def generar_alternativas(
    perfil_resultado: str,
    riesgo_min: int,
    riesgo_max: int,
    monto_soles: float,
    region: str | None = None,
) -> list[dict]:
    """Arma 3 formas distintas de repartir monto_soles entre los mismos
    activos (los mejores del perfil), variando cuanto peso le dan a la
    estabilidad vs. al crecimiento. Marca cual conviene mas segun el perfil.
    """
    enriquecidos = _enriquecer_candidatos(riesgo_min, riesgo_max, region)
    core = enriquecidos[:3]
    if not core or monto_soles <= 0:
        return []

    calidad_pesos = [max(a["calidad"], 0.05) for a in core]
    volatilidad_pesos = [1 / max(a.get("volatilidad_pct") or 1, 1) for a in core]
    retorno_pesos = [max(a.get("retorno_1y_pct") or 0, 0.5) for a in core]

    definiciones = [
        {
            "nombre": "Defensiva",
            "pesos": volatilidad_pesos,
            "razon_general": "Prioriza los activos con menor volatilidad dentro de tu perfil: busca minimizar caidas bruscas aunque el crecimiento sea mas lento.",
        },
        {
            "nombre": "Balanceada",
            "pesos": calidad_pesos,
            "razon_general": "Reparte tu capital segun el desempeño ajustado por riesgo de cada activo: el punto medio entre estabilidad y crecimiento.",
        },
        {
            "nombre": "Crecimiento",
            "pesos": retorno_pesos,
            "razon_general": "Concentra mas capital en el activo con mejor retorno historico dentro de tu perfil, asumiendo mas variacion a cambio de mayor potencial.",
        },
    ]

    recomendada = ALTERNATIVA_RECOMENDADA_POR_PERFIL.get(perfil_resultado, "Balanceada")

    alternativas = []
    for definicion in definiciones:
        montos = _distribuir_montos(definicion["pesos"], monto_soles)
        tickers = []
        for activo, monto in zip(core, montos):
            if monto <= 0:
                continue
            tickers.append(
                {
                    "ticker": activo["ticker"],
                    "nombre": activo["nombre"],
                    "monto_soles": monto,
                    "peso_pct": round(monto / monto_soles * 100, 1) if monto_soles else 0,
                    "retorno_1y_pct": activo.get("retorno_1y_pct"),
                    "volatilidad_pct": activo.get("volatilidad_pct"),
                    "razon": _razon_ticker(activo),
                }
            )
        alternativas.append(
            {
                "nombre": definicion["nombre"],
                "recomendada": definicion["nombre"] == recomendada,
                "razon_general": definicion["razon_general"],
                "tickers": tickers,
                "monto_total": monto_soles,
            }
        )

    return alternativas
