from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY
from app.database import Base, engine
from app.routers import dashboard_routes, onboarding_routes
from app.scheduler import iniciar_actualizacion_periodica

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Alza")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(onboarding_routes.router)
app.include_router(dashboard_routes.router)


@app.on_event("startup")
def _arrancar_actualizacion_de_mercado():
    iniciar_actualizacion_periodica()
