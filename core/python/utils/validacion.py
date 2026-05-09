"""Módulo que contiene funciones de utilidad para la validación de las facturas
 electrónicas."""

# Standard library imports
from base64 import b64decode
from datetime import datetime, timezone
import hashlib
from typing import Optional, Tuple

# Third-party imports
from cryptography import x509

from decimal import Decimal
from decimal import ROUND_HALF_UP

from lxml import etree

from signxml import XMLVerifier
from signxml import SignatureConfiguration
from signxml.exceptions import InvalidSignature
from signxml.exceptions import InvalidCertificate

from metadata.db_metadata import IdTipoError
from metadata.db_metadata import IdTipoDocumentoIdentidad


def calcular_dv_nit_v1(nit: str) -> int:
    """Calcula el dígito de verificación DIAN para un NIT, basado en el algoritmo
     establecido en la resolución 000165 de 2023.
    
    Args:
        nit: El NIT a validar.
        
    Returns:
        El dígito de verificación calculado.
    
    """
    pesos = [71, 67, 59, 53, 47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3]

    nit = ''.join(filter(str.isdigit, nit))
    nit_15 = nit.zfill(15)

    suma = 0
    for i in range(15):
        suma += int(nit_15[i]) * pesos[i]

    residuo = suma % 11

    if residuo == 0:
        digito_validacion = 0
    elif residuo == 1:
        digito_validacion = 1
    else:
        digito_validacion = 11 - residuo
        
    return digito_validacion


def construir_cadena_base_cufe(
    xml_factura: etree._Element,
    namespaces: dict,
) -> tuple:
    """Construye la cadena base del CUFE a partir de los campos del Invoice."""
    cadena_base = None

    numero_factura = extraer_texto_xpath(xml_factura, './cbc:ID', namespaces)
    fecha_emision = extraer_texto_xpath(xml_factura, './cbc:IssueDate', namespaces)
    hora_emision = extraer_texto_xpath(xml_factura, './cbc:IssueTime', namespaces)
    valor_total = parsear_decimal_2dp(
        extraer_texto_xpath(
            xml_factura, './cac:LegalMonetaryTotal/cbc:PayableAmount', namespaces
        )
    )
    nit_adquiriente = extraer_texto_xpath(
        xml_factura,
        './cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID',
        namespaces,
    )
    clave_tecnica = extraer_texto_xpath(
        xml_factura,
        './/sts:SoftwareSecurityCode',
        namespaces,
    )
    ambiente = extraer_texto_xpath(xml_factura, './cbc:ProfileExecutionID', namespaces)

    partes_obligatorias = [
        numero_factura,
        fecha_emision,
        hora_emision,
        valor_total,
        nit_adquiriente,
        clave_tecnica,
        ambiente,
    ]

    impuestos = obtener_impuestos_cufe(xml_factura, namespaces)
    partes_impuestos = []
    for codigo_impuesto, valor_impuesto in impuestos:
        partes_impuestos.append(codigo_impuesto)
        partes_impuestos.append(valor_impuesto)

    if all(parte is not None and str(parte).strip() for parte in partes_obligatorias):
        partes = [
            numero_factura,
            fecha_emision,
            hora_emision,
            format(valor_total, 'f'),
        ] + partes_impuestos + [
            nit_adquiriente,
            clave_tecnica,
            ambiente,
        ]
        cadena_base = ''.join(partes)

    return cadena_base, ''


def extraer_certificado_firma(
    nodo_firma: etree._Element,
    namespaces: dict
) -> Optional[x509.Certificate]:
    """Extrae el certificado X.509 embebido en la firma XML."""
    certificado = None

    nodos_certificado = nodo_firma.xpath('.//ds:X509Certificate', namespaces=namespaces)

    if (
        nodos_certificado
        and nodos_certificado[0].text
        and nodos_certificado[0].text.strip()
    ):
        cert_b64 = ''.join(nodos_certificado[0].text.split())
        cert_der = b64decode(cert_b64)
        certificado = x509.load_der_x509_certificate(cert_der)

    return certificado


def extraer_nodo_firma(
        xml_factura: etree._Element, namespaces: dict
    ) -> Optional[etree._Element]:
    """Retorna el primer nodo ds:Signature encontrado."""
    nodo_firma = None

    nodos_firma = xml_factura.xpath(
        './ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/ds:Signature',
        namespaces=namespaces,
    )

    if nodos_firma:
        nodo_firma = nodos_firma[0]

    return nodo_firma


def extraer_texto_xpath(
    xml_factura: etree._Element,
    xpath: str,
    namespaces: dict,
) -> Optional[str]:
    """Extrae el texto del primer nodo encontrado por XPath."""
    valor = None

    nodos = xml_factura.xpath(xpath, namespaces=namespaces)
    if nodos:
        nodo = nodos[0]
        if nodo is not None and nodo.text and nodo.text.strip():
            valor = nodo.text.strip()

    return valor


def obtener_impuestos_cufe(
    xml_factura: etree._Element,
    namespaces: dict,
) -> list:
    """Obtiene los pares (CódigoImpuesto, ValorImpuesto) para el cálculo del CUFE."""
    impuestos = []

    codigos_impuesto = ['01', '02', '03', '04', '05', '06']

    for codigo in codigos_impuesto:
        valor_total = Decimal('0.00')

        nodos_subtotal = xml_factura.xpath(
            f'./cac:TaxTotal/cac:TaxSubtotal[cac:TaxCategory/cac:TaxScheme/cbc:ID="{codigo}"]',
            namespaces=namespaces,
        )

        for subtotal in nodos_subtotal:
            nodo_valor = subtotal.xpath('./cbc:TaxAmount', namespaces=namespaces)
            texto_valor = (
                nodo_valor[0].text.strip()
                if nodo_valor and nodo_valor[0] is not None 
                and nodo_valor[0].text and nodo_valor[0].text.strip()
                else None
            )

            if texto_valor is not None:
                try:
                    valor_total += Decimal(texto_valor)

                except Exception:
                    valor_total += Decimal('0.00')

        impuestos.append((
            codigo,
            format(valor_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), 'f'),
        ))

    return impuestos


def parsear_decimal_2dp(valor_texto: str | None) -> Decimal | None:
    """Convierte una cadena a Decimal con 2 decimales (redondeo HALF_UP).

    Args:
        valor_texto: Cadena que representa un número decimal.

    Returns:
        Decimal con 2 decimales o None si la cadena no es un número válido.

    """
    resultado = None
    texto_limpio = (valor_texto or '').strip()

    if texto_limpio:
        try:
            numero = Decimal(texto_limpio)
            resultado = numero.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            resultado = None

    return resultado


def validar_datos_persona(
    nombre: str, nit: str, scheme_name: str, dv_xml: str, rol: str = 'emisor'
    ) -> dict:
    """Valida el nombre y NIT de una persona (emisor o adquiriente) según las reglas de la
     resolución 000165 de 2023.
     
    Args:
        nombre: Nombre o razón social de la persona.
        nit: NIT de la persona.
        scheme_name: Valor del atributo schemeName del nodo CompanyID (código de
            tipo de documento según TIPO_DOCUMENTO_IDENTIDAD).
        dv_xml: Valor del atributo schemeID del nodo CompanyID (dígito de verificación).
        rol: 'emisor' o 'adquiriente'.
        
    Returns:
        Diccionario con:
        - mensaje: Descripción del resultado de la validación.
        - resultado: True si los datos son válidos, False en caso contrario.
        - id_error: Código de error granular si es inválido.
    
    """
    resultado_validacion = False
    id_error = None
    
    is_emisor = (rol == 'emisor')

    if not nombre:
        mensaje = 'No se encontró nombre de la persona.'
        id_error = IdTipoError.emisor_sin_nombre if is_emisor else IdTipoError.adquiriente_sin_nombre

    elif not nit:
        mensaje = f'Se encontró nombre "{nombre}" pero no documento.'
        id_error = IdTipoError.emisor_sin_documento if is_emisor else IdTipoError.adquiriente_sin_documento

    elif scheme_name and not IdTipoDocumentoIdentidad.es_codigo_valido(scheme_name):
        mensaje = (
            f'Se encontró nombre "{nombre}" con documento {nit}, pero el tipo '
            f'de documento "{scheme_name}" no es un código DIAN válido.'
        )
        id_error = IdTipoError.emisor_documento_invalido if is_emisor else IdTipoError.adquiriente_documento_invalido

    elif is_emisor and scheme_name and not IdTipoDocumentoIdentidad.es_valido_para_emisor(scheme_name):
        mensaje = (
            f'Se encontró nombre "{nombre}" con documento {nit}, pero el tipo '
            f'de documento "{scheme_name}" no es válido para un emisor.'
        )
        id_error = IdTipoError.emisor_documento_invalido

    elif not IdTipoDocumentoIdentidad.requiere_dv(scheme_name):
        # Documento que no requiere DV: válido si tiene nombre y número
        mensaje = f'Datos válidos: "{nombre}" con documento {nit}.'
        resultado_validacion = True

    elif not (6 <= len(nit) <= 15) or not nit.isdigit():
        mensaje = (
            f'Se encontró nombre "{nombre}" pero el NIT "{nit}" no es válido.'
        )
        id_error = IdTipoError.emisor_documento_invalido if is_emisor else IdTipoError.adquiriente_documento_invalido

    elif dv_xml is None or not dv_xml.isdigit():
        mensaje = (
            f'Se encontró nombre "{nombre}" y NIT "{nit}" '
            f'pero sin dígito de verificación válido.'
        )
        id_error = IdTipoError.emisor_dv_invalido if is_emisor else IdTipoError.adquiriente_dv_invalido

    else:
        dv_xml = int(dv_xml)
        dv_calculado = calcular_dv_nit_v1(nit)

        if dv_calculado != dv_xml:
            mensaje = (
                f'Se encontró nombre "{nombre}" y NIT "{nit}" pero DV incorrecto '
                f'(XML: {dv_xml}, Calculado: {dv_calculado}).'
            )
            id_error = IdTipoError.emisor_dv_invalido if is_emisor else IdTipoError.adquiriente_dv_invalido

        else:
            mensaje = f'Datos válidos: "{nombre}" con NIT {nit}-{dv_xml}.'
            resultado_validacion = True
    
    resultado = {
        'mensaje': mensaje,
        'resultado': resultado_validacion,
        'id_error': id_error
    }
    
    return resultado


def validar_estructura_minima_ubl_v1(
    xml_factura: etree._Element,
    namespaces: dict,
) -> Tuple[bool, str]:
    """Valida nodos mínimos esperados en un Invoice UBL."""
    resultado = False

    xpaths_obligatorios = [
        './cbc:ID',
        './cbc:IssueDate',
        './cac:AccountingSupplierParty',
        './cac:AccountingCustomerParty',
        './cac:LegalMonetaryTotal',
        './cac:InvoiceLine',
    ]

    faltantes = []

    for xpath in xpaths_obligatorios:
        nodos = xml_factura.xpath(xpath, namespaces=namespaces)
        if not nodos:
            faltantes.append(xpath)

    if not faltantes:
        resultado = True
        mensaje = 'El XML cumple con la estructura mínima UBL.'

    else:
        mensaje = (
            'El XML no cumple con la estructura mínima UBL. '
            f'Faltan nodos: {", ".join(faltantes)}.'
        )

    return resultado, mensaje


def validar_fecha_futura(fecha: str, hora: str) -> dict:
    """Valida que la fecha y hora no sean futuras.

    Args:
        fecha: Cadena de fecha en formato ISO (YYYY-MM-DD).
        hora: Cadena de hora en formato ISO (HH:MM:SS±HH:MM).

    Returns:
        Diccionario con 'mensaje' y 'resultado' (bool).
    """
    resultado_validacion = False

    dt_str = f'{fecha}T{hora}'

    # Normalizar timezone: -05:00 → -0500
    if dt_str[-3] == ':' and (dt_str[-6] == '+' or dt_str[-6] == '-'):
        dt_str = dt_str[:-3] + dt_str[-2:]

    fecha_hora_dt = datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%S%z')

    ahora_utc = datetime.now(timezone.utc)

    fecha_hora_utc = fecha_hora_dt.astimezone(timezone.utc)

    if fecha_hora_utc > ahora_utc:
        mensaje = (
            f'Fecha y hora futuras (Fecha = "{fecha}", Hora = "{hora}").'
        )
    else:
        mensaje = f'Fecha y hora válidas: {fecha} {hora}.'
        resultado_validacion = True

    validacion = {'mensaje': mensaje, 'resultado': resultado_validacion}

    return validacion


def validar_firma_criptografica_y_confianza(
    xml_factura: etree._Element,
    ruta_ca_confiable: str,
) -> Tuple[bool, str]:
    """Verifica la firma XMLDSig/XAdES.

    Cubre:
    - Integridad (DigestValue)
    - Firma (SignatureValue)
    - Cadena de confianza (CA)
    """
    resultado = False
    mensaje = ''

    try:
        config = SignatureConfiguration(require_x509=True)

        if ruta_ca_confiable:
            XMLVerifier().verify(
                xml_factura,
                ca_pem_file=ruta_ca_confiable,
                expect_config=config,
            )
            resultado = True
            mensaje = 'Firma digital válida y cadena de confianza verificada.'
        else:
            mensaje = (
                'No se configuró RUTA_CA_CONFIABLE_XML_DSIG para validar '
                'la cadena de confianza.'
            )

    except (InvalidSignature, InvalidCertificate) as exc:
        mensaje = (
            'La firma digital no es válida o no confía en la cadena del certificado: '
            f'{exc}'
        )
    except Exception as exc:
        mensaje = f'No fue posible verificar la firma digital: {exc}'

    return resultado, mensaje


def validar_vigencia_certificado(certificado: x509.Certificate) -> Tuple[bool, str]:
    """Valida vigencia temporal del certificado."""
    resultado = False
    mensaje = ''

    ahora = datetime.now(timezone.utc)

    if certificado.not_valid_before_utc <= ahora <= certificado.not_valid_after_utc:
        resultado = True
    else:
        mensaje = (
            'El certificado de la firma digital se encuentra vencido o aún no es válido '
            f'(vigencia: {certificado.not_valid_before_utc.isoformat()} a '
            f'{certificado.not_valid_after_utc.isoformat()}).'
        )

    return resultado, mensaje


def validar_xml_contra_xsd_v1(
    xml_factura: etree._Element,
    ruta_xsd: str,
) -> Tuple[bool, str]:
    """Valida el XML contra el esquema XSD UBL."""
    resultado = False
    mensaje = ''

    try:
        with open(ruta_xsd, 'rb') as f:
            schema_doc = etree.parse(f)
            schema = etree.XMLSchema(schema_doc)

        xml_doc = etree.ElementTree(xml_factura)

        if schema.validate(xml_doc):
            resultado = True
            mensaje = 'El XML cumple con el esquema XSD UBL.'
        else:
            errores = [str(e) for e in schema.error_log]
            mensaje = f'Error de validación XSD: {" | ".join(errores)}'

    except Exception as exc:
        mensaje = f'No fue posible validar el XML contra el XSD: {exc}'

    return resultado, mensaje
