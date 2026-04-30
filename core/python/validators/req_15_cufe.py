"""Módulo que contiene funciones de validación del CUFE de la factura electrónica."""

# Standard library imports
import hashlib

# Third-party imports
from lxml import etree

# Local application imports
from core.python.utils.validacion import construir_cadena_base_cufe
from core.python.utils.validacion import extraer_texto_xpath


def validar_cufe_v1(xml_factura: etree._Element) -> bool:
    """Valida el CUFE de la factura electrónica según la resolución 000165 de 2023.

    Verifica:
    - presencia del UUID
    - coherencia del algoritmo informado
    - consistencia del ambiente
    - reconstrucción del CUFE mediante SHA-384
    - coincidencia con el valor informado en cbc:UUID

    Args:
        xml_factura: Elemento raíz del XML de la factura (Invoice).

    Returns:
        True si el CUFE es válido, False en caso contrario.
    """
    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    }

    resultado_validacion = False
    mensaje = ''

    cufe_informado = extraer_texto_xpath(xml_factura, './cbc:UUID', NAMESPACES)
    esquema_cufe = xml_factura.xpath(
        'string(./cbc:UUID/@schemeName)', namespaces=NAMESPACES
    ).strip()
    ambiente_uuid = xml_factura.xpath(
        'string(./cbc:UUID/@schemeID)', namespaces=NAMESPACES
    ).strip()
    ambiente_xml = extraer_texto_xpath(
        xml_factura, './cbc:ProfileExecutionID', NAMESPACES
    )

    if not cufe_informado:
        mensaje = 'No se encontró el CUFE en el nodo cbc:UUID.'
    elif not esquema_cufe:
        mensaje = 'No se encontró el atributo schemeName del CUFE (cbc:UUID/@schemeName).'
    elif 'CUFE' not in esquema_cufe.upper() or '384' not in esquema_cufe.upper():
        mensaje = (
            'El atributo schemeName del CUFE no corresponde al algoritmo esperado. '
            f'Valor informado: {esquema_cufe}.'
        )
    elif not ambiente_uuid or not ambiente_xml:
        mensaje = (
            'No fue posible validar el ambiente del documento porque faltan '
            'cbc:UUID/@schemeID o cbc:ProfileExecutionID.'
        )
    elif ambiente_uuid != ambiente_xml:
        mensaje = (
            'Existe inconsistencia entre el ambiente informado en cbc:UUID/@schemeID '
            f'({ambiente_uuid}) y cbc:ProfileExecutionID ({ambiente_xml}).'
        )
    else:
        cadena_base, _ = construir_cadena_base_cufe(xml_factura, NAMESPACES)

        if not cadena_base:
            mensaje = (
                'No fue posible reconstruir la cadena base del CUFE porque faltan '
                'uno o más campos obligatorios de la factura.'
            )
        else:
            cufe_calculado = hashlib.sha384(cadena_base.encode('utf-8')).hexdigest()
            cufe_informado_normalizado = cufe_informado.strip().lower()

            if cufe_calculado != cufe_informado_normalizado:
                mensaje = (
                    'El CUFE informado no coincide con el CUFE recalculado. '
                    f'Informado: {cufe_informado_normalizado}. '
                    f'Calculado: {cufe_calculado}.'
                )
            else:
                resultado_validacion = True
                mensaje = (
                    'El CUFE es válido. '
                    'Se verificó la presencia del UUID, la coherencia del algoritmo, '
                    'el ambiente y la coincidencia entre el CUFE informado y el '
                    'CUFE recalculado con SHA-384.'
                )

    enviar_log_validacion(mensaje)

    return resultado_validacion
