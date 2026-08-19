from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), default="")
    saldo_disponible: Mapped[float] = mapped_column(Float, default=0.0)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    perfil = relationship("RiskProfile", back_populates="usuario", uselist=False)
    posiciones = relationship("Position", back_populates="usuario")
    transacciones = relationship("Transaction", back_populates="usuario")
    metas = relationship("Goal", back_populates="usuario")
    snapshots = relationship("PortfolioSnapshot", back_populates="usuario")


class RiskProfile(Base):
    __tablename__ = "risk_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    horizonte: Mapped[str] = mapped_column(String(20))  # corto, medio, largo
    capacidad_inversion_soles: Mapped[float] = mapped_column(Float)
    tolerancia_riesgo: Mapped[str] = mapped_column(String(20))  # conservador, moderado, agresivo
    objetivo: Mapped[str] = mapped_column(String(30))  # crecimiento, ingresos, preservacion, jubilacion
    rango_edad: Mapped[str] = mapped_column(String(20))
    experiencia: Mapped[str] = mapped_column(String(20))  # ninguna, basica, intermedia, avanzada
    necesita_liquidez: Mapped[bool] = mapped_column(Boolean, default=False)

    score: Mapped[int] = mapped_column(Integer)
    perfil_resultado: Mapped[str] = mapped_column(String(20))  # conservador, moderado, crecimiento, agresivo
    confirmado: Mapped[bool] = mapped_column(Boolean, default=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Cuestionario detallado (opcional, solo si el usuario dice que el resumen no es correcto)
    objetivo_especifico: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ahorro_mensual_adicional: Mapped[float | None] = mapped_column(Float, nullable=True)
    interes_geografico: Mapped[str | None] = mapped_column(String(20), nullable=True)  # peru, global, ambos
    tiene_deudas: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cuestionario_detallado: Mapped[bool] = mapped_column(Boolean, default=False)

    usuario = relationship("User", back_populates="perfil")


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ticker: Mapped[str] = mapped_column(String(15))
    nombre: Mapped[str] = mapped_column(String(120))
    cantidad: Mapped[float] = mapped_column(Float)
    precio_promedio_compra: Mapped[float] = mapped_column(Float)
    abierta_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usuario = relationship("User", back_populates="posiciones")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ticker: Mapped[str] = mapped_column(String(15))
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(10))  # compra, venta, deposito
    cantidad: Mapped[float] = mapped_column(Float, default=0.0)
    precio: Mapped[float] = mapped_column(Float, default=0.0)
    monto_total: Mapped[float] = mapped_column(Float)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usuario = relationship("User", back_populates="transacciones")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    nombre: Mapped[str] = mapped_column(String(120))
    monto_objetivo: Mapped[float] = mapped_column(Float)
    fecha_objetivo: Mapped[datetime] = mapped_column(DateTime)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usuario = relationship("User", back_populates="metas")


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    valor_total: Mapped[float] = mapped_column(Float)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usuario = relationship("User", back_populates="snapshots")
