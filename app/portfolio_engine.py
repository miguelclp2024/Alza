"""Ejecucion SIMULADA de depositos, compras y ventas, y calculo de valor de
cartera con precios reales de mercado. Ninguna funcion de este archivo mueve
dinero real ni se conecta a un broker: todo se registra en la base de datos
local del usuario.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import TIPO_CAMBIO_USD_PEN
from app.market_data import get_quote
from app.models import PortfolioSnapshot, Position, Transaction, User
from app.universe import UNIVERSO_POR_TICKER


class SaldoInsuficienteError(Exception):
    pass


class PosicionInsuficienteError(Exception):
    pass


class TickerInvalidoError(Exception):
    pass


def depositar(db: Session, user: User, monto_soles: float) -> Transaction:
    if monto_soles <= 0:
        raise ValueError("El monto a depositar debe ser positivo")
    user.saldo_disponible += monto_soles
    tx = Transaction(
        user_id=user.id,
        ticker="SOLES",
        nombre="Deposito de fondos (simulado)",
        tipo="deposito",
        cantidad=0,
        precio=0,
        monto_total=monto_soles,
    )
    db.add(tx)
    db.commit()
    return tx


def _precio_en_soles(ticker: str) -> float:
    cotizacion = get_quote(ticker)
    precio_usd = cotizacion.get("precio")
    if precio_usd is None:
        raise TickerInvalidoError(f"No se pudo obtener el precio actual de {ticker}")
    return round(precio_usd * TIPO_CAMBIO_USD_PEN, 2)


def comprar(db: Session, user: User, ticker: str, monto_soles: float) -> Transaction:
    activo = UNIVERSO_POR_TICKER.get(ticker)
    if not activo:
        raise TickerInvalidoError(f"{ticker} no esta disponible en el universo de inversion")
    if monto_soles <= 0:
        raise ValueError("El monto a invertir debe ser positivo")
    if monto_soles > user.saldo_disponible:
        raise SaldoInsuficienteError("Saldo disponible insuficiente para esta operacion")

    precio_soles = _precio_en_soles(ticker)
    cantidad = round(monto_soles / precio_soles, 6)

    posicion = db.query(Position).filter_by(user_id=user.id, ticker=ticker).first()
    if posicion:
        costo_previo = posicion.cantidad * posicion.precio_promedio_compra
        nueva_cantidad = posicion.cantidad + cantidad
        posicion.precio_promedio_compra = round((costo_previo + monto_soles) / nueva_cantidad, 4)
        posicion.cantidad = nueva_cantidad
    else:
        posicion = Position(
            user_id=user.id,
            ticker=ticker,
            nombre=activo["nombre"],
            cantidad=cantidad,
            precio_promedio_compra=precio_soles,
        )
        db.add(posicion)

    user.saldo_disponible -= monto_soles
    tx = Transaction(
        user_id=user.id,
        ticker=ticker,
        nombre=activo["nombre"],
        tipo="compra",
        cantidad=cantidad,
        precio=precio_soles,
        monto_total=monto_soles,
    )
    db.add(tx)
    db.commit()
    return tx


def vender(db: Session, user: User, ticker: str, cantidad: float) -> Transaction:
    posicion = db.query(Position).filter_by(user_id=user.id, ticker=ticker).first()
    if not posicion or cantidad <= 0 or cantidad > posicion.cantidad + 1e-9:
        raise PosicionInsuficienteError("No tienes suficiente cantidad de este activo para vender")

    activo = UNIVERSO_POR_TICKER.get(ticker, {"nombre": ticker})
    precio_soles = _precio_en_soles(ticker)
    monto_total = round(precio_soles * cantidad, 2)

    posicion.cantidad -= cantidad
    if posicion.cantidad <= 1e-9:
        db.delete(posicion)

    user.saldo_disponible += monto_total
    tx = Transaction(
        user_id=user.id,
        ticker=ticker,
        nombre=activo["nombre"],
        tipo="venta",
        cantidad=cantidad,
        precio=precio_soles,
        monto_total=monto_total,
    )
    db.add(tx)
    db.commit()
    return tx


def obtener_resumen_cartera(db: Session, user: User) -> dict:
    posiciones = db.query(Position).filter_by(user_id=user.id).all()

    detalle = []
    valor_posiciones = 0.0
    costo_total = 0.0
    for p in posiciones:
        precio_actual = _precio_en_soles(p.ticker) if p.cantidad > 0 else 0
        valor_actual = round(precio_actual * p.cantidad, 2)
        costo = round(p.precio_promedio_compra * p.cantidad, 2)
        ganancia = round(valor_actual - costo, 2)
        ganancia_pct = round((ganancia / costo) * 100, 2) if costo else 0.0
        detalle.append(
            {
                "ticker": p.ticker,
                "nombre": p.nombre,
                "cantidad": p.cantidad,
                "precio_promedio_compra": p.precio_promedio_compra,
                "precio_actual": precio_actual,
                "valor_actual": valor_actual,
                "ganancia_soles": ganancia,
                "ganancia_pct": ganancia_pct,
                "abierta_en": p.abierta_en,
            }
        )
        valor_posiciones += valor_actual
        costo_total += costo

    valor_total = round(valor_posiciones + user.saldo_disponible, 2)
    ganancia_total = round(valor_posiciones - costo_total, 2)
    ganancia_total_pct = round((ganancia_total / costo_total) * 100, 2) if costo_total else 0.0

    return {
        "posiciones": detalle,
        "saldo_disponible": round(user.saldo_disponible, 2),
        "valor_posiciones": round(valor_posiciones, 2),
        "valor_total": valor_total,
        "ganancia_total_soles": ganancia_total,
        "ganancia_total_pct": ganancia_total_pct,
    }


def registrar_snapshot_si_corresponde(db: Session, user: User, valor_total: float) -> None:
    hoy = datetime.now(timezone.utc).date()
    ultimo = (
        db.query(PortfolioSnapshot)
        .filter_by(user_id=user.id)
        .order_by(PortfolioSnapshot.fecha.desc())
        .first()
    )
    if ultimo and ultimo.fecha.date() == hoy:
        ultimo.valor_total = valor_total
    else:
        db.add(PortfolioSnapshot(user_id=user.id, valor_total=valor_total))
    db.commit()
