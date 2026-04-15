# Base de Datos - Facturación Electrónica

Este proyecto contiene la configuración para levantar la base de datos PostgreSQL de facturación mediante Docker. La base de datos incluye la migración de la estructura inicial cargada automáticamente en el primer arranque desde el archivo `modelo_facturacion_gpt.sql`.

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
