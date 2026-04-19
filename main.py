"""Punto de entrada principal para la API de Facturación Electrónica."""

import logging
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

from routers import ingesta

# Configuración de logging base
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("api")

app = FastAPI(
    title="Facturacion Electronica API",
    version="1.0.0"
)

app.include_router(ingesta.router)

@app.get("/")
async def root():
    """Endpoint de salud del servicio."""
    return {"status": "online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
