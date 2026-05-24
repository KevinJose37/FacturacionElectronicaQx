"""Endpoints de la página de facturas."""

import asyncio

from fastapi import APIRouter, Query, Depends, HTTPException, Response

from core import facturas_service
from core.python.services import control_service
from core.python.services.audit_service import registrar_auditoria
from core.python.auth.deps import get_current_active_user
from core.python.schemas.auth_schemas import UserInDB

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


@router.get('/descargar-xml')
async def descargar_xml_factura(
    s3_key: str = Query(..., description='Ruta del archivo XML en S3'),
) -> Response:
    """Descarga el XML original de una factura desde S3.

    Args:
        s3_key: Llave del objeto XML en el bucket S3.

    Returns:
        Respuesta con el contenido XML y headers para descarga.

    Raises:
        HTTPException: Si el archivo no se pudo obtener.
    """
    contenido = await control_service.obtener_xml_factura(s3_key)

    if not contenido:
        raise HTTPException(
            status_code=404,
            detail='No se pudo recuperar el archivo XML desde el almacenamiento',
        )

    filename = s3_key.split('/')[-1]

    headers = {
        'Content-Disposition': f'inline; filename="{filename}"',
        'Access-Control-Expose-Headers': 'Content-Disposition',
    }

    return Response(
        content=contenido,
        media_type='application/xml',
        headers=headers,
    )


@router.get('/{id_factura}/pdf')
async def descargar_pdf_factura(
    id_factura: int,
    current_user: UserInDB = Depends(get_current_active_user),
) -> Response:
    """Endpoint seguro para descargar el archivo PDF de una factura desde S3.

    Args:
        id_factura: ID único de la factura.

    Returns:
        Respuesta con el contenido del PDF y headers de descarga.

    Raises:
        HTTPException: Si el archivo no se pudo obtener o no existe.
    """
    pdf_data = await facturas_service.obtener_pdf_factura(id_factura)

    if not pdf_data:
        raise HTTPException(
            status_code=404,
            detail='No se pudo recuperar el archivo PDF de la factura desde el almacenamiento',
        )

    contenido, filename = pdf_data

    headers = {
        'Content-Disposition': f'inline; filename="{filename}"',
        'Access-Control-Expose-Headers': 'Content-Disposition',
    }

    return Response(
        content=contenido,
        media_type='application/pdf',
        headers=headers,
    )


@router.get('/{id_factura}/xml')
async def descargar_xml_factura_por_id(
    id_factura: int,
    current_user: UserInDB = Depends(get_current_active_user),
) -> Response:
    """Endpoint seguro para descargar el archivo XML de una factura desde S3 usando su ID.

    Args:
        id_factura: ID único de la factura.

    Returns:
        Respuesta con el contenido del XML y headers de descarga.

    Raises:
        HTTPException: Si el archivo no se pudo obtener o no existe.
    """
    xml_data = await facturas_service.obtener_xml_factura_by_id(id_factura)

    if not xml_data:
        raise HTTPException(
            status_code=404,
            detail='No se pudo recuperar el archivo XML de la factura desde el almacenamiento',
        )

    contenido, filename = xml_data

    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Access-Control-Expose-Headers': 'Content-Disposition',
    }

    return Response(
        content=contenido,
        media_type='application/xml',
        headers=headers,
    )


from pydantic import BaseModel

class DecisionVerificacionGrafica(BaseModel):
    aprobado: bool


@router.post('/{id_factura}/verificacion-grafica')
async def decidir_verificacion_grafica(
    id_factura: int,
    decision: DecisionVerificacionGrafica,
    current_user: UserInDB = Depends(get_current_active_user),
) -> dict:
    """Registra la aprobación o rechazo manual de la validación gráfica."""
    await registrar_auditoria(
        user_id=current_user.id_usuario if hasattr(current_user, 'id_usuario') else 0,
        tipo_acceso='MANUAL_GRAPHIC_DECISION',
        tabla_afectada='FACTURA',
        query_params={'id_factura': id_factura, 'aprobado': decision.aprobado}
    )
    exito = await facturas_service.actualizar_verificacion_grafica(
        id_factura=id_factura,
        aprobado=decision.aprobado
    )
    if not exito:
        raise HTTPException(
            status_code=404,
            detail='No se encontró la factura especificada o no se pudo actualizar',
        )
    return {'status': 'success', 'message': 'Decisión manual registrada exitosamente'}


