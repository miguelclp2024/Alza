from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY
from app.database import Base, engine
from app.routers import dashboard_routes, onboarding_routes
from app.scheduler import iniciar_actualizacion_periodica

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Alza")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(onboarding_routes.router)
app.include_router(dashboard_routes.router)


@app.on_event("startup")
def _arrancar_actualizacion_de_mercado():
    iniciar_actualizacion_periodica()


@app.exception_handler(404)
async def pagina_no_encontrada(request: Request, exc):
    return templates.TemplateResponse("error_404.html", {"request": request}, status_code=404)


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots():
    return "User-agent: *\nAllow: /\n"
