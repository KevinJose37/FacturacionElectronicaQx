"""Punto de entrada principal para la API de Facturación Electrónica."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

# Fix para Windows: psycopg async requiere SelectorEventLoop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from core import close_pool, init_pool
from routers import (
    chat,
    control,
    dashboard,
    facturas,
    ingesta,
    logs_router,
    proveedores,
    rechazos,
    validaciones,
    exports,
    auth,
    usuarios,
)

# Configuración de logging base
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    await init_pool()
    logger.info('API iniciada — pool de conexiones listo.')
    yield
    await close_pool()
    logger.info('API detenida — pool de conexiones cerrado.')


app = FastAPI(
    title="Facturacion Electronica API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — permite que el frontend en otro origen consuma la API
cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Orquestación de Rutas ---
# Los routers individuales ya incluyen el prefijo /api
api_router = APIRouter()

# Registramos el webhook directamente en la app para que la ruta sea /webhook/gmail y no /api/webhook/gmail
app.include_router(ingesta.router)

api_router.include_router(control.router)
api_router.include_router(dashboard.router)
api_router.include_router(facturas.router)
api_router.include_router(proveedores.router)
api_router.include_router(validaciones.router)
api_router.include_router(rechazos.router)
api_router.include_router(logs_router.router)
api_router.include_router(chat.router)
api_router.include_router(exports.router)
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)

app.include_router(api_router)


@app.get("/")
async def root():
    """Endpoint de salud del servicio."""
    return {"status": "online"}

if __name__ == "__main__":
    if sys.platform == 'win32':
        # Forzar SelectorEventLoop antes de que uvicorn cree su loop
        import selectors
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.set_event_loop(loop)
    uvicorn.run("main:app", host="0.0.0.0", port=8888, reload=False)