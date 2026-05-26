"""Módulo que contiene funciones de validación de los ítems de la factura electrónica."""

# Standard library imports
import logging

# Third-party imports
from lxml import etree

# Local application imports
from metadata.db_metadata import IdTipoError

logger = logging.getLogger(__name__)


def validar_lineas_factura_v1(xml_invoice: etree._Element | None) -> dict:
    """Valida las líneas de la factura electrónica (InvoiceLine) según la resolución
     000165 de 2023.
     
    Args:
        xml_invoice: Árbol XML de la factura electrónica a validar.
        
    Returns:
        Diccionario con:
        - 'valido': bool indicando si las líneas cumplen.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con líneas extraídas y conteo.
    """

    NAMESPACES = {
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
    }

    errores = []
    lineas_extraidas = []
    id_error = None

    if xml_invoice is None:
        errores.append('No se encontró el XML Invoice para validar las líneas.')

    else:
        # Extraer LineCountNumeric
        nodo_count = xml_invoice.xpath('./cbc:LineCountNumeric', namespaces=NAMESPACES)
        conteo_informado = (
            int(nodo_count[0].text.strip())
            if nodo_count and nodo_count[0].text and nodo_count[0].text.strip().isdigit()
            else None
        )

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
                if not codigo_item:
                    codigo_item = linea.xpath(
                        './cac:Item/cac:SellersItemIdentification/cbc:ID',
                        namespaces=NAMESPACES
                    )
                if not codigo_item:
                    codigo_item = linea.xpath(
                        './cac:Item/cac:BuyersItemIdentification/cbc:ID',
                        namespaces=NAMESPACES
                    )
                precio_unitario = linea.xpath(
                    './cac:Price/cbc:PriceAmount', namespaces=NAMESPACES
                )

                id_val = (id_linea[0].text or '').strip() if id_linea else ''
                cantidad_val = (cantidad[0].text or '').strip() if cantidad else ''
                unidad_medida = cantidad[0].get('unitCode') if cantidad else None
                valor_val = (valor[0].text or '').strip() if valor else ''
                descripcion_val = (
                    (descripcion[0].text or '').strip() if descripcion else ''
                )
                codigo_val = (codigo_item[0].text or '').strip() if codigo_item else ''
                precio_unit_val = (
                    (precio_unitario[0].text or '').strip() if precio_unitario else ''
                )

                # Extraer impuestos a nivel de línea
                impuestos_linea = []
                tax_totals = linea.xpath('./cac:TaxTotal', namespaces=NAMESPACES)
                for tt in tax_totals:
                    subtotales = tt.xpath('./cac:TaxSubtotal', namespaces=NAMESPACES)
                    for st in subtotales:
                        nodo_tax_id = st.xpath(
                            './cac:TaxCategory/cac:TaxScheme/cbc:ID',
                            namespaces=NAMESPACES
                        )
                        nodo_percent = st.xpath(
                            './cac:TaxCategory/cbc:Percent', namespaces=NAMESPACES
                        )
                        nodo_tax_amount = st.xpath(
                            './cbc:TaxAmount', namespaces=NAMESPACES
                        )
                        nodo_taxable = st.xpath(
                            './cbc:TaxableAmount', namespaces=NAMESPACES
                        )
                        impuestos_linea.append({
                            'codigo_impuesto': (
                                (nodo_tax_id[0].text or '').strip()
                                if nodo_tax_id else None
                            ),
                            'tarifa': (
                                (nodo_percent[0].text or '').strip()
                                if nodo_percent else None
                            ),
                            'valor_impuesto': (
                                (nodo_tax_amount[0].text or '').strip()
                                if nodo_tax_amount else None
                            ),
                            'base_gravable': (
                                (nodo_taxable[0].text or '').strip()
                                if nodo_taxable else None
                            ),
                        })

                # Validaciones
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

                lineas_extraidas.append({
                    'numero_linea': int(id_val) if id_val.isdigit() else idx,
                    'cantidad': cantidad_val,
                    'unidad_medida': unidad_medida,
                    'valor_total_linea': valor_val,
                    'valor_unitario': precio_unit_val,
                    'descripcion': descripcion_val,
                    'codigo_item': codigo_val,
                    'impuestos': impuestos_linea,
                })

    if errores:
        mensaje = 'Errores en validación de líneas:\n' + '\n'.join(errores)
        resultado_validacion = False
        
        # Determinar el id_error más relevante
        if any('descripción vacía' in e for e in errores):
            id_error = IdTipoError.linea_sin_descripcion
        elif any('cantidad' in e for e in errores):
            id_error = IdTipoError.linea_cantidad_invalida
        elif any('valor' in e for e in errores):
            id_error = IdTipoError.linea_valor_invalido
        elif any('XML Invoice' in e for e in errores) or any('no contiene líneas' in e for e in errores):
            id_error = IdTipoError.linea_sin_descripcion # Consideramos como falta de descripción/ítem
        else:
            id_error = IdTipoError.linea_valor_invalido # fallback
            
    else:
        mensaje = 'Las líneas de la factura cumplen el requisito 8.'
        resultado_validacion = True

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'id_error': id_error,
        'datos': {
            'lineas': lineas_extraidas,
            'total_lineas': len(lineas_extraidas),
        }
    }

    return resultado
