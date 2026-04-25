# Ejemplos de Flujo: Procesamiento y Subida de Facturas

A continuación se detalla cómo es el recorrido lógico interno de `procesar_y_subir_factura()` ilustrando un escenario donde todo sale bien, y otros donde el sistema detiene el proceso de manera preventiva.

## ✅ Ejemplo 1: Flujo Exitoso (Factura Legítima)

**Contexto**: El proveedor envía un correo con el adjunto `factura_123.zip`. Este ZIP contiene un XML de la DIAN y la representación gráfica en PDF.

1.  **Entrada**: Se llama a `procesar_y_subir_factura("downloads/factura_123.zip")`.
2.  **Validación ZIP**:
    *   **Identidad**: El sistema lee los primeros 100 bytes del archivo. Determina que el *magic number* es `b'PK\x03\x04'` (firma estándar de un ZIP). -> *Pasa*.
    *   **Corrupción**: Se hace un `testzip()`. El CRC interno es consistente con el tamaño de los archivos declarados. -> *Pasa*.
3.  **Desempaquetado**: Se crea una carpeta temporal en la memoria RAM del servidor. Se extrae `factura_123.xml` y `factura_123.pdf`.
4.  **Validación de Contenidos (Seguridad)**:
    *   **XML**: Abre `factura_123.xml`, ignora espacios en blanco y detecta que el primer carácter es `<`. Es un XML válido. -> *Pasa*.
    *   **PDF**: Abre `factura_123.pdf`, verifica que empieza con `%PDF-`. Es un PDF real. -> *Pasa*.
5.  **Subida a la Nube**: 
    *   Sube `factura_123.zip` a AWS S3 (con la llave `facturas/factura_123.zip`).
    *   Sube `factura_123.xml` y `factura_123.pdf` (con las llaves `facturas_descomprimidas/factura_123/...`).
    *   AWS responde positivamente.
6.  **Retorno**: Se elimina la carpeta temporal automáticamente y la función retorna `True`. (En `_procesar_correo` esto permitirá que el mensaje pase a la cola).

---

## ❌ Ejemplo 2: Flujo No Exitoso (Malware disfrazado de PDF)

**Contexto**: Un atacante envía un correo engañoso. Adjunta un archivo `Factura_URGENTE.zip`. Dentro de ese ZIP viene un troyano ejecutable para Windows llamado `factura.pdf` (en realidad es un `.exe` renombrado) para engañar al sistema.

1.  **Entrada**: Se llama a `procesar_y_subir_factura("downloads/Factura_URGENTE.zip")`.
2.  **Validación ZIP**: El atacante comprimió el archivo con WinRAR de forma normal. El *magic number* y el CRC son válidos. -> *Pasa*.
3.  **Desempaquetado**: Se extrae `factura.pdf` a la carpeta temporal aislada.
4.  **Validación de Contenidos (Seguridad)**:
    *   **PDF**: El sistema abre el archivo `factura.pdf` y lee los primeros bytes. Descubre que empiezan con `MZ` (firma de los ejecutables de Windows), no con `%PDF-`.
    *   **¡ALERTA!**: `validar_identidad_archivo()` detecta el engaño y retorna `False`. Se marca `malware_detectado = True`.
    *   Se hace un *Break* inmediato. No se revisan más archivos.
5.  **Subida a la Nube**: La subida a S3 **se cancela** por completo. (Evita almacenar o propagar el troyano).
6.  **Retorno**: La carpeta temporal (con el ejecutable peligroso) es destruida por completo. Retorna `False`. 
    *   *Consecuencia:* En el script de email, esto hará que el correo sospechoso **no** sea puesto en la cola ni marcado como `\Seen` de forma exitosa, logrando fallar de manera segura (*fail-fast*).

---

## ❌ Ejemplo 3: Flujo No Exitoso (Archivo Incompleto/Corrupto)

**Contexto**: El proveedor envía un ZIP legítimo, pero hubo un micro-corte de red mientras el script descargaba el adjunto desde IMAP, corrompiendo el final del archivo.

1.  **Entrada**: Se llama a `procesar_y_subir_factura("downloads/factura_danada.zip")`.
2.  **Validación ZIP**:
    *   **Identidad**: El archivo empieza con la firma correcta. -> *Pasa*.
    *   **Corrupción**: El sistema llama a `testzip()`. Como faltan bytes del final, los cálculos cíclicos de redundancia fallan. Se lanza una excepción de archivo malo o un error de CRC.
    *   **¡ALERTA!**: Se imprime en el log: `"El archivo ZIP está corrupto o es inválido."`
3.  **Subida a la Nube**: El código entra por la rama de error de validación, por lo que nunca extrae nada y nunca hace el llamado a `s3_utils`.
4.  **Retorno**: Retorna `False`. El sistema exigirá un reprocesamiento posterior.

> **Conclusión**: El uso del "único return" con un valor por defecto en `False` garantiza que, a menos que el ZIP pruebe ser 100% seguro y se suba sin incidentes, el proceso siempre se inclinará por la precaución y el bloqueo del flujo.
