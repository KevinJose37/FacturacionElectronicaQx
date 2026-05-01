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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from core import close_pool, init_pool
from routers import (
    chat,
    dashboard,
    facturas,
    ingesta,
    logs_router,
    proveedores,
    rechazos,
    validaciones,
)

# Configuración de logging base
logging.basicConfig(
    level=logging.INFO,
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

# Routers
app.include_router(ingesta.router)
app.include_router(dashboard.router)
app.include_router(facturas.router)
app.include_router(proveedores.router)
app.include_router(validaciones.router)
app.include_router(rechazos.router)
app.include_router(logs_router.router)
app.include_router(chat.router)


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
    uvicorn.run(app, host="127.0.0.1", port=8000, loop="asyncio")
