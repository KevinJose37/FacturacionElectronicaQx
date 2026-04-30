# Integración de Procesamiento y Seguridad de Facturas

Este documento muestra cómo se debe integrar la nueva lógica de extracción, validación de seguridad (magic numbers y CRC) y carga a S3 (`procesar_y_subir_factura`) dentro del ciclo normal de ingesta de correos electrónicos.

## Punto de Integración

La función ideal para integrar esto es `_procesar_correo()` que se encuentra en `core/email_listener.py`. Esta función se encarga de descargar el archivo ZIP del correo; por lo tanto, inmediatamente después de obtener la ruta local del ZIP descargado, podemos iniciar nuestra validación de seguridad y carga.

### Ejemplo de Integración en `email_listener.py`

Debes agregar el import de la función en la parte superior del archivo:

```python
from core.factura_processor import procesar_y_subir_factura
```

Luego, modifica la función `_procesar_correo` para insertar la llamada justo después de la descarga, y antes o durante la publicación en la cola de mensajes:

```python
    def _procesar_correo(self, conn: imaplib.IMAP4_SSL, uid: bytes) -> bool:
        """Procesa un correo individual.

        Args:
            conn: Conexión IMAP.
            uid: UID del correo.

        Returns:
            bool: True si procesó correctamente.
        """
        status, data = conn.uid("fetch", uid, "(RFC822)")
        if status != "OK" or not data: return False

        raw = data[0][1]
        if not self._tiene_adjunto_zip(raw): return False

        msg = _email.message_from_bytes(raw)
        parsed = self._parser.parsear(msg.get("Subject", ""))
        
        # 1. Descarga el archivo ZIP localmente
        ruta = self._attachment_handler.descargar_zip(msg, parsed)

        if not ruta: return False

        # =====================================================================
        # 2. NUEVA LÓGICA: Procesar, Validar Seguridad y Subir a S3
        # =====================================================================
        exito_procesamiento = procesar_y_subir_factura(ruta)
        
        if not exito_procesamiento:
            # Si el archivo era malware, corrupto o falló AWS, marcamos error.
            logger.error(f"Fallo de seguridad o carga a S3 para el ZIP: {ruta}")
            return False
            
        # =====================================================================
        # 3. Publicación en Cola (Opcional: puedes incluir el estatus de S3)
        # =====================================================================
        exito = self._publisher.publish({
            "email_uid": uid.decode(),
            "parsed_subject": parsed,
            "attachment_path": str(ruta),
            "s3_uploaded": True  # Indicador para el siguiente paso del pipeline
        })

        if exito:
            conn.uid("store", uid, "+FLAGS", "\\Seen")
        return exito
```

## Beneficios de esta aproximación

1. **Fallo Rápido (Fail-Fast)**: Si el ZIP contiene malware (es decir, el PDF o XML es en realidad un `.exe`), la función `procesar_y_subir_factura` lo detecta mediante la firma binaria y retorna `False`. El correo no se marca como `\Seen` y la factura maliciosa no ingresa a la cola de procesamiento del sistema.
2. **Eficiencia en la Nube**: El archivo se sube a S3 inmediatamente después de llegar, antes de encolar el mensaje. Los *workers* que consuman el mensaje de la cola (`publisher.publish`) podrán acceder directamente a los archivos limpios en AWS S3 sin sobrecargar el servidor local.
