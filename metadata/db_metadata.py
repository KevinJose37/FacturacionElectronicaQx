"""Metadatos del módulo de base de datos.

Mensajes de error y textos del pool de conexiones y cache.
"""

class IdEstadoProceso:
    """Estados de proceso para ingesta de facturas."""

    pendiente = 1
    """Estado pendiente de procesamiento."""

    en_proceso = 2
    """Estado en proceso de ingesta."""

    procesado = 3
    """Estado procesado de ingesta."""

    error = 4
    """Estado de error en el procesamiento."""

    fallido = 5
    """Estado de fallo definitivo (agotó reintentos)."""


class IdTipoArchivo:
    """Tipos de archivos para ingesta de facturas."""

    zip = 1
    """Archivo ZIP para ingesta de facturas."""

    xml = 2
    """Archivo XML para ingesta de facturas."""

    pdf = 3
    """Archivo PDF para ingesta de facturas."""


class IdTipoProceso:
    """Tipos de procesos de ingesta de facturas.

    Corresponden a la tabla FACTURACION.TIPO_PROCESO.
    """

    escaneo_malware = 1
    """Verificación de archivos contra virus y malware."""

    descarga_almacenamiento = 2
    """Descarga y almacenamiento del archivo en S3."""

    validacion_contenido_zip = 3
    """Verificación de que el ZIP contiene XML y PDF completos."""

    extraccion_zip = 4
    """Extracción de archivos del ZIP."""

    registro_adjuntos = 5
    """Registro de adjuntos en la base de datos."""

    # -- Procesamiento de factura electrónica --

    validacion_cufe = 6
    """Validación y extracción del CUFE."""

    validacion_denominacion = 7
    """Validar denominación como factura electrónica de venta."""

    extraccion_emisor = 8
    """Extracción datos del vendedor/emisor."""

    extraccion_adquiriente = 9
    """Extracción datos del adquiriente."""

    validacion_numeracion = 10
    """Validación de la numeración autorizada DIAN."""

    validacion_fecha_generacion = 11
    """Validar fecha y hora de generación."""

    validacion_fecha_validacion = 12
    """Validar fecha y hora de validación/expedición DIAN."""

    validacion_documento_dian = 13
    """Validar el documento «Documento validado por la DIAN»."""

    extraccion_lineas = 14
    """Extracción de líneas/ítems de la factura."""

    validacion_valor_total = 15
    """Validar valor total vs sumatoria de líneas."""

    extraccion_forma_pago = 16
    """Extracción de la forma de pago."""

    extraccion_medio_pago = 17
    """Extracción del medio de pago."""

    extraccion_calidad_tributaria = 18
    """Extracción de la calidad tributaria del emisor."""

    extraccion_impuestos = 19
    """Extracción de impuestos a nivel factura."""

    validacion_firma_digital = 20
    """Validación de la firma digital del facturador."""

    extraccion_qr = 21
    """Extracción y validación del código QR."""

    validacion_anexo_tecnico = 22
    """Validación del anexo técnico UBL."""

    extraccion_software = 23
    """Extracción datos del software y proveedor tecnológico."""

    registro_factura = 24
    """Registro final de la factura en BD."""

    verificacion_grafica = 25
    """Verificación de representación gráfica PDF vs XML."""
    
    filtro_recepcion = 26
    """Evaluación de correo en filtro de recepción de facturación."""


class IdTipoError:
    """Tipos de error en el procesamiento de ingesta.

    Corresponden a la tabla FACTURACION.TIPO_ERROR.
    Se usan en la columna ID_ERROR de PROCESO_INGESTA.
    """

    # -- Escaneo de malware (ESCANEO_MALWARE) --
    malware_detectado = 1
    """ClamAV detectó virus o malware en el archivo."""

    extension_prohibida = 2
    """El archivo tiene una extensión peligrosa (.exe, .bat, etc.)."""

    tamano_excedido = 3
    """El archivo excede el tamaño máximo permitido."""

    # -- Validación de contenido ZIP (VALIDACION_CONTENIDO_ZIP) --
    zip_corrupto = 4
    """El archivo ZIP está corrupto o no es válido."""

    zip_sin_xml = 5
    """El ZIP no contiene archivos XML de factura."""

    zip_profundidad_excedida = 6
    """ZIPs anidados exceden la profundidad máxima permitida."""

    zip_subzip_invalido = 7
    """Un sub-ZIP dentro del ZIP principal no contiene pares válidos."""

    # -- Descarga y almacenamiento (DESCARGA_ALMACENAMIENTO) --
    fallo_descarga_adjuntos = 8
    """No se pudieron descargar los adjuntos del correo."""

    fallo_subida_s3 = 9
    """Error al subir el archivo a S3."""

    fallo_registro_bd = 10
    """Error al registrar el adjunto en la base de datos."""

    # -- Extracción de XMLs embebidos (EXTRACCION_ZIP) --
    xml_embebido_no_encontrado = 11
    """No se encontraron los XMLs de Invoice o ApplicationResponse embebidos."""

    xml_embebido_parse_error = 12
    """Error al parsear el XML AttachedDocument para extraer embebidos."""

    # -- Emparejamiento XML/PDF --
    pdf_faltante = 13
    """No se encontró un PDF correspondiente al XML."""

    pdf_sin_xml = 14
    """Se encontró un PDF sin XML correspondiente."""

    # -- Filtro de facturación --
    correo_sin_adjuntos_validos = 15
    """El correo de facturación no contiene adjuntos válidos (ZIP, XML o PDF)."""

    correo_rechazado_filtro = 16
    """El correo no cumple los criterios del filtro de facturación."""

    # -- Errores generales --
    error_procesamiento_general = 17
    """Error inesperado durante el procesamiento del correo."""

    adjunto_duplicado = 18
    """El adjunto ya fue procesado previamente (hash duplicado)."""

    # -- Procesamiento de factura electrónica --

    cufe_no_encontrado = 19
    """No se encontró el CUFE en el XML."""

    cufe_invalido = 20
    """El CUFE del XML no es válido o no coincide con el recalculado."""

    xml_parse_error = 21
    """Error al parsear el XML descargado de S3."""

    datos_emisor_invalidos = 22
    """No se pudieron extraer los datos del emisor."""

    datos_adquiriente_invalidos = 23
    """No se pudieron extraer los datos del adquiriente."""

    numeracion_invalida = 24
    """La numeración de la factura no es válida."""

    fecha_generacion_invalida = 25
    """Fecha de generación inválida o futura."""

    fecha_validacion_invalida = 26
    """Fecha de validación DIAN inválida."""

    validacion_dian_fallo = 27
    """El documento no fue validado por la DIAN."""

    lineas_invalidas = 28
    """Las líneas de la factura no cumplen los requisitos."""

    valor_total_inconsistente = 29
    """El valor total no coincide con la sumatoria de líneas."""

    forma_pago_invalida = 30
    """Forma de pago inválida o faltante."""

    medio_pago_invalido = 31
    """Medio de pago inválido (requerido para pago de contado)."""

    calidad_tributaria_faltante = 32
    """No se informó la calidad tributaria del emisor."""

    impuestos_invalidos = 33
    """Impuestos con datos faltantes o inconsistentes."""

    firma_digital_invalida = 34
    """La firma digital no es válida."""

    qr_invalido = 35
    """El código QR es inválido o inconsistente."""

    anexo_tecnico_invalido = 36
    """El XML no cumple con el anexo técnico UBL."""

    software_proveedor_faltante = 37
    """No se informó el fabricante de software."""

    error_registro_factura = 38
    """Error al registrar la factura en la BD."""

    max_reintentos_excedido = 39
    """Se excedió el máximo de reintentos."""

    emisor_sin_nombre = 40
    """El emisor no tiene nombre o razón social."""

    emisor_sin_documento = 41
    """El emisor no tiene número de documento o NIT."""

    emisor_documento_invalido = 42
    """El documento del emisor tiene un formato inválido."""

    emisor_dv_invalido = 43
    """El dígito de verificación del emisor es incorrecto."""

    adquiriente_sin_nombre = 44
    """El adquiriente no tiene nombre o razón social."""

    adquiriente_sin_documento = 45
    """El adquiriente no tiene número de documento o NIT."""

    adquiriente_documento_invalido = 46
    """El documento del adquiriente tiene un formato inválido."""

    adquiriente_dv_invalido = 47
    """El dígito de verificación del adquiriente es incorrecto."""

    numeracion_sin_rango_autorizado = 48
    """La factura no incluye la información del rango de numeración autorizado."""

    numeracion_fuera_de_rango = 49
    """El número de factura está fuera del rango autorizado por la DIAN."""

    numeracion_vencida = 50
    """La autorización de numeración de la factura se encuentra vencida."""

    fecha_generacion_futura = 51
    """La fecha de generación de la factura es una fecha futura."""

    fecha_generacion_formato_invalido = 52
    """El formato de la fecha de generación es inválido o no se pudo extraer."""

    linea_sin_descripcion = 53
    """Una o más líneas de la factura no tienen descripción del ítem."""

    linea_valor_invalido = 54
    """Una o más líneas tienen valores nulos o inválidos en precios o cantidades."""

    linea_cantidad_invalida = 55
    """Una o más líneas tienen una cantidad reportada inválida."""

    denominacion_incorrecta = 56
    """La denominación del documento no corresponde a Factura Electrónica de Venta."""

    tipo_documento_dian_invalido = 57
    """El código de tipo de documento (InvoiceTypeCode) es inválido."""

    profile_id_no_encontrado = 58
    """No se encontró el nodo cbc:ProfileID para validar la denominación."""



class IdFormaPago:
    """Formas de pago según catálogo DIAN.

    Corresponden a la tabla TIPO_FORMA_PAGO.
    """

    contado = '1'
    """Contado."""

    credito = '2'
    """Crédito."""

    CODIGOS_VALIDOS = {'1', '2'}

    @classmethod
    def es_codigo_valido(cls, codigo: str) -> bool:
        """Verifica si un código de forma de pago es válido."""
        return codigo in cls.CODIGOS_VALIDOS


class IdMedioPago:
    """Medios de pago según catálogo DIAN (ISO 4217/UN/EDIFACT TRED 4461).

    Corresponden a la tabla TIPO_MEDIO_PAGO.
    Solo se nombran los códigos más frecuentes; el set completo está en
    CODIGOS_VALIDOS.
    """

    instrumento_no_definido = '1'
    """Instrumento no definido."""

    credito_ach = '2'
    """Crédito ACH."""

    debito_ach = '3'
    """Débito ACH."""

    efectivo = '10'
    """Efectivo."""

    cheque = '20'
    """Cheque."""

    transferencia_credito = '30'
    """Transferencia Crédito."""

    transferencia_debito = '31'
    """Transferencia Débito."""

    consignacion_bancaria = '42'
    """Consignación bancaria."""

    tarjeta_credito = '48'
    """Tarjeta Crédito."""

    tarjeta_debito = '49'
    """Tarjeta Débito."""

    otro = 'ZZZ'
    """Otro."""

    CODIGOS_VALIDOS = {
        '1', '2', '3', '4', '5', '6', '7', '9',
        '10', '11', '12', '13', '14', '15', '16', '17', '18', '19',
        '20', '21', '22', '23', '24', '25', '26', '27', '28', '29',
        '30', '31', '32', '33', '34', '35', '36', '37', '38', '39',
        '40', '41', '42', '43', '44', '45', '46', '47', '48', '49',
        '50', '51', '52', '53',
        '60', '61', '62', '63', '64', '65', '66', '67',
        '70', '71', '72', '74', '75', '76', '77', '78',
        '91', '92', '93', '94', '95', '96', '97',
        'ZZZ',
    }

    @classmethod
    def es_codigo_valido(cls, codigo: str) -> bool:
        """Verifica si un código de medio de pago es válido."""
        return codigo in cls.CODIGOS_VALIDOS


class IdResponsabilidadFiscal:
    """Responsabilidades fiscales DIAN (TaxLevelCode).

    Corresponden a la tabla TIPO_CONDICION_FISCAL.
    """

    gran_contribuyente = 'O-13'
    """Gran contribuyente."""

    autorretenedor = 'O-15'
    """Autorretenedor."""

    agente_retencion_iva = 'O-23'
    """Agente de retención IVA."""

    regimen_simple = 'O-47'
    """Régimen simple de tributación."""

    no_aplica_otros = 'R-99-PN'
    """No aplica – Otros."""

    CODIGOS_VALIDOS = {'O-13', 'O-15', 'O-23', 'O-47', 'R-99-PN'}

    @classmethod
    def es_codigo_valido(cls, codigo: str) -> bool:
        """Verifica si un código de responsabilidad fiscal es válido."""
        return codigo in cls.CODIGOS_VALIDOS


class IdTipoDocumentoIdentidad:
    """Tipos de documento de identificación tributaria (Anexo 1.9 DIAN).

    Corresponden a la tabla TIPO_DOCUMENTO_IDENTIDAD.
    Los códigos provienen del schemeName de cbc:CompanyID / sts:ProviderID.
    """

    certificado_nacido_vivo = '10'
    """Certificado de nacido vivo."""

    registro_civil = '11'
    """Registro civil."""

    tarjeta_identidad = '12'
    """Tarjeta de identidad."""

    cedula_ciudadania = '13'
    """Cédula de ciudadanía."""

    tarjeta_extranjeria = '21'
    """Tarjeta de extranjería."""

    cedula_extranjeria = '22'
    """Cédula de extranjería."""

    nit = '31'
    """NIT."""

    pasaporte = '41'
    """Pasaporte."""

    documento_extranjero = '42'
    """Documento de identificación extranjero."""

    pep = '47'
    """PEP (Permiso Especial de Permanencia)."""

    ppt = '48'
    """PPT (Permiso Protección Temporal)."""

    nit_otro_pais = '50'
    """NIT de otro país."""

    nuip = '91'
    """NUIP (solo para adquiriente)."""

    # Todos los códigos válidos
    CODIGOS_VALIDOS = {
        '10', '11', '12', '13', '21', '22', '31',
        '41', '42', '47', '48', '50', '91',
    }

    # Códigos que NO aplican para el emisor (solo adquiriente)
    CODIGOS_SOLO_ADQUIRIENTE = {'91'}

    @classmethod
    def es_codigo_valido(cls, codigo: str) -> bool:
        """Verifica si un código de documento es válido."""
        return codigo in cls.CODIGOS_VALIDOS

    @classmethod
    def es_valido_para_emisor(cls, codigo: str) -> bool:
        """Verifica si el código es válido para un emisor/vendedor."""
        return codigo in cls.CODIGOS_VALIDOS and codigo not in cls.CODIGOS_SOLO_ADQUIRIENTE

    @classmethod
    def requiere_dv(cls, codigo: str) -> bool:
        """Verifica si el tipo de documento requiere dígito de verificación."""
        return codigo == cls.nit


class IdTipoDocumentoDian:
    """Tipos de documento electrónico DIAN (InvoiceTypeCode).

    Corresponden a la tabla TIPO_DOCUMENTO_DIAN.
    """

    factura_electronica = '01'
    """Factura electrónica de Venta."""

    factura_exportacion = '02'
    """Factura electrónica de venta - exportación."""

    instrumento_transmision = '03'
    """Instrumento electrónico de transmisión - tipo 03."""

    factura_tipo_04 = '04'
    """Factura electrónica de Venta - tipo 04."""

    nota_credito = '91'
    """Nota Crédito."""

    nota_debito = '92'
    """Nota Débito."""

    eventos = '96'
    """Eventos (ApplicationResponse)."""

    # Códigos de factura válidos para el flujo de ingesta
    CODIGOS_FACTURA_VALIDOS = {'01', '02', '03', '04'}

    @classmethod
    def es_factura_valida(cls, codigo: str) -> bool:
        """Verifica si el código corresponde a una factura electrónica válida."""
        return codigo in cls.CODIGOS_FACTURA_VALIDOS


class IdTipoImpuesto:
    """Tipos de impuesto según catálogo DIAN.

    Corresponden a la tabla TIPO_IMPUESTO.
    Los códigos son los definidos por la DIAN en el Anexo Técnico.
    """

    iva = '01'
    """Impuesto sobre la Ventas."""

    ic = '02'
    """Impuesto al Consumo Departamental Nominal."""

    ica = '03'
    """Impuesto de Industria, Comercio y Aviso."""

    inc = '04'
    """Impuesto Nacional al Consumo."""

    rete_iva = '05'
    """Retención sobre el IVA."""

    rete_renta = '06'
    """Retención sobre Renta."""

    rete_ica = '07'
    """Retención sobre el ICA."""

    ic_porcentual = '08'
    """Impuesto al Consumo Departamental Porcentual."""

    fto_horticultura = '20'
    """Cuota de Fomento Hortifrutícola."""

    timbre = '21'
    """Impuesto de Timbre."""

    inc_bolsas = '22'
    """Impuesto Nacional al Consumo de Bolsa Plástica."""

    in_carbono = '23'
    """Impuesto Nacional del Carbono."""

    in_combustibles = '24'
    """Impuesto Nacional a los Combustibles."""

    sobretasa_combustibles = '25'
    """Sobretasa a los combustibles."""

    sordicom = '26'
    """Contribución minoristas (Combustibles)."""

    ic_datos = '30'
    """Impuesto al Consumo de Datos."""

    icl = '32'
    """Impuesto al Consumo de Licores."""

    inpp = '33'
    """Impuesto nacional productos plásticos."""

    ibua = '34'
    """Impuesto a las bebidas ultraprocesadas azucaradas."""

    icui = '35'
    """Impuesto a los productos comestibles ultraprocesados industrialmente."""

    adv = '36'
    """AD VALOREM."""

    otros = 'ZZ'
    """Otros tributos, tasas, contribuciones, y similares."""

    @classmethod
    def es_codigo_valido(cls, codigo: str) -> bool:
        """Verifica si un código de impuesto es válido."""
        codigos = {
            v for k, v in vars(cls).items()
            if not k.startswith('_') and isinstance(v, str)
        }
        return codigo in codigos


class IdTipoEventoDian:
    """Tipos de eventos de la DIAN.
    
    Corresponden a la tabla TIPO_EVENTO_DIAN.
    """

    documento_validado_dian = '02'
    """Documento validado por la DIAN."""

    documento_rechazado_dian = '04'
    """Documento rechazado por la DIAN."""

    acuse_recibo_fev = '030'
    """Acuse de recibo de Factura Electrónica de Venta."""

    reclamo_fev = '031'
    """Reclamo de la Factura Electrónica de Venta."""

    recibo_bien_prestacion_servicio = '032'
    """Recibo del bien o prestación del servicio."""

    aceptacion_expresa = '033'
    """Aceptación expresa."""

    aceptacion_tacita = '034'
    """Aceptación Tácita."""


class MensajesDB:
    """Mensajes de error y log del módulo de base de datos."""

    pool_no_inicializado = 'El pool de conexiones no ha sido inicializado. Llama a init_pool() primero.'
    """Error cuando se intenta obtener el pool antes de inicializarlo. Usado en connection.py."""

    pool_inicializado = 'Pool de conexiones async inicializado (%s:%s/%s)'
    """Mensaje de log al inicializar el pool. Usado en connection.py."""

    pool_cerrado = 'Pool de conexiones async cerrado.'
    """Mensaje de log al cerrar el pool. Usado en connection.py."""

    cache_set = 'Cache SET: %s (ttl=%ds)'
    """Mensaje de log al guardar una entrada en cache. Usado en cache.py."""

    cache_cleared = 'Cache CLEARED (all keys)'
    """Mensaje de log al limpiar todo el cache. Usado en cache.py."""

    cache_invalidated = 'Cache INVALIDATED: %s'
    """Mensaje de log al invalidar una clave específica. Usado en cache.py."""
