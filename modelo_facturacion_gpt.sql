CREATE SCHEMA IF NOT EXISTS FACTURACION;

-- =========================
-- CATÁLOGOS (Tablas TIPO_...)
-- =========================

CREATE TABLE FACTURACION.TIPO_ESTADO_PROCESO (
    ID_ESTADO_PROCESO INT PRIMARY KEY,
    CODIGO_REFERENCIA VARCHAR(30) UNIQUE NOT NULL,
    DESCRIPCION       VARCHAR(150) NOT NULL
);

INSERT INTO FACTURACION.TIPO_ESTADO_PROCESO (ID_ESTADO_PROCESO, CODIGO_REFERENCIA, DESCRIPCION) VALUES
(1, 'PENDIENTE', 'Pendiente de procesamiento'),
(2, 'EN_PROCESO', 'En proceso de ingesta'),
(3, 'PROCESADO', 'Procesado de ingesta'),
(4, 'ERROR', 'Estado de error en el procesamiento'),
(5, 'FALLIDO', 'Estado de fallo definitivo (agotó reintentos)')
ON CONFLICT DO NOTHING;

CREATE TABLE FACTURACION.TIPO_ARCHIVO (
    ID_TIPO_ARCHIVO   INT PRIMARY KEY,
    CODIGO_REFERENCIA VARCHAR(30) UNIQUE NOT NULL,
    DESCRIPCION       VARCHAR(150) NOT NULL
);

INSERT INTO FACTURACION.TIPO_ARCHIVO (ID_TIPO_ARCHIVO, CODIGO_REFERENCIA, DESCRIPCION) VALUES
(1, 'ZIP', 'Archivo ZIP'),
(2, 'XML', 'Archivo XML'),
(3, 'PDF', 'Archivo PDF')
ON CONFLICT DO NOTHING;


CREATE TABLE FACTURACION.TIPO_PROCESO (
    ID_TIPO_PROCESO   INT PRIMARY KEY,
    CODIGO_REFERENCIA VARCHAR(50) UNIQUE NOT NULL,
    DESCRIPCION       VARCHAR(200) NOT NULL
);

INSERT INTO FACTURACION.TIPO_PROCESO (ID_TIPO_PROCESO, CODIGO_REFERENCIA, DESCRIPCION) VALUES
(1,  'ESCANEO_MALWARE',              'Verificación de archivos contra virus y malware'),
(2,  'DESCARGA_ALMACENAMIENTO',      'Descarga y almacenamiento del archivo en S3'),
(3,  'VALIDACION_CONTENIDO_ZIP',     'Verificación de que el ZIP contiene XML y PDF completos'),
(4,  'EXTRACCION_ZIP',               'Extracción de archivos del ZIP'),
(5,  'REGISTRO_ADJUNTOS',            'Registro de adjuntos en la base de datos'),
(6,  'VALIDACION_CUFE',              'Validación y extracción del CUFE'),
(7,  'VALIDACION_DENOMINACION',      'Validar denominación como factura electrónica de venta'),
(8,  'EXTRACCION_EMISOR',            'Extracción datos del vendedor/emisor'),
(9,  'EXTRACCION_ADQUIRIENTE',       'Extracción datos del adquiriente'),
(10, 'VALIDACION_NUMERACION',        'Validación de la numeración autorizada DIAN'),
(11, 'VALIDACION_FECHA_GENERACION',  'Validar fecha y hora de generación'),
(12, 'VALIDACION_FECHA_VALIDACION',  'Validar fecha y hora de validación/expedición DIAN'),
(13, 'VALIDACION_DOCUMENTO_DIAN',    'Validar documento «Documento validado por la DIAN»'),
(14, 'EXTRACCION_LINEAS',            'Extracción de líneas/ítems de la factura'),
(15, 'VALIDACION_VALOR_TOTAL',       'Validar valor total vs sumatoria de líneas'),
(16, 'EXTRACCION_FORMA_PAGO',        'Extracción de la forma de pago'),
(17, 'EXTRACCION_MEDIO_PAGO',        'Extracción del medio de pago'),
(18, 'EXTRACCION_CALIDAD_TRIBUTARIA','Extracción de la calidad tributaria del emisor'),
(19, 'EXTRACCION_IMPUESTOS',         'Extracción de impuestos a nivel factura'),
(20, 'VALIDACION_FIRMA_DIGITAL',     'Validación de la firma digital del facturador'),
(21, 'EXTRACCION_QR',                'Extracción y validación del código QR'),
(22, 'VALIDACION_ANEXO_TECNICO',     'Validación del anexo técnico UBL'),
(23, 'EXTRACCION_SOFTWARE',          'Extracción datos del software y proveedor tecnológico'),
(24, 'REGISTRO_FACTURA',             'Registro final de la factura en BD')
ON CONFLICT DO NOTHING;


CREATE TABLE FACTURACION.TIPO_ERROR (
    ID_TIPO_ERROR     INT PRIMARY KEY,
    CODIGO_REFERENCIA VARCHAR(50) UNIQUE NOT NULL,
    DESCRIPCION       VARCHAR(200) NOT NULL
);

INSERT INTO FACTURACION.TIPO_ERROR (ID_TIPO_ERROR, CODIGO_REFERENCIA, DESCRIPCION) VALUES
(1,  'MALWARE_DETECTADO',            'Se detectó virus o malware en el archivo'),
(2,  'EXTENSION_PROHIBIDA',          'El archivo tiene una extensión peligrosa (.exe, .bat, etc.)'),
(3,  'TAMANO_EXCEDIDO',              'El archivo excede el tamaño máximo permitido'),
(4,  'ZIP_CORRUPTO',                 'El archivo ZIP está corrupto o no es válido'),
(5,  'ZIP_SIN_XML',                  'El ZIP no contiene archivos XML de factura'),
(6,  'ZIP_PROFUNDIDAD_EXCEDIDA',     'ZIPs anidados exceden la profundidad máxima permitida'),
(7,  'ZIP_SUBZIP_INVALIDO',          'Un sub-ZIP dentro del ZIP principal no contiene pares válidos'),
(8,  'FALLO_DESCARGA_ADJUNTOS',      'No se pudieron descargar los adjuntos del correo'),
(9,  'FALLO_SUBIDA_S3',              'Error al subir el archivo a S3'),
(10, 'FALLO_REGISTRO_BD',            'Error al registrar el adjunto en la base de datos'),
(11, 'XML_EMBEBIDO_NO_ENCONTRADO',   'No se encontraron los XMLs de Invoice o ApplicationResponse embebidos'),
(12, 'XML_EMBEBIDO_PARSE_ERROR',     'Error al parsear el XML AttachedDocument para extraer embebidos'),
(13, 'PDF_FALTANTE',                 'No se encontró un PDF correspondiente al XML'),
(14, 'PDF_SIN_XML',                  'Se encontró un PDF sin XML correspondiente'),
(15, 'CORREO_SIN_ADJUNTOS_VALIDOS',  'El correo de facturación no contiene adjuntos válidos'),
(16, 'CORREO_RECHAZADO_FILTRO',      'El correo no cumple los criterios del filtro de facturación'),
(17, 'ERROR_PROCESAMIENTO_GENERAL',  'Error inesperado durante el procesamiento del correo'),
(18, 'ADJUNTO_DUPLICADO',            'El adjunto ya fue procesado previamente (hash duplicado)'),
(19, 'CUFE_NO_ENCONTRADO',           'No se encontró el CUFE en el XML'),
(20, 'CUFE_INVALIDO',                'El CUFE del XML no es válido o no coincide con el recalculado'),
(21, 'XML_PARSE_ERROR',              'Error al parsear el XML descargado de S3'),
(26, 'FECHA_VALIDACION_INVALIDA',    'Fecha de validación DIAN inválida'),
(27, 'VALIDACION_DIAN_FALLO',        'El documento no fue validado por la DIAN'),
(29, 'VALOR_TOTAL_INCONSISTENTE',    'El valor total no coincide con la sumatoria de líneas'),
(30, 'FORMA_PAGO_INVALIDA',          'Forma de pago inválida o faltante'),
(31, 'MEDIO_PAGO_INVALIDO',          'Medio de pago inválido (requerido para pago de contado)'),
(32, 'CALIDAD_TRIBUTARIA_FALTANTE',  'No se informó la calidad tributaria del emisor'),
(33, 'IMPUESTOS_INVALIDOS',          'Impuestos con datos faltantes o inconsistentes'),
(34, 'FIRMA_DIGITAL_INVALIDA',       'La firma digital no es válida'),
(35, 'QR_INVALIDO',                  'El código QR es inválido o inconsistente'),
(36, 'ANEXO_TECNICO_INVALIDO',       'El XML no cumple con el anexo técnico UBL'),
(37, 'SOFTWARE_PROVEEDOR_FALTANTE',  'No se informó el fabricante de software'),
(38, 'ERROR_REGISTRO_FACTURA',       'Error al registrar la factura en la BD'),
(39, 'MAX_REINTENTOS_EXCEDIDO',      'Se excedió el máximo de reintentos'),
(40, 'EMISOR_SIN_NOMBRE',            'El emisor no tiene nombre o razón social'),
(41, 'EMISOR_SIN_DOCUMENTO',         'El emisor no tiene número de documento o NIT'),
(42, 'EMISOR_DOCUMENTO_INVALIDO',    'El documento del emisor tiene un formato inválido'),
(43, 'EMISOR_DV_INVALIDO',           'El dígito de verificación del emisor es incorrecto'),
(44, 'ADQUIRIENTE_SIN_NOMBRE',       'El adquiriente no tiene nombre o razón social'),
(45, 'ADQUIRIENTE_SIN_DOCUMENTO',    'El adquiriente no tiene número de documento o NIT'),
(46, 'ADQUIRIENTE_DOCUMENTO_INVALIDO', 'El documento del adquiriente tiene un formato inválido'),
(47, 'ADQUIRIENTE_DV_INVALIDO',      'El dígito de verificación del adquiriente es incorrecto'),
(48, 'NUMERACION_SIN_RANGO_AUTORIZADO', 'La factura no incluye la información del rango de numeración autorizado'),
(49, 'NUMERACION_FUERA_DE_RANGO',    'El número de factura está fuera del rango autorizado por la DIAN'),
(50, 'NUMERACION_VENCIDA',           'La autorización de numeración de la factura se encuentra vencida'),
(51, 'FECHA_GENERACION_FUTURA',      'La fecha de generación de la factura es una fecha futura'),
(52, 'FECHA_GENERACION_FORMATO_INVALIDO', 'El formato de la fecha de generación es inválido o no se pudo extraer'),
(53, 'LINEA_SIN_DESCRIPCION',        'Una o más líneas de la factura no tienen descripción del ítem'),
(54, 'LINEA_VALOR_INVALIDO',         'Una o más líneas tienen valores nulos o inválidos en precios o cantidades'),
(55, 'LINEA_CANTIDAD_INVALIDA',      'Una o más líneas tienen una cantidad reportada inválida')
ON CONFLICT DO NOTHING;


CREATE TABLE FACTURACION.TIPO_EVENTO_DIAN (
    CODIGO_EVENTO     VARCHAR(10) PRIMARY KEY,
    NOMBRE_EVENTO     VARCHAR(150) NOT NULL
);

INSERT INTO FACTURACION.TIPO_EVENTO_DIAN (CODIGO_EVENTO, NOMBRE_EVENTO) VALUES
('02', 'Documento validado por la DIAN'),
('04', 'Documento rechazado por la DIAN'),
('030', 'Acuse de recibo de Factura Electrónica de Venta'),
('031', 'Reclamo de la Factura Electrónica de Venta'),
('032', 'Recibo del bien o prestación del servicio'),
('033', 'Aceptación expresa'),
('034', 'Aceptación Tácita')
ON CONFLICT DO NOTHING;


CREATE TABLE FACTURACION.TIPO_FORMA_PAGO (
    CODIGO_FORMA_PAGO VARCHAR(10) PRIMARY KEY,
    DESCRIPCION       VARCHAR(100) NOT NULL
);

INSERT INTO FACTURACION.TIPO_FORMA_PAGO (CODIGO_FORMA_PAGO, DESCRIPCION) VALUES
('1', 'Contado'),
('2', 'Crédito')
ON CONFLICT DO NOTHING;


CREATE TABLE FACTURACION.TIPO_MEDIO_PAGO (
    CODIGO_MEDIO_PAGO VARCHAR(10) PRIMARY KEY,
    DESCRIPCION       VARCHAR(200) NOT NULL
);

INSERT INTO FACTURACION.TIPO_MEDIO_PAGO (CODIGO_MEDIO_PAGO, DESCRIPCION) VALUES
('1',   'Instrumento no definido'),
('2',   'Crédito ACH'),
('3',   'Débito ACH'),
('4',   'Reversión débito de demanda ACH'),
('5',   'Reversión crédito de demanda ACH'),
('6',   'Crédito de demanda ACH'),
('7',   'Débito de demanda ACH'),
('9',   'Clearing Nacional o Regional'),
('10',  'Efectivo'),
('11',  'Reversión Crédito Ahorro'),
('12',  'Reversión Débito Ahorro'),
('13',  'Crédito Ahorro'),
('14',  'Débito Ahorro'),
('15',  'Bookentry Crédito'),
('16',  'Bookentry Débito'),
('17',  'Desembolso Crédito (CCD)'),
('18',  'Desembolso (CCD) débito'),
('19',  'Crédito Pago negocio corporativo (CTP)'),
('20',  'Cheque'),
('21',  'Proyecto bancario'),
('22',  'Proyecto bancario certificado'),
('23',  'Cheque bancario de gerencia'),
('24',  'Nota cambiaria esperando aceptación'),
('25',  'Cheque certificado'),
('26',  'Cheque Local'),
('27',  'Débito Pago Negocio Corporativo (CTP)'),
('28',  'Crédito Negocio Intercambio Corporativo (CTX)'),
('29',  'Débito Negocio Intercambio Corporativo (CTX)'),
('30',  'Transferencia Crédito'),
('31',  'Transferencia Débito'),
('32',  'Desembolso Crédito plus (CCD+)'),
('33',  'Desembolso Débito plus (CCD+)'),
('34',  'Pago y depósito pre acordado (PPD)'),
('35',  'Desembolso Crédito (CCD)'),
('36',  'Desembolso Débito (CCD)'),
('37',  'Pago Negocio Corporativo Ahorros Crédito (CTP)'),
('38',  'Pago Negocio Corporativo Ahorros Débito (CTP)'),
('39',  'Crédito Intercambio Corporativo (CTX)'),
('40',  'Débito Intercambio Corporativo (CTX)'),
('41',  'Desembolso Crédito plus (CCD+)'),
('42',  'Consignación bancaria'),
('43',  'Desembolso Débito plus (CCD+)'),
('44',  'Nota cambiaria'),
('45',  'Transferencia Crédito Bancario'),
('46',  'Transferencia Débito Interbancario'),
('47',  'Transferencia Débito Bancaria'),
('48',  'Tarjeta Crédito'),
('49',  'Tarjeta Débito'),
('50',  'Postgiro'),
('51',  'Telex estándar bancario'),
('52',  'Pago comercial urgente'),
('53',  'Pago Tesorería Urgente'),
('60',  'Nota promisoria'),
('61',  'Nota promisoria firmada por el acreedor'),
('62',  'Nota promisoria firmada por el acreedor, avalada por el banco'),
('63',  'Nota promisoria firmada por el acreedor, avalada por un tercero'),
('64',  'Nota promisoria firmada por el banco'),
('65',  'Nota promisoria firmada por un banco avalada por otro banco'),
('66',  'Nota promisoria firmada'),
('67',  'Nota promisoria firmada por un tercero avalada por un banco'),
('70',  'Retiro de nota por el acreedor'),
('71',  'Bonos'),
('72',  'Vales'),
('74',  'Retiro de nota por el acreedor sobre un banco'),
('75',  'Retiro de nota por el acreedor, avalada por otro banco'),
('76',  'Retiro de nota por el acreedor, sobre un banco avalada por un tercero'),
('77',  'Retiro de una nota por el acreedor sobre un tercero'),
('78',  'Retiro de una nota por el acreedor sobre un tercero avalada por un banco'),
('91',  'Nota bancaria transferible'),
('92',  'Cheque local transferible'),
('93',  'Giro referenciado'),
('94',  'Giro urgente'),
('95',  'Giro formato abierto'),
('96',  'Método de pago solicitado no usado'),
('97',  'Clearing entre partners'),
('ZZZ', 'Otro')
ON CONFLICT DO NOTHING;


CREATE TABLE FACTURACION.TIPO_IMPUESTO (
    CODIGO_IMPUESTO   VARCHAR(10) PRIMARY KEY,
    NOMBRE            VARCHAR(80) NOT NULL,
    DESCRIPCION       VARCHAR(200) NOT NULL
);

INSERT INTO FACTURACION.TIPO_IMPUESTO (CODIGO_IMPUESTO, NOMBRE, DESCRIPCION) VALUES
('01', 'IVA',                    'Impuesto sobre la Ventas'),
('02', 'IC',                     'Impuesto al Consumo Departamental Nominal'),
('03', 'ICA',                    'Impuesto de Industria, Comercio y Aviso'),
('04', 'INC',                    'Impuesto Nacional al Consumo'),
('05', 'ReteIVA',                'Retención sobre el IVA'),
('06', 'ReteRenta',              'Retención sobre Renta'),
('07', 'ReteICA',                'Retención sobre el ICA'),
('08', 'IC Porcentual',          'Impuesto al Consumo Departamental Porcentual'),
('20', 'FtoHorticultura',        'Cuota de Fomento Hortifrutícola'),
('21', 'Timbre',                 'Impuesto de Timbre'),
('22', 'INC Bolsas',             'Impuesto Nacional al Consumo de Bolsa Plástica'),
('23', 'INCarbono',              'Impuesto Nacional del Carbono'),
('24', 'INCombustibles',         'Impuesto Nacional a los Combustibles'),
('25', 'Sobretasa Combustibles', 'Sobretasa a los combustibles'),
('26', 'Sordicom',               'Contribución minoristas (Combustibles)'),
('30', 'IC Datos',               'Impuesto al Consumo de Datos'),
('32', 'ICL',                    'Impuesto al Consumo de Licores'),
('33', 'INPP',                   'Impuesto nacional productos plásticos'),
('34', 'IBUA',                   'Impuesto a las bebidas ultraprocesadas azucaradas'),
('35', 'ICUI',                   'Impuesto a los productos comestibles ultraprocesados industrialmente y/o con alto contenido de azúcares añadidos, sodio o grasas saturadas'),
('36', 'ADV',                    'AD VALOREM'),
('ZZ', 'Otros',                  'Otros tributos, tasas, contribuciones, y similares')
ON CONFLICT DO NOTHING;


CREATE TABLE FACTURACION.TIPO_CONDICION_FISCAL (
    CODIGO_RESPONSABILIDAD VARCHAR(20) PRIMARY KEY,
    DESCRIPCION            VARCHAR(150) NOT NULL
);

INSERT INTO FACTURACION.TIPO_CONDICION_FISCAL (CODIGO_RESPONSABILIDAD, DESCRIPCION) VALUES
('O-13',    'Gran contribuyente'),
('O-15',    'Autorretenedor'),
('O-23',    'Agente de retención IVA'),
('O-47',    'Régimen simple de tributación'),
('R-99-PN', 'No aplica – Otros')
ON CONFLICT DO NOTHING;


CREATE TABLE FACTURACION.TIPO_ROL_TERCERO (
    ID_ROL_TERCERO    INT PRIMARY KEY,
    CODIGO_REFERENCIA VARCHAR(30) UNIQUE NOT NULL,
    DESCRIPCION       VARCHAR(100) NOT NULL
);

INSERT INTO FACTURACION.TIPO_ROL_TERCERO (ID_ROL_TERCERO, CODIGO_REFERENCIA, DESCRIPCION) VALUES
(1, 'EMISOR', 'Emisor / facturador'),
(2, 'ADQUIRIENTE', 'Adquiriente'),
(3, 'FABRICANTE_SOFTWARE', 'Fabricante de software'),
(4, 'PROVEEDOR_TECNOLOGICO', 'Proveedor tecnológico')
ON CONFLICT DO NOTHING;


-- Tipos de documento de identificación tributaria (Anexo 1.9 DIAN).
-- Códigos provienen del schemeName de cbc:CompanyID / sts:ProviderID.
CREATE TABLE FACTURACION.TIPO_DOCUMENTO_IDENTIDAD (
    ID_TIPO_DOCUMENTO   VARCHAR(10) PRIMARY KEY,
    CODIGO_REFERENCIA   VARCHAR(40) UNIQUE NOT NULL,
    DESCRIPCION         VARCHAR(200) NOT NULL
);

INSERT INTO FACTURACION.TIPO_DOCUMENTO_IDENTIDAD (ID_TIPO_DOCUMENTO, CODIGO_REFERENCIA, DESCRIPCION) VALUES
('10', 'CERTIFICADO_NACIDO_VIVO', 'Certificado de nacido vivo'),
('11', 'REGISTRO_CIVIL',          'Registro civil'),
('12', 'TARJETA_IDENTIDAD',       'Tarjeta de identidad'),
('13', 'CEDULA_CIUDADANIA',       'Cédula de ciudadanía'),
('21', 'TARJETA_EXTRANJERIA',     'Tarjeta de extranjería'),
('22', 'CEDULA_EXTRANJERIA',      'Cédula de extranjería'),
('31', 'NIT',                     'NIT'),
('41', 'PASAPORTE',               'Pasaporte'),
('42', 'DOCUMENTO_EXTRANJERO',    'Documento de identificación extranjero'),
('47', 'PEP',                     'PEP (Permiso Especial de Permanencia)'),
('48', 'PPT',                     'PPT (Permiso Protección Temporal)'),
('50', 'NIT_OTRO_PAIS',           'NIT de otro país'),
('91', 'NUIP',                    'NUIP')
ON CONFLICT DO NOTHING;

-- =========================
-- TIPO DE DOCUMENTO DIAN (Código de tipo de facturación electrónica)
-- =========================

CREATE TABLE FACTURACION.TIPO_DOCUMENTO_DIAN (
    CODIGO_TIPO_DOCUMENTO VARCHAR(10) PRIMARY KEY,
    NOMBRE                VARCHAR(120) NOT NULL,
    DESCRIPCION           VARCHAR(250) NULL,
    ADMITE_EVENTOS        BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO FACTURACION.TIPO_DOCUMENTO_DIAN (CODIGO_TIPO_DOCUMENTO, NOMBRE, DESCRIPCION, ADMITE_EVENTOS) VALUES
('01', 'Factura electrónica de Venta',                              NULL, TRUE),
('02', 'Factura electrónica de venta - exportación',                 NULL, TRUE),
('03', 'Instrumento electrónico de transmisión - tipo 03',           'Transcripción de la factura de talonario o papel', TRUE),
('04', 'Factura electrónica de Venta - tipo 04',                     NULL, TRUE),
('91', 'Nota Crédito',                                               'Exclusivo en referencias a documentos (elementos DocumentReference)', FALSE),
('92', 'Nota Débito',                                                NULL, FALSE),
('96', 'Eventos (ApplicationResponse)',                              NULL, FALSE)
ON CONFLICT DO NOTHING;

-- =========================
-- CORREO DE ENTRADA
-- =========================

CREATE TABLE FACTURACION.CORREO_ENTRANTE (
    CORREO_ID       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    MESSAGE_ID      VARCHAR(255) NOT NULL UNIQUE,
    REMITENTE       VARCHAR(320) NOT NULL,
    ASUNTO          VARCHAR(500),
    PROCESADO       BOOLEAN NOT NULL DEFAULT FALSE,
    FECHA_DETECCION TIMESTAMPTZ NOT NULL,
    FECHA_ENVIO     TIMESTAMPTZ NULL,
    CUERPO_TEXTO    TEXT NULL,
    CUERPO_HTML     TEXT NULL,
    CONTIENE_ADJUNTOS BOOLEAN NOT NULL DEFAULT FALSE,
    ID_ORIGEN       INT NULL,
    OBSERVACION     VARCHAR(255) NULL
);

-- =========================
-- ADJUNTOS DEL CORREO
-- =========================

CREATE TABLE FACTURACION.ADJUNTOS_CORREO (
    ADJUNTO_ID         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    CORREO_ID          BIGINT NOT NULL REFERENCES FACTURACION.CORREO_ENTRANTE(CORREO_ID),
    ADJUNTO_PADRE_ID   BIGINT NULL REFERENCES FACTURACION.ADJUNTOS_CORREO(ADJUNTO_ID),
    NOMBRE_ARCHIVO     VARCHAR(255) NOT NULL,
    ID_TIPO_ARCHIVO    INT NULL,
    URI_ALMACENAMIENTO VARCHAR(255) NOT NULL,
    SHA256             VARCHAR(64) NOT NULL,
    ARCHIVO_SEGURO     BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT UQ_ADJUNTO_CORREO_NOMBRE UNIQUE (CORREO_ID, NOMBRE_ARCHIVO)
);

-- =========================
-- TRAZABILIDAD / ORQUESTACIÓN
-- =========================

CREATE TABLE FACTURACION.EVENTO_INGESTA (
    ADJUNTO_ID          BIGINT PRIMARY KEY REFERENCES FACTURACION.ADJUNTOS_CORREO(ADJUNTO_ID),
    FECHA_CREACION      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FECHA_ACTUALIZACION TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ID_ESTADO           INT NOT NULL REFERENCES FACTURACION.TIPO_ESTADO_PROCESO(ID_ESTADO_PROCESO),
    INTENTOS            BIGINT NOT NULL DEFAULT 0,
    VERSION_MOTOR       VARCHAR(10) NULL
);

CREATE TABLE FACTURACION.PROCESO_INGESTA (
    ID_PROCESO_INGESTA BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ADJUNTO_ID         BIGINT NOT NULL REFERENCES FACTURACION.ADJUNTOS_CORREO(ADJUNTO_ID),
    ID_PROCESO         INT NOT NULL REFERENCES FACTURACION.TIPO_PROCESO(ID_TIPO_PROCESO),
    ID_ESTADO          INT NOT NULL REFERENCES FACTURACION.TIPO_ESTADO_PROCESO(ID_ESTADO_PROCESO),
    ID_ERROR           INT NULL REFERENCES FACTURACION.TIPO_ERROR(ID_TIPO_ERROR),
    FECHA_INICIO       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FECHA_FIN          TIMESTAMPTZ NULL,
    OBSERVACION        VARCHAR(255) NOT NULL
);

-- =========================
-- TERCEROS (req_02: Emisor, req_03: Adquiriente)
-- =========================

CREATE TABLE FACTURACION.TERCERO (
    ID_TERCERO         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ID_ROL_TERCERO     INT NOT NULL REFERENCES FACTURACION.TIPO_ROL_TERCERO(ID_ROL_TERCERO),
    NUMERO_DOCUMENTO   VARCHAR(20) NOT NULL,
    DIGITO_VERIFICADOR VARCHAR(2) NULL,
    ID_TIPO_DOCUMENTO  VARCHAR(2) NULL REFERENCES FACTURACION.TIPO_DOCUMENTO_IDENTIDAD(ID_TIPO_DOCUMENTO),
    CORREO_CONTACTO    VARCHAR(320) NULL,
    TELEFONO_CONTACTO  VARCHAR(50) NULL,
    CODIGO_PAIS        CHAR(2) NOT NULL DEFAULT 'CO',
    FECHA_CREACION     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT UQ_TERCERO_DOCUMENTO_ROL UNIQUE (ID_ROL_TERCERO, NUMERO_DOCUMENTO)
);

CREATE INDEX IX_TERCERO_TIPO_DOCUMENTO ON FACTURACION.TERCERO (ID_TIPO_DOCUMENTO);

-- =========================
-- NUMERACIÓN AUTORIZADA DIAN (req_04)
-- =========================

CREATE TABLE FACTURACION.AUTORIZACION_NUMERACION_DIAN (
    ID_AUTORIZACION       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ID_TERCERO_EMISOR     BIGINT NOT NULL REFERENCES FACTURACION.TERCERO(ID_TERCERO),
    PREFIJO_FACTURACION   VARCHAR(20) NOT NULL DEFAULT '',
    NUMERO_RESOLUCION     VARCHAR(50) NOT NULL,
    RANGO_DESDE           BIGINT NOT NULL,
    RANGO_HASTA           BIGINT NOT NULL,
    FECHA_AUTORIZACION    DATE NOT NULL,
    FECHA_INICIO_VIGENCIA DATE NOT NULL,
    FECHA_FIN_VIGENCIA    DATE NOT NULL,
    CODIGO_TECNICO        VARCHAR(120) NULL,
    FECHA_CREACION        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT CK_RANGO_NUMERACION CHECK (RANGO_HASTA >= RANGO_DESDE),
    CONSTRAINT CK_VIGENCIA CHECK (FECHA_FIN_VIGENCIA >= FECHA_INICIO_VIGENCIA)
);

-- =========================
-- FACTURA (req_01, 04, 05, 09, 14, 15, 16)
-- =========================

CREATE TABLE FACTURACION.FACTURA (
    ID_FACTURA              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    CUFE                    VARCHAR(100) NOT NULL,
    DENOMINACION            VARCHAR(50) NULL,
    CODIGO_TIPO_DOCUMENTO_DIAN VARCHAR(10) NULL REFERENCES FACTURACION.TIPO_DOCUMENTO_DIAN(CODIGO_TIPO_DOCUMENTO),
    PREFIJO_FACTURACION     VARCHAR(20) NOT NULL DEFAULT '',
    NUMERO_FACTURA          VARCHAR(50) NOT NULL,
    ID_TERCERO_EMISOR       BIGINT NOT NULL REFERENCES FACTURACION.TERCERO(ID_TERCERO),
    RAZON_SOCIAL_EMISOR     VARCHAR(300) NULL,
    ID_TERCERO_ADQUIRIENTE  BIGINT NOT NULL REFERENCES FACTURACION.TERCERO(ID_TERCERO),
    RAZON_SOCIAL_ADQUIRIENTE VARCHAR(300) NULL,
    ID_AUTORIZACION         BIGINT NULL REFERENCES FACTURACION.AUTORIZACION_NUMERACION_DIAN(ID_AUTORIZACION),
    FECHA_GENERACION        TIMESTAMPTZ NOT NULL,
    FECHA_EXPEDICION        TIMESTAMPTZ NULL,
    FECHA_VENCIMIENTO       DATE NULL,
    CODIGO_MONEDA           CHAR(3) NOT NULL DEFAULT 'COP',
    VALOR_TOTAL             NUMERIC(18,2) NULL CHECK (VALOR_TOTAL IS NULL OR VALOR_TOTAL >= 0),
    HASH_FIRMA_DIGITAL      VARCHAR(128) NULL,
    CONTENIDO_QR            TEXT NULL,
    ADJUNTO_ID              BIGINT NULL REFERENCES FACTURACION.ADJUNTOS_CORREO(ADJUNTO_ID),
    ID_ESTADO_PROCESO       INT NOT NULL REFERENCES FACTURACION.TIPO_ESTADO_PROCESO(ID_ESTADO_PROCESO),
    FECHA_CREACION          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FECHA_ACTUALIZACION     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT UQ_FACTURA_CUFE UNIQUE (CUFE),
    CONSTRAINT UQ_FACTURA_EMISOR_NUMERO UNIQUE (ID_TERCERO_EMISOR, PREFIJO_FACTURACION, NUMERO_FACTURA)
);

CREATE INDEX IX_FACTURA_ADQUIRIENTE ON FACTURACION.FACTURA (ID_TERCERO_ADQUIRIENTE);
CREATE INDEX IX_FACTURA_FECHA_EXPEDICION ON FACTURACION.FACTURA (FECHA_EXPEDICION);

-- =========================
-- CONDICIONES FISCALES DE LA FACTURA (req_12)
-- Múltiples registros por factura
-- =========================

CREATE TABLE FACTURACION.CONDICION_FISCAL_FACTURA (
    ID_FACTURA               BIGINT NOT NULL REFERENCES FACTURACION.FACTURA(ID_FACTURA),
    CODIGO_RESPONSABILIDAD   VARCHAR(20) NOT NULL REFERENCES FACTURACION.TIPO_CONDICION_FISCAL(CODIGO_RESPONSABILIDAD),
    ES_APLICABLE             BOOLEAN NOT NULL DEFAULT TRUE,
    NOTAS_ADICIONALES        VARCHAR(300) NULL,
    PRIMARY KEY (ID_FACTURA, CODIGO_RESPONSABILIDAD)
);

-- =========================
-- FORMA Y MEDIO DE PAGO (req_10, req_11)
-- Un registro único por factura
-- =========================

CREATE TABLE FACTURACION.PAGO_FACTURA (
    ID_FACTURA          BIGINT PRIMARY KEY REFERENCES FACTURACION.FACTURA(ID_FACTURA),
    CODIGO_FORMA_PAGO   VARCHAR(10) NOT NULL REFERENCES FACTURACION.TIPO_FORMA_PAGO(CODIGO_FORMA_PAGO),
    CODIGO_MEDIO_PAGO   VARCHAR(10) NULL REFERENCES FACTURACION.TIPO_MEDIO_PAGO(CODIGO_MEDIO_PAGO),
    PLAZO_EN_DIAS       INTEGER NULL CHECK (PLAZO_EN_DIAS >= 0),
    NOTAS_ADICIONALES   VARCHAR(300) NULL,
    CONSTRAINT CK_MEDIO_SI_CONTADO CHECK (
        (CODIGO_FORMA_PAGO = '1' AND CODIGO_MEDIO_PAGO IS NOT NULL)
        OR
        (CODIGO_FORMA_PAGO = '2')
    )
);

-- =========================
-- DETALLE DE FACTURA / LÍNEAS (req_08)
-- Múltiples registros por factura
-- =========================

CREATE TABLE FACTURACION.DETALLE_FACTURA (
    ID_DETALLE        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ID_FACTURA        BIGINT NOT NULL REFERENCES FACTURACION.FACTURA(ID_FACTURA),
    NUMERO_LINEA      INTEGER NOT NULL,
    CODIGO_ITEM       VARCHAR(80) NULL,
    DESCRIPCION_ITEM  TEXT NOT NULL,
    CANTIDAD          NUMERIC(18,6) NOT NULL CHECK (CANTIDAD > 0),
    UNIDAD_DE_MEDIDA  VARCHAR(30) NULL,
    VALOR_UNITARIO    NUMERIC(18,2) NOT NULL CHECK (VALOR_UNITARIO >= 0),
    VALOR_TOTAL_LINEA NUMERIC(18,2) NOT NULL CHECK (VALOR_TOTAL_LINEA >= 0),
    CODIGO_INTERNO    VARCHAR(80) NULL,
    FECHA_CREACION    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT UQ_FACTURA_LINEA UNIQUE (ID_FACTURA, NUMERO_LINEA)
);



-- =========================
-- IMPUESTOS A NIVEL FACTURA (req_13)
-- Múltiples registros por factura
-- =========================

CREATE TABLE FACTURACION.IMPUESTO_FACTURA (
    ID_FACTURA        BIGINT NOT NULL REFERENCES FACTURACION.FACTURA(ID_FACTURA),
    CODIGO_IMPUESTO   VARCHAR(10) NOT NULL REFERENCES FACTURACION.TIPO_IMPUESTO(CODIGO_IMPUESTO),
    TARIFA            NUMERIC(9,4) NOT NULL CHECK (TARIFA >= 0),
    BASE_GRAVABLE     NUMERIC(18,2) NOT NULL CHECK (BASE_GRAVABLE >= 0),
    VALOR_IMPUESTO    NUMERIC(18,2) NOT NULL CHECK (VALOR_IMPUESTO >= 0),
    PRIMARY KEY (ID_FACTURA, CODIGO_IMPUESTO, TARIFA)
);



-- =========================
-- PROVEEDORES TECNOLÓGICOS AUTORIZADOS DIAN (req_18)
-- Registro oficial de proveedores tecnológicos habilitados
-- =========================

CREATE TABLE FACTURACION.PROVEEDOR_TECNOLOGICO (
    NIT_PROVEEDOR     VARCHAR(20) PRIMARY KEY,
    RAZON_SOCIAL      VARCHAR(300) NOT NULL,
    CODIGO_PT         VARCHAR(10) NOT NULL UNIQUE
);

INSERT INTO FACTURACION.PROVEEDOR_TECNOLOGICO (NIT_PROVEEDOR, RAZON_SOCIAL, CODIGO_PT) VALUES
('901020203', 'ACEPTA S A S',                                                            '030'),
('830099008', 'ALIADDO SAS',                                                              '045'),
('901037591', 'APG CONSULTING COLOMBIA S.A.S.',                                           '074'),
('900464969', 'ASISTENCIA MOVIL S.A.S.',                                                  '047'),
('900965992', 'ATEB COLOMBIA S A S',                                                      '011'),
('900372288', 'AVANCES SOFTWARE S.A.S.',                                                  '065'),
('900297700', 'AVANCYS S.A.S.',                                                           '090'),
('901137226', 'BCN CONSULTORES COLOMBIA S.A.S.',                                          '005'),
('901066054', 'BILLY FACTUREX SAS',                                                       '013'),
('830005677', 'BIT CONSULTING S.A.S',                                                     '010'),
('900011395', 'BPM CONSULTING LTDA',                                                      '061'),
('901121154', 'BRITEK TRIBUTO S.A.S',                                                     '071'),
('900665411', 'BYTHEWAVE S.A.S',                                                          '024'),
('890930534', 'CADENA S.A.',                                                              '021'),
('800096812', 'CARVAJAL SOLUCIONES DE COMUNICACION S.A.S.',                               '094'),
('890321151', 'CARVAJAL TECNOLOGIA Y SERVICIOS S.A.S.',                                   '027'),
('805012299', 'CODESA',                                                                   '075'),
('830057860', 'COMERCIO ELECTRONICO EN INTERNET S.A. CENET S.A.',                         '017'),
('800150249', 'COMPUNET S.A',                                                             '060'),
('900646251', 'COMPUTEC OUTSOURCING S.A.S',                                               '019'),
('901180226', 'CONEXUSIT SAS',                                                            '070'),
('900457033', 'CONTROLTECH SERVICES S.A.S.',                                              '077'),
('900949812', 'DATA EXPRESS LATINOAMERICA S.A.S.',                                        '046'),
('901223648', 'DATAICO S.A.S',                                                            '089'),
('900918004', 'DBNET COLOMBIA SAS',                                                       '056'),
('860028581', 'DELCOP COLOMBIA SAS',                                                      '032'),
('860028580', 'DISPAPELES S.A.S',                                                         '007'),
('800088155', 'DOMINA ENTREGA TOTAL S.A.S',                                               '069'),
('805018674', 'ECOM S.A.S.',                                                              '054'),
('900680995', 'EDICOM S.A.S',                                                             '033'),
('900957899', 'EDX COLOMBIA S A S',                                                       '050'),
('901081604', 'EKOMERCIO ELECTRÓNICO SAS',                                                '036'),
('900984424', 'ESDINAMICO SAS',                                                           '034'),
('900306823', 'F Y M TECHNOLOGY S.A.S.',                                                  '006'),
('900273836', 'F1 TOP POINT LTDA',                                                        '073'),
('900896085', 'FACELE S A S',                                                             '086'),
('900875062', 'FACTURA1 S.A.S.',                                                          '003'),
('901187615', 'FACTURAXION COLOMBIA SAS',                                                 '066'),
('900399741', 'FACTURE S.A.S',                                                            '004'),
('890901481', 'FEDERACION NACIONAL DE COMERCIANTES FENALCO SECCIONAL ANTIOQUIA',          '058'),
('900204272', 'GESTION DE SEGURIDAD ELECTRONICA S.A',                                     '088'),
('900730535', 'GESTION FRANCA S.A.S',                                                     '068'),
('900133732', 'GLOBALTEK DEVELOPMENT S A',                                                '041'),
('900711544', 'GRUPO FLA SAS',                                                            '093'),
('901014886', 'GURUSOFT S.A.S',                                                           '040'),
('811021438', 'HERRAMIENTAS DE GESTION INFORMATICA S.A.S',                                '028'),
('890941901', 'ILIMITADA INGENIERIA DE SISTEMAS S.A.S.',                                  '076'),
('901183470', 'IMAGINE INTEGRATORS S.A.S.',                                               '078'),
('900556261', 'INDIGO TECHNOLOGIES S.A.S.',                                               '095'),
('900123011', 'INFORMATIX DE COLOMBIA LTDA.',                                             '072'),
('900738794', 'INNAPSIS APPFLOW SAS',                                                     '044'),
('860502327', 'JAIME TORRES C Y CIA S A',                                                 '022'),
('860515402', 'LEXCO S.A.',                                                               '048'),
('800255858', 'MAKRO SOFT LTDA',                                                          '063'),
('900176162', 'NEIA S.A.S',                                                               '081'),
('901285179', 'NODEXUM',                                                                  '084'),
('830074854', 'NOVA CORP SAS',                                                            '043'),
('900521653', 'NUBOX COLOMBIA S A S',                                                     '039'),
('830003840', 'OASISCOM SAS',                                                             '052'),
('900032774', 'OLIMPIA MANAGEMENT S A',                                                   '038'),
('830135010', 'OPENTECNOLOGIA S.A.',                                                      '014'),
('900749874', 'PAPERLESS S.A.S.',                                                         '053'),
('800101428', 'PARADIGMA S A S',                                                          '020'),
('830502641', 'PHIDIAS S.A.S',                                                            '083'),
('900013664', 'PLATAFORMA COLOMBIA S.A.S.',                                               '042'),
('890923937', 'PRODUCTORA DE SOFTWARE S.A.S',                                             '029'),
('830096620', 'PROFESIONALES EN TRANSACCIONES ELECTRONICAS S.A. PTESA',                   '009'),
('900299474', 'Q10 SOLUCIONES S.A.S.',                                                    '082'),
('800026212', 'RICOH COLOMBIA S.A.',                                                      '067'),
('900606963', 'SAPHETY - TRANSACCIONES ELECTRONICAS S A S',                               '025'),
('900035507', 'SAVE COLOMBIA COMPANY S.A.S.',                                             '037'),
('901356496', 'SEDISOLUTIONS SAS',                                                        '091'),
('900508908', 'SIGNATURE SOUTH CONSULTING COLOMBIA S.A.S',                                '051'),
('830048145', 'SIIGO S.A',                                                                '008'),
('901098244', 'SIMBA SOFTWARE SAS',                                                       '018'),
('890319193', 'SISTEMAS DE INFORMACION EMPRESARIAL S.A',                                  '015'),
('830084433', 'SOCIEDAD CAMERAL DE CERTIFICACION DIGITAL CERTICAMARA S A',                '026'),
('900379787', 'SOCIEDAD DE EXPLOTACION DE REDES ELECTRONICAS Y SERVICIOS DE COLOMBIA S.A.S.', '064'),
('900364710', 'SOFTWARE COLOMBIA SERVICIOS INFORMATICOS SAS',                             '031'),
('900395252', 'SOFTWARE ESTRATÉGICO S.A.S',                                               '062'),
('900559088', 'SOLUCIONES ALEGRA S.A.S',                                                  '085'),
('901361537', 'SOLUCIONES EMPRESARIALES EN LA NUBE S.A.S. SENSAS',                        '092'),
('800157786', 'SOLUCIONES INTEGRALES DE OFICINA S.A.S EN REORGANIZACION',                 '087'),
('900083058', 'SYSCAFE S.A.S',                                                            '079'),
('830020470', 'TELEINTE S A S',                                                           '055'),
('900390126', 'THE FACTORY HKA COLOMBIA S.A.S.',                                          '016'),
('900423948', 'TN COLOMBIA S.A.S',                                                        '059'),
('800182856', 'TNS SAS',                                                                  '057'),
('900032159', 'TRANSFIRIENDO S.A.',                                                       '023'),
('901034990', 'VISUALSOFT COLOMBIA SAS',                                                  '080'),
('811026198', 'VSDC S.A.S.',                                                              '012'),
('900534356', 'WORLD OFFICE COLOMBIA S.A.S',                                              '035')
ON CONFLICT DO NOTHING;

-- =========================
-- FABRICANTE DE SOFTWARE (req_18)
-- =========================

CREATE TABLE FACTURACION.FABRICANTE_SOFTWARE (
    ID_FABRICANTE_SOFTWARE BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    NUMERO_DOCUMENTO       VARCHAR(20) NOT NULL,
    RAZON_SOCIAL           VARCHAR(300) NOT NULL,
    FECHA_CREACION         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT UQ_SOFTWARE_FABRICANTE UNIQUE (NUMERO_DOCUMENTO)
);

-- =========================
-- PRODUCTO DE SOFTWARE (req_18)
-- =========================

CREATE TABLE FACTURACION.PRODUCTO_SOFTWARE (
    ID_PRODUCTO_SOFTWARE   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ID_FABRICANTE_SOFTWARE BIGINT NOT NULL REFERENCES FACTURACION.FABRICANTE_SOFTWARE(ID_FABRICANTE_SOFTWARE),
    NOMBRE_SOFTWARE        VARCHAR(250) NOT NULL,
    VERSION_SOFTWARE       VARCHAR(80) NULL,
    FECHA_CREACION         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UQ_SOFTWARE_PRODUCTO ON FACTURACION.PRODUCTO_SOFTWARE (ID_FABRICANTE_SOFTWARE, NOMBRE_SOFTWARE, COALESCE(VERSION_SOFTWARE, ''));

-- =========================
-- SOFTWARE ↔ FACTURA (req_18)
-- Un registro único por factura
-- =========================

CREATE TABLE FACTURACION.SOFTWARE_FACTURA (
    ID_FACTURA               BIGINT PRIMARY KEY REFERENCES FACTURACION.FACTURA(ID_FACTURA),
    ID_PRODUCTO_SOFTWARE     BIGINT NOT NULL REFERENCES FACTURACION.PRODUCTO_SOFTWARE(ID_PRODUCTO_SOFTWARE),
    NIT_PROVEEDOR_TECNOLOGICO VARCHAR(20) NULL REFERENCES FACTURACION.PROVEEDOR_TECNOLOGICO(NIT_PROVEEDOR),
    NOTAS_ADICIONALES        VARCHAR(300) NULL
);

-- =========================
-- EVENTOS DIAN DE LA FACTURA
-- Múltiples eventos por factura (Validación, Acuse, Recibo, Aceptación, Reclamo)
-- =========================

CREATE TABLE FACTURACION.EVENTO_DIAN_FACTURA (
    ID_EVENTO_FACTURA BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ID_FACTURA        BIGINT NOT NULL REFERENCES FACTURACION.FACTURA(ID_FACTURA),
    CODIGO_EVENTO     VARCHAR(10) NOT NULL REFERENCES FACTURACION.TIPO_EVENTO_DIAN(CODIGO_EVENTO),
    FECHA_EVENTO      TIMESTAMPTZ NULL,
    DESCRIPCION       VARCHAR(500) NULL,
    ID_RASTREO        VARCHAR(100) NULL,
    FECHA_CREACION    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================
-- ALERTAS DEL SISTEMA
-- =========================

CREATE TABLE FACTURACION.TIPO_PRIORIDAD_ALERTA (
    CODIGO_PRIORIDAD  VARCHAR(10) PRIMARY KEY,
    DESCRIPCION       VARCHAR(100) NOT NULL,
    ENVIA_CORREO      BOOLEAN NOT NULL DEFAULT FALSE,
    COLOR_UI          VARCHAR(10) NOT NULL DEFAULT '#6B7280',
    ORDEN             INT NOT NULL DEFAULT 99
);

INSERT INTO FACTURACION.TIPO_PRIORIDAD_ALERTA (CODIGO_PRIORIDAD, DESCRIPCION, ENVIA_CORREO, COLOR_UI, ORDEN) VALUES
('CRITICA', 'Requiere acción inmediata',         TRUE,  '#EF4444', 1),
('ALTA',    'Requiere atención pronto',           FALSE, '#F59E0B', 2),
('MEDIA',   'Informativa con acción sugerida',    FALSE, '#3B82F6', 3),
('BAJA',    'Solo informativa',                   FALSE, '#6B7280', 4)
ON CONFLICT DO NOTHING;


CREATE TABLE FACTURACION.TIPO_ALERTA (
    CODIGO_TIPO_ALERTA    VARCHAR(30) PRIMARY KEY,
    DESCRIPCION           VARCHAR(200) NOT NULL,
    CODIGO_PRIORIDAD_DEF  VARCHAR(10) NOT NULL REFERENCES FACTURACION.TIPO_PRIORIDAD_ALERTA(CODIGO_PRIORIDAD)
);

INSERT INTO FACTURACION.TIPO_ALERTA (CODIGO_TIPO_ALERTA, DESCRIPCION, CODIGO_PRIORIDAD_DEF) VALUES
('MALWARE_DETECTADO',    'Archivo infectado con virus o malware',                   'CRITICA'),
('BOT_INACTIVO',         'El bot de extracción dejó de funcionar',                  'CRITICA'),
('CONEXION_FALLIDA',     'Fallo de conexión a servicio externo (IMAP, BD, S3)',     'CRITICA'),
('FACTURA_RECHAZADA',    'Factura no pasó las validaciones DIAN',                   'ALTA'),
('VENCIMIENTO_PROXIMO',  'Factura próxima a vencer sin evento de aceptación DIAN',  'ALTA'),
('MAX_REINTENTOS',       'Factura agotó el máximo de reintentos de procesamiento',  'ALTA'),
('ZIP_INCOMPLETO',       'ZIP sin pares XML+PDF válidos',                           'MEDIA'),
('PDF_FALTANTE',         'Factura procesada sin PDF adjunto',                       'MEDIA'),
('CORREO_SIN_ADJUNTOS',  'Correo de facturación sin adjuntos válidos',              'MEDIA'),
('VALIDACION_PARCIAL',   'Factura registrada con algunas validaciones fallidas',    'BAJA'),
('DUPLICADO_DETECTADO',  'Factura duplicada detectada y omitida',                   'BAJA')
ON CONFLICT DO NOTHING;


CREATE TABLE FACTURACION.ALERTA (
    ID_ALERTA         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    CODIGO_TIPO_ALERTA VARCHAR(30) NOT NULL REFERENCES FACTURACION.TIPO_ALERTA(CODIGO_TIPO_ALERTA),
    CODIGO_PRIORIDAD  VARCHAR(10) NOT NULL REFERENCES FACTURACION.TIPO_PRIORIDAD_ALERTA(CODIGO_PRIORIDAD),
    TITULO            VARCHAR(200) NOT NULL,
    MENSAJE           TEXT NOT NULL,
    CONTEXTO          JSONB NULL,
    LEIDA             BOOLEAN NOT NULL DEFAULT FALSE,
    RESUELTA          BOOLEAN NOT NULL DEFAULT FALSE,
    CORREO_ENVIADO    BOOLEAN NOT NULL DEFAULT FALSE,
    CORREO_ID         BIGINT NULL REFERENCES FACTURACION.CORREO_ENTRANTE(CORREO_ID),
    ADJUNTO_ID        BIGINT NULL REFERENCES FACTURACION.ADJUNTOS_CORREO(ADJUNTO_ID),
    FACTURA_ID        BIGINT NULL REFERENCES FACTURACION.FACTURA(ID_FACTURA),
    FECHA_CREACION    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FECHA_RESOLUCION  TIMESTAMPTZ NULL
);

-- =========================
-- ÍNDICES DE APOYO
-- =========================

CREATE INDEX IX_CORREO_FECHA ON FACTURACION.CORREO_ENTRANTE (FECHA_DETECCION);
CREATE INDEX IX_ADJUNTO_CORREO ON FACTURACION.ADJUNTOS_CORREO (CORREO_ID);
CREATE INDEX IX_ADJUNTO_SHA256 ON FACTURACION.ADJUNTOS_CORREO (SHA256);
CREATE INDEX IX_PROCESO_ESTADO ON FACTURACION.PROCESO_INGESTA (ID_ESTADO);
CREATE INDEX IX_PROCESO_ADJUNTO ON FACTURACION.PROCESO_INGESTA (ADJUNTO_ID);
CREATE INDEX IX_EVENTO_DIAN_FACTURA_RECIENTE ON FACTURACION.EVENTO_DIAN_FACTURA (ID_FACTURA, FECHA_CREACION DESC);

-- Índices de alertas
CREATE INDEX IX_ALERTA_PRIORIDAD ON FACTURACION.ALERTA (CODIGO_PRIORIDAD, FECHA_CREACION DESC);
CREATE INDEX IX_ALERTA_NO_LEIDA ON FACTURACION.ALERTA (LEIDA, FECHA_CREACION DESC) WHERE LEIDA = FALSE;
CREATE INDEX IX_ALERTA_TIPO ON FACTURACION.ALERTA (CODIGO_TIPO_ALERTA, FECHA_CREACION DESC);
CREATE INDEX IX_ALERTA_FACTURA ON FACTURACION.ALERTA (FACTURA_ID) WHERE FACTURA_ID IS NOT NULL;