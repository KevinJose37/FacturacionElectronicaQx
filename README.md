# Base de Datos - Facturación Electrónica

Este proyecto contiene la configuración para levantar la base de datos PostgreSQL de facturación mediante Docker. La base de datos incluye la migración de la estructura inicial cargada automáticamente en el primer arranque desde el archivo `modelo_facturacion.sql`.

## Requisitos Previos

Si estás ejecutando esto en un VPS o en local, asegúrate de tener instalados:
- [Docker](https://docs.docker.com/engine/install/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Pasos para ejecutar

1. **Abre tu terminal** en la raíz del proyecto (donde se ubica el archivo `docker-compose.yml`).
2. **Levanta la base de datos** en segundo plano (modo detached) ejecutando el siguiente comando:

   ```bash
   docker-compose up -d
   ```
   *(Si utilizas la versión V2 de Docker Compose, el comando es `docker compose up -d`)*

3. **Verifica la migración:** En su primer arranque, PostgreSQL ejecutará el script SQL provisto. Para asegurar que no hubo errores, revisa los logs del contenedor:
   ```bash
   docker logs facturacion_db
   ```
   *Deberías ver un mensaje que dice "database system is ready to accept connections" al final.*

## Datos de Conexión (VPS y Local)

El contenedor expondrá el puerto `5432` convencional de PostgreSQL. Utiliza la siguiente información para conectar tu aplicación o cliente de base de datos (como DBeaver o pgAdmin):

- **Host Local:** `127.0.0.1` o `localhost`
- **Host en VPS:** `<IP_PUBLICA_DE_TU_VPS>`
- **Puerto:** `5432`
- **Base de Datos:** `facturacion`
- **Usuario:** `admin`
- **Contraseña:** `mysecretpassword` *(Ver nota de seguridad)*

**String de conexión:**
```
postgresql://admin:mysecretpassword@<IP_DEL_VPS>:5432/facturacion?schema=public
```

***

### ⚠️ Consideraciones de Seguridad (¡Muy Importante para VPS!)

Si estás subiendo esto a un VPS en producción y lo dejas abierto al internet:

1. **¡Cambia la Contraseña!**
   Antes de levantar el servicio, edita el archivo `docker-compose.yml` y cambia `mysecretpassword` por una contraseña fuerte.
2. **Restricción de Puertos (Firewall)**
   Por defecto, el servicio será accesible para cualquier persona que conozca la IP del VPS. Si tu API se hospeda en el mismo servidor, puedes quitar la directiva `ports` de Docker Compose o utilizar UFW en Ubuntu para permitir solo IPs autorizadas:
   ```bash
   # Solo permitir acceso a la BD desde la IP de mi backend
   sudo ufw allow from <IP_DE_MI_BACKEND> to any port 5432
   ```

## Comandos Útiles

- **Detener el servicio:** `docker-compose stop`
- **Reiniciar el servicio:** `docker-compose start`
- **Borrar contenedor (Mantiene la Data):** `docker-compose down`
- **Borrar contenedor y resetear TODA la base de datos (Peligro):** `docker-compose down -v`

---

## API — Facturación Electrónica

### Requisitos

- Python 3.11+
- PostgreSQL corriendo (ver sección anterior)

### Instalación

```bash
# Crear entorno virtual
python -m venv venv

# Activar (Linux/Mac)
source venv/bin/activate

# Activar (Windows)
.\venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### Configuración `.env`

Crea un archivo `.env` en la raíz del proyecto (usa `.env.example` como referencia):

```env
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=facturacion
POSTGRES_USER=admin
POSTGRES_PASSWORD=mysecretpassword
WEBHOOK_SECRET=tu_secreto_aqui
EMAIL_USER=tu_email@gmail.com
EMAIL_PASSWORD=tu_app_password
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8080
```

### Migraciones de Base de Datos

Las migraciones SQL se encuentran en `scripts/` con el formato `migration_NNN_descripcion.sql`.

**Migraciones disponibles:**

| Archivo | Descripción | Idempotente |
|---------|-------------|:-----------:|
| `modelo_facturacion.sql` | Schema inicial completo (se ejecuta auto con Docker) | ✅ |
| `scripts/migration_001_tipo_documento.sql` | Agrega columna `tipo_documento` a `factura` | ✅ |

#### Correr migraciones en el VPS

```bash
# Opción 1: Desde el VPS con psql (recomendado)
psql -h 127.0.0.1 -p 5432 -U admin -d facturacion -f scripts/migration_001_tipo_documento.sql

# Opción 2: Desde el VPS usando Docker exec
docker exec -i facturacion_db psql -U admin -d facturacion < scripts/migration_001_tipo_documento.sql

# Opción 3: Desde tu máquina local apuntando al VPS
psql -h <IP_DEL_VPS> -p 5432 -U admin -d facturacion -f scripts/migration_001_tipo_documento.sql
```

> **Nota:** Todas las migraciones usan `IF NOT EXISTS` o son idempotentes, por lo que se pueden ejecutar múltiples veces sin riesgo.

#### Correr TODAS las migraciones de una vez

```bash
# Desde el VPS
for f in scripts/migration_*.sql; do
  echo "Ejecutando $f..."
  psql -h 127.0.0.1 -p 5432 -U admin -d facturacion -f "$f"
done
```

### Datos de Prueba (Seed)

Para poblar la base de datos con datos de ejemplo:

```bash
python scripts/seed.py
```

> ⚠️ **El seed borra todos los datos existentes** antes de insertar los nuevos. No ejecutar en producción con datos reales.

### Iniciar la API

```bash
python main.py
```

La API estará disponible en `http://0.0.0.0:8888`.

- **Documentación Swagger:** `http://<HOST>:8888/docs`
- **Health check:** `GET /` → `{"status": "online"}`

### Endpoints Disponibles

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/dashboard` | GET | Dashboard completo (KPIs, gráficos, pipeline) |
| `/api/facturas` | GET | Listado de facturas con filtros y estadísticas |
| `/api/proveedores` | GET | Listado de proveedores con métricas |
| `/api/validaciones` | GET | Reglas de validación con conteos |
| `/api/rechazos` | GET | Rechazos con causas frecuentes |
| `/api/logs` | GET | Logs del sistema con conteos por nivel |
| `/webhook/gmail` | POST | Webhook para ingesta desde Gmail |
