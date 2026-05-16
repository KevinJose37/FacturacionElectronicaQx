"""Endpoints de la página de facturas."""

import asyncio

from fastapi import APIRouter, Query

from core import facturas_service
from core.python.services.audit_service import registrar_auditoria
from core.python.auth.deps import get_current_active_user
from core.python.schemas.auth_schemas import UserInDB
from fastapi import Depends

router = APIRouter(prefix='/api/facturas', tags=['facturas'])


@router.get('')
async def obtener_facturas(
    estado: str | None = Query(None, description='Filtro por estado'),
    busqueda: str | None = Query(None, description='Búsqueda por texto'),
    pagina: int = Query(1, ge=1, description='Número de página'),
    por_pagina: int = Query(30, ge=1, le=100, description='Registros por página'),
    current_user: UserInDB = Depends(get_current_active_user),
) -> dict:
    """Obtiene listado de facturas con estadísticas."""
    
    await registrar_auditoria(
        user_id=current_user.id_usuario if hasattr(current_user, 'id_usuario') else 0,
        tipo_acceso='VIEW_INVOICE_LIST',
        tabla_afectada='FACTURA',
        query_params={'estado': estado, 'busqueda': busqueda, 'pagina': pagina}
    )
    stats, facturas = await asyncio.gather(
        facturas_service.obtener_estadisticas(),
        facturas_service.listar_facturas(estado, busqueda, pagina, por_pagina),
    )

    respuesta = {'stats': stats, 'invoices': facturas}
    return respuesta
