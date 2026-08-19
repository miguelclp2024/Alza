import os
import secrets

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cumbre_capital.db")

# Tipo de cambio aproximado USD/PEN usado solo para mostrar precios de
# acciones (cotizadas en USD) dentro de una billetera denominada en soles.
# Es un valor fijo de referencia para la demo, no una tasa de cambio en vivo.
TIPO_CAMBIO_USD_PEN = float(os.getenv("TIPO_CAMBIO_USD_PEN", "3.75"))

# Este proyecto es una demo educativa: el dinero y las ordenes de compra/venta
# son simulados. No mueve dinero real ni ejecuta ordenes en un broker real.
MODO_DEMO = True
