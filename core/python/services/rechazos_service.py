"""Servicio de consultas para la página de rechazos."""

import logging
from datetime import datetime, timezone

from config import load_yaml_queries
from core.python.db import get_pool
from metadata.common_metadata import DefaultTextos

logger = logging.getLogger(__name__)

_QUERIES = load_yaml_queries('services/queries_services.yml').get('rechazos', {})

MAPEO_RECHAZOS = {
    'MALWARE_DETECTADO': ('Malware Detectado', 'Se detectó código malicioso en el archivo adjunto. Por seguridad, el procesamiento fue bloqueado.'),
    'EXTENSION_PROHIBIDA': ('Extensión Prohibida', 'El archivo tiene una extensión potencialmente peligrosa (.exe, .bat, etc.) no permitida.'),
    'TAMANO_EXCEDIDO': ('Tamaño Excedido', 'El archivo supera el peso máximo permitido para el procesamiento de facturas.'),
    'ZIP_CORRUPTO': ('Archivo ZIP Corrupto', 'El contenedor ZIP se encuentra dañado y no se pudo descomprimir.'),
    'ZIP_SIN_XML': ('Contenedor sin XML', 'El archivo ZIP no contiene el archivo XML de la factura electrónica.'),
    'ZIP_PROFUNDIDAD_EXCEDIDA': ('ZIP Anidado Excedido', 'La estructura de archivos ZIP anidados supera el límite máximo permitido.'),
    'ZIP_SUBZIP_INVALIDO': ('Sub-ZIP Inválido', 'Un sub-ZIP dentro del contenedor principal no tiene el formato o contenido esperado.'),
    'FALLO_DESCARGA_ADJUNTOS': ('Fallo de Descarga', 'No se pudieron descargar los archivos adjuntos del correo de origen.'),
    'FALLO_SUBIDA_S3': ('Fallo en Almacenamiento S3', 'Ocurrió un error al subir el archivo al almacenamiento en la nube S3.'),
    'FALLO_REGISTRO_BD': ('Fallo de Registro en Base de Datos', 'No se pudo guardar la información del adjunto en el sistema.'),
    'XML_EMBEBIDO_NO_ENCONTRADO': ('XML Embebido no Encontrado', 'No se encontró el XML de Invoice o ApplicationResponse requerido dentro del documento.'),
    'XML_EMBEBIDO_PARSE_ERROR': ('Error en XML Embebido', 'No se pudo leer la estructura del XML AttachedDocument para extraer los archivos internos.'),
    'PDF_FALTANTE': ('Falta Representación Gráfica PDF', 'No se encontró la versión en PDF que debe acompañar al XML de la factura.'),
    'PDF_SIN_XML': ('PDF sin XML Asociado', 'Se cargó un archivo PDF pero no se encontró el XML de la factura correspondiente.'),
    'CORREO_SIN_ADJUNTOS_VALIDOS': ('Correo sin Adjuntos Válidos', 'El correo de facturación no contiene ningún archivo adjunto con formato admitido.'),
    'CORREO_RECHAZADO_FILTRO': ('Correo Rechazado', 'El correo recibido no cumple con las reglas de filtrado de facturación.'),
    'ERROR_PROCESAMIENTO_GENERAL': ('Error General de Procesamiento', 'Ocurrió un error inesperado al procesar la factura electrónica.'),
    'ADJUNTO_DUPLICADO': ('Factura Duplicada', 'Esta factura o archivo adjunto ya fue procesado y registrado previamente.'),
    'CUFE_NO_ENCONTRADO': ('CUFE no Encontrado', 'No se localizó el Código Único de Factura Electrónica (CUFE) en el XML.'),
    'CUFE_INVALIDO': ('CUFE Inválido', 'El CUFE del XML es incorrecto o no coincide al ser recalculado por el sistema.'),
    'XML_PARSE_ERROR': ('Error de Lectura XML', 'El archivo XML presenta errores de sintaxis y no pudo ser leído.'),
    'FECHA_VALIDACION_INVALIDA': ('Fecha de Validación Inválida', 'La fecha de validación emitida por la DIAN no tiene un formato válido.'),
    'VALIDACION_DIAN_FALLO': ('Rechazado por la DIAN', 'El documento no superó las validaciones oficiales de la DIAN.'),
    'VALOR_TOTAL_INCONSISTENTE': ('Inconsistencia en Totales', 'El valor total de la factura no coincide con la suma de las líneas de detalle.'),
    'FORMA_PAGO_INVALIDA': ('Forma de Pago Inválida', 'La forma de pago indicada en la factura no es válida o está ausente.'),
    'MEDIO_PAGO_INVALIDO': ('Medio de Pago Inválido', 'El medio de pago ingresado no es válido (obligatorio para ventas de contado).'),
    'CALIDAD_TRIBUTARIA_FALTANTE': ('Falta Calidad Tributaria', 'No se especificó la calidad tributaria o responsabilidades del emisor.'),
    'IMPUESTOS_INVALIDOS': ('Inconsistencia de Impuestos', 'Los impuestos reportados tienen datos faltantes o cálculos inconsistentes.'),
    'FIRMA_DIGITAL_INVALIDA': ('Firma Digital Inválida', 'La firma digital de la factura no superó la verificación de seguridad.'),
    'QR_INVALIDO': ('Código QR Inválido', 'El código QR del documento no es válido o es inconsistente.'),
    'ANEXO_TECNICO_INVALIDO': ('Incompatibilidad UBL', 'El formato XML no cumple con el Anexo Técnico de la DIAN (estándar UBL).'),
    'SOFTWARE_PROVEEDOR_FALTANTE': ('Falta Proveedor Tecnológico', 'No se encuentra reportado el fabricante del software de facturación.'),
    'ERROR_REGISTRO_FACTURA': ('Error al Registrar Factura', 'No se pudo almacenar la factura en la base de datos de facturación.'),
    'MAX_REINTENTOS_EXCEDIDO': ('Reintentos Máximos Superados', 'Se excedió el número máximo de reintentos automáticos para procesar la factura.'),
    'EMISOR_SIN_NOMBRE': ('Falta Nombre del Emisor', 'El emisor no incluye nombre o razón social en el documento.'),
    'EMISOR_SIN_DOCUMENTO': ('Falta NIT del Emisor', 'El emisor no cuenta con NIT o número de documento de identificación.'),
    'EMISOR_DOCUMENTO_INVALIDO': ('NIT del Emisor Inválido', 'El formato del número de documento o NIT del emisor es incorrecto.'),
    'EMISOR_DV_INVALIDO': ('Dígito de Verificación de Emisor Erróneo', 'El dígito de verificación (DV) del NIT del emisor es incorrecto.'),
    'ADQUIRIENTE_SIN_NOMBRE': ('Falta Nombre del Adquiriente', 'El receptor/adquiriente no incluye nombre o razón social.'),
    'ADQUIRIENTE_SIN_DOCUMENTO': ('Falta NIT del Adquiriente', 'El adquiriente no cuenta con NIT o documento de identificación.'),
    'ADQUIRIENTE_DOCUMENTO_INVALIDO': ('NIT del Adquiriente Inválido', 'El formato del número de documento o NIT del adquiriente es incorrecto.'),
    'ADQUIRIENTE_DV_INVALIDO': ('Dígito de Verificación de Adquiriente Erróneo', 'El dígito de verificación (DV) del NIT del adquiriente es incorrecto.'),
    'NUMERACION_SIN_RANGO_AUTORIZADO': ('Falta Rango Autorizado', 'La factura no especifica el rango de numeración ni resolución de la DIAN.'),
    'NUMERACION_FUERA_DE_RANGO': ('Factura Fuera de Rango', 'El consecutivo de la factura está fuera del rango autorizado por la DIAN.'),
    'NUMERACION_VENCIDA': ('Resolución DIAN Vencida', 'La autorización o resolución de numeración de la DIAN se encuentra vencida.'),
    'FECHA_GENERACION_FUTURA': ('Fecha de Expedición Futura', 'La fecha de generación de la factura es posterior al día de hoy.'),
    'FECHA_GENERACION_FORMATO_INVALIDO': ('Error en Fecha de Expedición', 'El formato de la fecha de generación es inválido o no se pudo extraer.'),
    'LINEA_SIN_DESCRIPCION': ('Falta Descripción de Ítem', 'Una o más líneas de detalle de la factura no incluyen descripción del ítem.'),
    'LINEA_VALOR_INVALIDO': ('Valor de Ítem Inválido', 'Hay inconsistencias o valores nulos en los precios y totales de las líneas.'),
    'LINEA_CANTIDAD_INVALIDA': ('Cantidad de Ítem Inválida', 'Una o más líneas tienen cantidades reportadas iguales o menores a cero.'),
    'DENOMINACION_INCORRECTA': ('Denominación Incorrecta', 'La denominación del documento no corresponde expresamente a "Factura Electrónica de Venta" según la resolución.'),
    'TIPO_DOCUMENTO_DIAN_INVALIDO': ('Tipo de Documento DIAN Inválido', 'El código de tipo de documento (InvoiceTypeCode) no corresponde a una factura electrónica admitida.'),
    'PROFILE_ID_NO_ENCONTRADO': ('Nodo ProfileID no Encontrado', 'No se localizó el nodo cbc:ProfileID en el XML, requerido para validar su denominación.'),
}


async def listar_rechazos() -> list:
    """Lista facturas rechazadas con detalles del error.

    Returns:
        Lista de rechazos con proveedor, motivo, regla y severidad.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['listar'])
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        # r[5]=id_estado_proceso: 5=FALLIDO → high, 4=ERROR → medium
        severidad = 'high' if r[5] == 5 else 'medium'
        codigo = r[3]
        if codigo in MAPEO_RECHAZOS:
            titulo, desc = MAPEO_RECHAZOS[codigo]
        else:
            titulo = codigo or DefaultTextos.error_generico_regla
            desc = r[2] or DefaultTextos.error_no_especificado

        resultado.append({
            'id': r[0],
            'db_id': r[6],
            'provider': r[1] or DefaultTextos.sin_nombre,
            'reason': desc,
            'rule': titulo,
            'date': r[4].strftime(DefaultTextos.formato_fecha_corto) if r[4] else '',
            'severity': severidad,
        })
    return resultado


async def obtener_estadisticas() -> dict:
    """Calcula estadísticas de rechazos.

    Returns:
        Diccionario con rechazos_hoy, severidad_alta, reintentos, tasa_rechazo.
    """
    pool = get_pool()
    ahora = datetime.now(tz=timezone.utc)
    inicio_hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['estadisticas'], (inicio_hoy,))
            row = await cur.fetchone()
            rechazos_hoy, severidad_alta, total = row[0], row[1], row[2]

            await cur.execute(_QUERIES['reintentos'])
            reintentos = (await cur.fetchone())[0]

    tasa = round((rechazos_hoy / max(total, 1)) * 100, 1)
    estadisticas = {
        'rechazos_hoy': rechazos_hoy,
        'severidad_alta': severidad_alta,
        'reintentos': reintentos,
        'tasa_rechazo': tasa,
    }
    return estadisticas


async def obtener_causas_frecuentes() -> list:
    """Agrupa rechazos por código de respuesta.

    Returns:
        Lista de causas con código y conteo.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['causas_frecuentes'])
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        codigo = r[0]
        if codigo in MAPEO_RECHAZOS:
            titulo, _ = MAPEO_RECHAZOS[codigo]
        else:
            titulo = codigo or DefaultTextos.error_generico_regla
        resultado.append({'rule': titulo, 'count': r[1]})
    return resultado
