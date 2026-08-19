from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.analisis import HORIZONTES, HORIZONTES_POR_PLAZO, proyectar_cartera
from app.auth import get_or_create_user
from app.database import get_db
from app.models import Goal, PortfolioSnapshot, Transaction
from app.portfolio_engine import (
    PosicionInsuficienteError,
    SaldoInsuficienteError,
    TickerInvalidoError,
    comprar,
    depositar,
    obtener_resumen_cartera,
    registrar_snapshot_si_corresponde,
    vender,
)
from app.scoring import PERFILES, generar_alternativas

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _requiere_perfil(request: Request, db: Session):
    user = get_or_create_user(request, db)
    if not user.perfil or not user.perfil.confirmado:
        return None
    return user


def _construir_explicacion_proyeccion(proyeccion: dict) -> str:
    tendencias = [d["tendencia"] for d in proyeccion["detalle"]]
    alcistas = tendencias.count("alcista")
    bajistas = tendencias.count("bajista")
    if alcistas > bajistas:
        resumen_tendencia = (
            "la mayoría de tus activos muestra una tendencia alcista "
            "(su precio reciente está por encima de su promedio de mediano plazo)"
        )
    elif bajistas > alcistas:
        resumen_tendencia = (
            "la mayoría de tus activos muestra una tendencia bajista "
            "(su precio reciente está por debajo de su promedio de mediano plazo)"
        )
    else:
        resumen_tendencia = "tus activos muestran una tendencia mixta o lateral"

    if proyeccion["ganancia_esperada_pct"] >= 0:
        direccion = f"un crecimiento estimado de {proyeccion['ganancia_esperada_pct']}%"
    else:
        direccion = f"una posible caída estimada de {abs(proyeccion['ganancia_esperada_pct'])}%"

    drawdowns = [d["max_drawdown_3y_pct"] for d in proyeccion["detalle"] if d.get("max_drawdown_3y_pct") is not None]
    frase_riesgo = ""
    if drawdowns:
        peor = min(drawdowns)
        activo_peor = next(
            d["ticker"] for d in proyeccion["detalle"] if d.get("max_drawdown_3y_pct") == peor
        )
        frase_riesgo = (
            f" Como referencia de riesgo real: en los últimos 3 años, el activo más volátil de tu cartera "
            f"({activo_peor}) llegó a caer {abs(peor)}% desde su máximo antes de recuperarse — algo similar "
            f"podría volver a pasar."
        )

    return (
        f"Con el retorno histórico ponderado de tu cartera ({proyeccion['retorno_esperado_anual_pct']}% anual) "
        f"y su volatilidad ({proyeccion['volatilidad_anual_pct']}% anual), el modelo proyecta {direccion} "
        f"para {proyeccion['horizonte_label']}. Ahora mismo, {resumen_tendencia}.{frase_riesgo}"
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, horizonte: str = "", db: Session = Depends(get_db)):
    user = _requiere_perfil(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    resumen = obtener_resumen_cartera(db, user)
    registrar_snapshot_si_corresponde(db, user, resumen["valor_total"])

    historial = (
        db.query(Transaction)
        .filter_by(user_id=user.id)
        .order_by(Transaction.fecha.desc())
        .limit(15)
        .all()
    )
    metas = db.query(Goal).filter_by(user_id=user.id).order_by(Goal.fecha_objetivo).all()

    snapshots = (
        db.query(PortfolioSnapshot)
        .filter_by(user_id=user.id)
        .order_by(PortfolioSnapshot.fecha.asc())
        .all()
    )
    grafico_fechas = [s.fecha.strftime("%Y-%m-%d") for s in snapshots]
    grafico_valores = [s.valor_total for s in snapshots]

    codigos_horizonte = HORIZONTES_POR_PLAZO.get(user.perfil.horizonte, HORIZONTES_POR_PLAZO["medio"])
    horizontes_disponibles = [{"codigo": c, "label": HORIZONTES[c]["label"]} for c in codigos_horizonte]

    proyeccion = None
    explicacion_proyeccion = None
    if horizonte in codigos_horizonte and resumen["posiciones"]:
        proyeccion = proyectar_cartera(resumen["posiciones"], horizonte)
        if proyeccion:
            explicacion_proyeccion = _construir_explicacion_proyeccion(proyeccion)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "resumen": resumen,
            "historial": historial,
            "metas": metas,
            "grafico_fechas": grafico_fechas,
            "grafico_valores": grafico_valores,
            "hoy": datetime.utcnow(),
            "horizontes_disponibles": horizontes_disponibles,
            "horizonte_activo": horizonte,
            "proyeccion": proyeccion,
            "explicacion_proyeccion": explicacion_proyeccion,
        },
    )


@router.get("/invertir/guia", response_class=HTMLResponse)
def guia_inversion_real(request: Request, db: Session = Depends(get_db)):
    user = _requiere_perfil(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    resumen = obtener_resumen_cartera(db, user)
    mercado = user.perfil.interes_geografico or "ambos"
    return templates.TemplateResponse(
        "guia_inversion_real.html",
        {"request": request, "user": user, "posiciones": resumen["posiciones"], "mercado": mercado},
    )


def _banda_de_riesgo(perfil_resultado: str):
    return next((p for p in PERFILES if p[1] == perfil_resultado), PERFILES[0])


@router.get("/invertir", response_class=HTMLResponse)
def invertir_form(request: Request, mensaje: str = "", error: str = "", db: Session = Depends(get_db)):
    user = _requiere_perfil(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    perfil = user.perfil
    resumen = obtener_resumen_cartera(db, user)

    banda = _banda_de_riesgo(perfil.perfil_resultado)
    region = perfil.interes_geografico if perfil.interes_geografico in ("peru", "global") else None
    alternativas = generar_alternativas(
        perfil.perfil_resultado, banda[2], banda[3], resumen["saldo_disponible"], region
    )

    return templates.TemplateResponse(
        "invertir.html",
        {
            "request": request,
            "user": user,
            "perfil": perfil,
            "alternativas": alternativas,
            "resumen": resumen,
            "mensaje": mensaje,
            "error": error,
        },
    )


@router.post("/invertir/depositar")
def depositar_submit(request: Request, monto: float = Form(...), db: Session = Depends(get_db)):
    user = _requiere_perfil(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    try:
        depositar(db, user, monto)
        return RedirectResponse(url="/invertir?mensaje=Deposito simulado registrado", status_code=303)
    except ValueError as e:
        return RedirectResponse(url=f"/invertir?error={quote(str(e))}", status_code=303)


@router.post("/invertir/vender")
def vender_submit(
    request: Request,
    ticker: str = Form(...),
    cantidad: float = Form(...),
    db: Session = Depends(get_db),
):
    user = _requiere_perfil(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    try:
        vender(db, user, ticker.upper(), cantidad)
        mensaje = quote(f"Venta simulada de {ticker.upper()} realizada")
        return RedirectResponse(url=f"/invertir?mensaje={mensaje}", status_code=303)
    except (PosicionInsuficienteError, TickerInvalidoError) as e:
        return RedirectResponse(url=f"/invertir?error={quote(str(e))}", status_code=303)


@router.post("/invertir/aplicar-alternativa", response_class=HTMLResponse)
def aplicar_alternativa(request: Request, alternativa: str = Form(...), db: Session = Depends(get_db)):
    user = _requiere_perfil(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    perfil = user.perfil
    resumen = obtener_resumen_cartera(db, user)
    banda = _banda_de_riesgo(perfil.perfil_resultado)
    region = perfil.interes_geografico if perfil.interes_geografico in ("peru", "global") else None
    alternativas = generar_alternativas(
        perfil.perfil_resultado, banda[2], banda[3], resumen["saldo_disponible"], region
    )
    elegida = next((a for a in alternativas if a["nombre"] == alternativa), None)

    if not elegida or not elegida["tickers"]:
        return RedirectResponse(url="/invertir?error=No se pudo aplicar esa alternativa", status_code=303)

    try:
        for item in elegida["tickers"]:
            comprar(db, user, item["ticker"], item["monto_soles"])
    except (SaldoInsuficienteError, TickerInvalidoError, ValueError) as e:
        return RedirectResponse(url=f"/invertir?error={quote(str(e))}", status_code=303)

    return templates.TemplateResponse(
        "resultado_alternativa.html", {"request": request, "user": user, "alternativa": elegida}
    )


@router.post("/invertir/deshacer")
def deshacer_alternativa(request: Request, db: Session = Depends(get_db)):
    """Vende de vuelta todas las posiciones abiertas (todo simulado) para que
    el usuario pueda explorar una alternativa distinta con su saldo completo."""
    user = _requiere_perfil(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    resumen = obtener_resumen_cartera(db, user)
    for p in resumen["posiciones"]:
        try:
            vender(db, user, p["ticker"], p["cantidad"])
        except (PosicionInsuficienteError, TickerInvalidoError):
            pass

    return RedirectResponse(url="/invertir", status_code=303)


@router.get("/metas", response_class=HTMLResponse)
def metas_form(request: Request, db: Session = Depends(get_db)):
    user = _requiere_perfil(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    metas = db.query(Goal).filter_by(user_id=user.id).order_by(Goal.fecha_objetivo).all()
    resumen = obtener_resumen_cartera(db, user)
    return templates.TemplateResponse(
        "metas.html", {"request": request, "user": user, "metas": metas, "resumen": resumen}
    )


@router.post("/metas")
def metas_crear(
    request: Request,
    nombre: str = Form(...),
    monto_objetivo: float = Form(...),
    fecha_objetivo: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _requiere_perfil(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    meta = Goal(
        user_id=user.id,
        nombre=nombre,
        monto_objetivo=monto_objetivo,
        fecha_objetivo=datetime.strptime(fecha_objetivo, "%Y-%m-%d"),
    )
    db.add(meta)
    db.commit()
    return RedirectResponse(url="/metas", status_code=303)
