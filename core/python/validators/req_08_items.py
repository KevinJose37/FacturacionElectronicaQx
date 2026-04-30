"""Módulo que contiene funciones de validación de los ítems de la factura electrónica."""

# Third-party imports
from lxml import etree


def validar_lineas_factura_v1(xml_invoice: etree._Element | None) -> bool:
    """Valida las líneas de la factura electrónica (InvoiceLine) según la resolución
     000165 de 2023.
     
    Args:
        xml_invoice: Árbol XML de la factura electrónica a validar.
        
    Reglas:
    - Debe existir al menos una línea (cac:InvoiceLine)
    - Cada línea debe tener ID (cbc:ID)
    - Cada línea debe tener cantidad (cbc:InvoicedQuantity) > 0
    - Cada línea debe tener valor (cbc:LineExtensionAmount) > 0
    - Cada línea debe tener descripción (cac:Item/cbc:Description) no vacía
    - Cada línea debe tener código de identificación del ítem
      (cac:Item/cac:StandardItemIdentification/cbc:ID)
    
    Retorna:
        True si las líneas cumplen con las validaciones, False en caso contrario.
    
    """

    NAMESPACES = {
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
    }

    errores = []

    if xml_invoice is None:
        errores.append('No se encontró el XML Invoice para validar las líneas.')

    else:
        lineas = xml_invoice.xpath('./cac:InvoiceLine', namespaces=NAMESPACES)

        if not lineas:
            errores.append('La factura no contiene líneas (cac:InvoiceLine).')

        else:
            for idx, linea in enumerate(lineas, start=1):
                id_linea = linea.xpath('./cbc:ID', namespaces=NAMESPACES)
                cantidad = linea.xpath('./cbc:InvoicedQuantity', namespaces=NAMESPACES)
                valor = linea.xpath('./cbc:LineExtensionAmount', namespaces=NAMESPACES)
                descripcion = linea.xpath(
                    './cac:Item/cbc:Description', namespaces=NAMESPACES
                )
                codigo_item = linea.xpath(
                    './cac:Item/cac:StandardItemIdentification/cbc:ID',
                    namespaces=NAMESPACES
                )

                id_val = (id_linea[0].text or '').strip() if id_linea else ''
                cantidad_val = (cantidad[0].text or '').strip() if cantidad else ''
                unidad_medida = cantidad[0].get('unitCode') if cantidad else None
                valor_val = (valor[0].text or '').strip() if valor else ''
                descripcion_val = (
                    (descripcion[0].text or '').strip() if descripcion else ''
                )
                codigo_val = (codigo_item[0].text or '').strip() if codigo_item else ''

                if not id_val:
                    errores.append(f'Línea {idx}: no tiene ID.')

                if not unidad_medida:
                    errores.append(f'Línea {idx}: no tiene unidad de medida (unitCode).')

                try:
                    if float(cantidad_val) <= 0:
                        errores.append(
                            f'Línea {idx}: cantidad inválida ({cantidad_val}).'
                        )
                        
                except Exception:
                    errores.append(f'Línea {idx}: cantidad no numérica ({cantidad_val}).')

                try:
                    if float(valor_val) <= 0:
                        errores.append(f'Línea {idx}: valor inválido ({valor_val}).')

                except Exception:
                    errores.append(f'Línea {idx}: valor no numérico ({valor_val}).')

                if not descripcion_val:
                    errores.append(f'Línea {idx}: descripción vacía.')

                if not codigo_val:
                    errores.append(
                        f'Línea {idx}: no tiene código de identificación del ítem.'
                    )

    if errores:
        mensaje = 'Errores en validación de líneas:\n' + '\n'.join(errores)
        enviar_log_validacion(mensaje)
        resultado_validacion = False

    else:
        mensaje = 'Las líneas de la factura cumplen el requisito 8.'
        enviar_log_validacion(mensaje)
        resultado_validacion = True
    
    return resultado_validacion
