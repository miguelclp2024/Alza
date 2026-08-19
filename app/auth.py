"""Identidad de sesion SIN registro/login: cada visitante recibe
automaticamente un perfil anonimo ligado a una cookie de sesion firmada.
Si borra las cookies o cambia de navegador, empieza un perfil nuevo (es una
limitacion aceptada a cambio de que consultar la plataforma sea inmediato).
"""

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import User


def get_or_create_user(request: Request, db: Session) -> User:
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if user:
        return user

    user = User(nombre="")
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return user


def reiniciar_sesion(request: Request) -> None:
    request.session.clear()
