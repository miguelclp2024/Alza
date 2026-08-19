from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_or_create_user, reiniciar_sesion
from app.database import get_db
from app.models import RiskProfile
from app.scoring import calcular_perfil

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_TEXTO_HORIZONTE = {"corto": "menos de 2 años", "medio": "entre 2 y 7 años", "largo": "más de 7 años"}
_TEXTO_TOLERANCIA = {
    "conservador": "prefieres evitar pérdidas, aunque eso signifique ganar menos",
    "moderado": "toleras cierta variación sin entrar en pánico",
    "agresivo": "estás dispuesto a asumir más riesgo a cambio de más potencial de ganancia",
}
_TEXTO_OBJETIVO = {
    "preservacion": "preservar el capital que ya tienes",
    "ingresos": "generar ingresos recurrentes",
    "crecimiento": "hacer crecer tu capital a largo plazo",
    "jubilacion": "asegurar tu jubilación",
}
_TEXTO_MERCADO = {
    "peru": "prefieres el mercado peruano",
    "global": "prefieres el mercado internacional",
    "ambos": "te da igual el mercado, priorizas lo que mejor rinda",
}


def _construir_resumen_texto(respuestas: dict, perfil_resultado: str) -> str:
    return (
        f"Nos dices que piensas usar este dinero en {_TEXTO_HORIZONTE.get(respuestas['horizonte'], respuestas['horizonte'])}, "
        f"que {_TEXTO_TOLERANCIA.get(respuestas['tolerancia_riesgo'], '')}, que tu meta principal es "
        f"{_TEXTO_OBJETIVO.get(respuestas['objetivo'], respuestas['objetivo'])}, y que "
        f"{_TEXTO_MERCADO.get(respuestas['interes_geografico'], '')}. Con eso armamos un perfil "
        f"{perfil_resultado}."
    )


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request, db: Session = Depends(get_db)):
    user = get_or_create_user(request, db)
    if user.perfil and user.perfil.confirmado:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("bienvenida.html", {"request": request, "user": user})


@router.get("/comenzar", response_class=HTMLResponse)
def comenzar(request: Request, db: Session = Depends(get_db)):
    user = get_or_create_user(request, db)
    if user.perfil and user.perfil.confirmado:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("onboarding.html", {"request": request, "user": user})


@router.post("/onboarding", response_class=HTMLResponse)
def onboarding_submit(
    request: Request,
    nombre: str = Form(...),
    horizonte: str = Form(...),
    capacidad_inversion_soles: float = Form(...),
    tolerancia_riesgo: str = Form(...),
    interes_geografico: str = Form(...),
    objetivo: str = Form(...),
    rango_edad: str = Form(...),
    experiencia: str = Form(...),
    necesita_liquidez: str = Form("no"),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(request, db)
    user.nombre = nombre.strip()

    respuestas = {
        "horizonte": horizonte,
        "tolerancia_riesgo": tolerancia_riesgo,
        "objetivo": objetivo,
        "rango_edad": rango_edad,
        "experiencia": experiencia,
        "necesita_liquidez": necesita_liquidez == "si",
        "interes_geografico": interes_geografico,
    }
    calculo = calcular_perfil(respuestas)

    perfil = user.perfil or RiskProfile(user_id=user.id)
    perfil.horizonte = horizonte
    perfil.capacidad_inversion_soles = capacidad_inversion_soles
    perfil.tolerancia_riesgo = tolerancia_riesgo
    perfil.objetivo = objetivo
    perfil.rango_edad = rango_edad
    perfil.experiencia = experiencia
    perfil.necesita_liquidez = respuestas["necesita_liquidez"]
    perfil.interes_geografico = interes_geografico
    perfil.score = calculo["score"]
    perfil.perfil_resultado = calculo["perfil_resultado"]
    perfil.confirmado = False

    db.add(user)
    db.add(perfil)
    db.commit()
    db.refresh(perfil)

    resumen_texto = _construir_resumen_texto(respuestas, calculo["perfil_resultado"])
    return templates.TemplateResponse(
        "confirmar_perfil.html",
        {"request": request, "user": user, "nombre": user.nombre, "perfil": perfil, "resumen_texto": resumen_texto},
    )


@router.post("/onboarding/confirmar")
def onboarding_confirmar(request: Request, respuesta: str = Form(...), db: Session = Depends(get_db)):
    user = get_or_create_user(request, db)
    if not user.perfil:
        return RedirectResponse(url="/", status_code=303)

    if respuesta == "si":
        user.perfil.confirmado = True
        if user.saldo_disponible == 0:
            user.saldo_disponible = user.perfil.capacidad_inversion_soles
        db.add(user)
        db.commit()
        return RedirectResponse(url="/invertir", status_code=303)

    return RedirectResponse(url="/onboarding/detallado", status_code=303)


@router.get("/onboarding/detallado", response_class=HTMLResponse)
def onboarding_detallado_form(request: Request, db: Session = Depends(get_db)):
    user = get_or_create_user(request, db)
    if not user.perfil:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "onboarding_detallado.html", {"request": request, "user": user, "nombre": user.nombre}
    )


@router.post("/onboarding/detallado")
def onboarding_detallado_submit(
    request: Request,
    objetivo_especifico: str = Form(...),
    ahorro_mensual_adicional: float = Form(...),
    tiene_deudas: str = Form(...),
    escenario_extremo: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_or_create_user(request, db)
    perfil = user.perfil
    if not perfil:
        return RedirectResponse(url="/", status_code=303)

    respuestas = {
        "horizonte": perfil.horizonte,
        "tolerancia_riesgo": perfil.tolerancia_riesgo,
        "objetivo": perfil.objetivo,
        "rango_edad": perfil.rango_edad,
        "experiencia": perfil.experiencia,
        "necesita_liquidez": perfil.necesita_liquidez,
        "tiene_deudas": tiene_deudas == "si",
        "escenario_extremo": escenario_extremo,
    }
    calculo = calcular_perfil(respuestas)

    perfil.objetivo_especifico = objetivo_especifico
    perfil.ahorro_mensual_adicional = ahorro_mensual_adicional
    perfil.tiene_deudas = respuestas["tiene_deudas"]
    perfil.cuestionario_detallado = True
    perfil.score = calculo["score"]
    perfil.perfil_resultado = calculo["perfil_resultado"]
    perfil.confirmado = True

    if user.saldo_disponible == 0:
        user.saldo_disponible = perfil.capacidad_inversion_soles

    db.add(user)
    db.add(perfil)
    db.commit()

    return RedirectResponse(url="/invertir", status_code=303)


@router.get("/reiniciar")
def reiniciar(request: Request):
    reiniciar_sesion(request)
    return RedirectResponse(url="/", status_code=303)
