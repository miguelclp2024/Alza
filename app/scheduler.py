"""Hilos de fondo que mantienen los caches de mercado actualizados mientras
el servidor esta corriendo:
- cotizaciones/indicadores basicos (app/market_data.py) cada 60 segundos.
- analisis financiero para proyecciones (app/analisis.py) cada hora.
"""

import threading
import time

from app.analisis import refrescar_analisis_universo
from app.market_data import refrescar_universo

_INTERVALO_COTIZACIONES_SEGUNDOS = 60
_INTERVALO_ANALISIS_SEGUNDOS = 3600


def _loop(funcion, intervalo_segundos):
    while True:
        try:
            funcion()
        except Exception:
            pass
        time.sleep(intervalo_segundos)


def iniciar_actualizacion_periodica() -> None:
    threading.Thread(
        target=_loop, args=(refrescar_universo, _INTERVALO_COTIZACIONES_SEGUNDOS), daemon=True
    ).start()
    threading.Thread(
        target=_loop, args=(refrescar_analisis_universo, _INTERVALO_ANALISIS_SEGUNDOS), daemon=True
    ).start()
