"""Endpoints de la página de control de facturas."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from core.python.services import control_service

router = APIRouter(prefix='/api/control', tags=['control'])


class ControlUpdateBody(BaseModel):
    """Cuerpo de la petición para actualizar un registro de control."""

    fecha_entrega_contabilidad: str | None = None
    nombre_recibe_contabilidad: str | None = None
    forma_pago: str | None = None
    acuso_recibido: bool = False
    recibido_bien_servicio: bool = False
    aceptacion_empresa: bool = False
    observaciones_entrega: str | None = None
    eventos_dian_notif: str | None = None


@router.get('')
async def obtener_control(
    fecha_inicio: date = Query(None),
    fecha_fin: date = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    """Obtiene registros de control de facturas con paginación y filtros.

    Args:
        fecha_inicio: Filtro opcional de fecha inicial.
        fecha_fin: Filtro opcional de fecha final.
        page: Número de página (1-indexed).
        size: Cantidad de registros por página.

    Returns:
        Diccionario con items y metadata de paginación.
    """
    resultado = await control_service.listar_control(
        fecha_inicio, fecha_fin, page, size,
    )
    return resultado


@router.patch('/{id_control}')
async def actualizar_control(
    id_control: int,
    body: ControlUpdateBody,
) -> dict:
    """Actualiza los campos editables de un registro de control.

    Args:
        id_control: ID del registro de control a actualizar.
        body: Campos editables con sus nuevos valores.

    Returns:
        Diccionario con el estado de la operación.

    Raises:
        HTTPException: Si el registro no se encontró.
    """
    actualizado = await control_service.actualizar_control(
        id_control, body.model_dump(),
    )

    if not actualizado:
        raise HTTPException(status_code=404, detail='Registro de control no encontrado')

    resultado = {'ok': True, 'message': 'Registro actualizado correctamente'}
    return resultado


@router.get('/descargar-paquete')
async def descargar_paquete_factura(
    id_factura: int = Query(..., description='ID de la factura'),
) -> Response:
    """Endpoint para descargar el paquete ZIP de una factura.

    Si existe el ZIP original en S3 lo descarga. De lo contrario,
    genera un ZIP con el XML y el PDF.

    Args:
        id_factura: Identificador único de la factura.

    Returns:
        Respuesta con el contenido del ZIP y headers de descarga.

    Raises:
        HTTPException: Si los archivos no se pudieron obtener.
    """
    resultado = await control_service.obtener_paquete_factura(id_factura)

    if not resultado:
        raise HTTPException(
            status_code=404,
            detail='No se pudieron recuperar los archivos de la factura',
        )

    contenido, filename = resultado

    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Access-Control-Expose-Headers': 'Content-Disposition',
    }

    return Response(
        content=contenido,
        media_type='application/zip',
        headers=headers,
    )


@router.get('/descargar-xml')
async def descargar_xml_factura(
    s3_key: str = Query(..., description='Ruta del archivo en S3'),
) -> Response:
    """Endpoint para descargar el XML de una factura desde S3.

    Args:
        s3_key: Llave del objeto en el bucket S3.

    Returns:
        Respuesta con el contenido del XML y headers de descarga.

    Raises:
        HTTPException: Si el archivo no se pudo obtener.
    """
    contenido = await control_service.obtener_xml_factura(s3_key)

    if not contenido:
        raise HTTPException(
            status_code=404,
            detail='No se pudo recuperar el archivo XML desde el almacenamiento',
        )

    # Extraer nombre de archivo de la ruta
    filename = s3_key.split('/')[-1]

    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Access-Control-Expose-Headers': 'Content-Disposition',
    }

    return Response(
        content=contenido,
        media_type='application/xml',
        headers=headers,
    )
