# Alza

Plataforma web **demostrativa** de orientacion financiera: sin registro ni
contrasenas, el visitante responde un cuestionario de perfil de riesgo,
confirma que el resumen lo describe bien (o profundiza con un cuestionario
detallado si no), y recibe alternativas concretas de inversion en acciones y
ETFs reales segun su perfil y su capital (datos de mercado en vivo via Yahoo
Finance, refrescados cada minuto en segundo plano). Puede "depositar" saldo
virtual, aplicar una alternativa completa o comprar/vender activos puntuales
a precio real simulado, y hacer seguimiento en un dashboard con grafico de
evolucion, historial de operaciones y metas financieras.

**Importante: todo el dinero es simulado.** No se procesan pagos reales, no se
ejecutan ordenes en ningun broker, y no se maneja custodia de fondos de
terceros. Operar una plataforma que SI reciba e invierta dinero real de
terceros requiere licencias regulatorias (en Peru, ante la SMV/SBS) que este
proyecto no tiene ni pretende tener. Es un proyecto educativo/portafolio.

## Identidad sin registro

Cada visitante recibe automaticamente una cookie de sesion firmada al entrar
(`app/auth.py`, `get_or_create_user`) y con eso ya puede usar la plataforma
de punta a punta, sin crear cuenta. La limitacion: si borra las cookies o
cambia de navegador/dispositivo, empieza un perfil nuevo. Es la contrapartida
aceptada a cambio de que consultar la plataforma sea inmediato.

## Arquitectura

- **Backend:** FastAPI + SQLAlchemy (SQLite en local, Postgres en produccion).
- **Frontend:** Jinja2 + Tailwind (via CDN) + Chart.js, sin build step.
- **Datos de mercado:** `yfinance` (Yahoo Finance). `app/scheduler.py` corre un
  hilo de fondo que refresca el cache de todo el universo curado cada 60s
  (`app/market_data.py: refrescar_universo`), asi las paginas casi nunca
  esperan a Yahoo Finance.
- **Sesiones:** cookies firmadas (`itsdangerous` / `SessionMiddleware`).

Estructura:
```
app/
  main.py              # arranque de FastAPI, monta routers y estaticos
  config.py            # variables de entorno / parametros
  database.py          # engine y sesion de SQLAlchemy
  models.py            # User, RiskProfile, Position, Transaction, Goal, PortfolioSnapshot
  auth.py              # sesion anonima (sin password)
  scheduler.py           # hilo de refresco de mercado cada 60s
  market_data.py           # precios e indicadores reales (Yahoo Finance)
  universe.py                # universo curado de acciones/ETFs
  scoring.py                   # cuestionario -> perfil -> alternativas de cartera
  portfolio_engine.py            # depositar/comprar/vender (simulado) + calculo de P&L
  routers/
    onboarding_routes.py          # cuestionario, confirmacion, cuestionario detallado
    dashboard_routes.py             # dashboard, invertir, metas
  templates/             # paginas Jinja2
  static/                # css/js/fonts/img
```

## Correr en local

```powershell
cd cumbre-capital
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # y edita SECRET_KEY si quieres
uvicorn app.main:app --reload --port 8000
```

Abre http://127.0.0.1:8000

## Nota tecnica: IPv6

En algunas redes las conexiones a Yahoo Finance por IPv6 se cuelgan en vez de
fallar. `app/market_data.py` fuerza resolucion DNS solo IPv4 al importar el
modulo (`socket.getaddrinfo` parcheado). Si despliegas en un proveedor donde
esto no aplique, es inofensivo dejarlo.

## Desplegar en internet (Render o Railway)

Ambos servicios corren un unico proceso Python sin que necesites separar
frontend/backend (a diferencia de Vercel, que esta pensado para Next.js /
serverless y no es ideal para esta app con SQLite/Postgres + un proceso largo).

1. Sube el proyecto a un repositorio de GitHub (crea el repo, `git init`,
   `git add .`, `git commit`, `git push`).
2. En Render/Railway: "New Web Service" -> conecta el repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Agrega una base de datos Postgres (ambos la ofrecen gratis/barata) y copia
   su `DATABASE_URL` a las variables de entorno del servicio. SQLAlchemy la
   usara automaticamente (ver `app/config.py`).
4. Define tambien `SECRET_KEY` (genera una con
   `python -c "import secrets; print(secrets.token_hex(32))"`).
5. Una vez desplegado te daran una URL tipo `algo.onrender.com` o
   `algo.up.railway.app`. Pruebala antes de conectar el dominio.

### Conectar tu dominio propio

En el panel de tu proveedor de dominio (donde lo compraste), agrega un
registro DNS apuntando a la URL que te dio Render/Railway:
- Si tu dominio es `midominio.com` -> registro **CNAME** en `www` apuntando a
  la URL del servicio (o **ALIAS/ANAME** en el dominio raiz si tu proveedor lo
  soporta).
- Luego, en el panel de Render/Railway, en "Custom Domain", agrega
  `midominio.com` y sigue las instrucciones de verificacion (suelen pedir un
  registro TXT adicional). El certificado HTTPS se genera automaticamente.

Puede tardar unos minutos a un par de horas en propagarse.

## Personalizar diseño

- **Logo:** coloca el archivo (idealmente `.svg`) en `app/static/img/` y
  referencialo en `app/templates/base.html` (reemplaza el triangulo
  placeholder en el `<nav>`).
- **Fuentes propias:** coloca los `.woff2` en `app/static/fonts/` y agrega
  reglas `@font-face` en `app/static/css/styles.css`, actualizando
  `fontFamily` en el `tailwind.config` de `base.html`.

## Limitaciones conocidas / para mejorar

- El motor de recomendacion (`scoring.py`) es un modelo simplificado con
  fines demostrativos, no un modelo de asesoria financiera profesional.
- El tipo de cambio USD/PEN es un valor fijo de referencia
  (`TIPO_CAMBIO_USD_PEN` en `.env`), no una tasa en vivo.
- Sin registro no hay forma de recuperar tu perfil desde otro dispositivo.
