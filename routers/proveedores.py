"""Endpoints de la página de proveedores."""

import asyncio

from fastapi import APIRouter

from core import proveedores_service
from core.python.services.audit_service import registrar_auditoria
from core.python.auth.deps import get_current_active_user
from core.python.schemas.auth_schemas import UserInDB
from fastapi import Depends, HTTPException
from core.python.db import get_pool

router = APIRouter(prefix='/api/proveedores', tags=['proveedores'])


@router.get('')
async def obtener_proveedores(
    current_user: UserInDB = Depends(get_current_active_user)
) -> dict:
    """Obtiene listado de proveedores con estadísticas."""
    await registrar_auditoria(
        user_id=current_user.id_usuario if hasattr(current_user, 'id_usuario') else 0,
        tipo_acceso='VIEW_PROVIDERS_LIST',
        tabla_afectada='TERCERO'
    )
    stats, proveedores = await asyncio.gather(
        proveedores_service.obtener_estadisticas(),
        proveedores_service.listar_proveedores(),
    )

    respuesta = {'stats': stats, 'providers': proveedores}
    return respuesta

@router.delete('/{nit}')
async def suprimir_proveedor(
    nit: str,
    current_user: UserInDB = Depends(get_current_active_user)
) -> dict:
    """Supresión de datos personales de un proveedor (pseudoanonimización).
    
    Conserva la razón social y NIT por retención fiscal (10 años),
    pero elimina datos de contacto directo.
    """
    await registrar_auditoria(
        user_id=current_user.id_usuario if hasattr(current_user, 'id_usuario') else 0,
        tipo_acceso='SUPRESION_DATOS',
        tabla_afectada='TERCERO',
        query_params={'nit': nit}
    )

    pool = get_pool()
    query = """
        UPDATE FACTURACION.TERCERO
        SET CORREO_CONTACTO = 'anon_deleted@quipux.com',
            TELEFONO_CONTACTO = '0000000'
        WHERE NUMERO_DOCUMENTO = %s
    """
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, [nit])
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Proveedor no encontrado")
                await conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"message": "Datos personales de contacto suprimidos exitosamente"}
