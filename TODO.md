# TODO — Pendientes para producción

## 🔴 Gateway / Proxy (Caddy)

El servicio `gateway` (Caddy) está **comentado** en `docker-compose.yml` porque el VPS actualmente usa **nginx-proxy** que ya ocupa los puertos 80/443.

### Pasos para habilitar en producción

1. **Detener nginx-proxy** en el VPS:
   ```bash
   docker stop nginx-proxy
   docker rm nginx-proxy
   ```

2. **Verificar que los puertos 80 y 443 estén libres:**
   ```bash
   ss -tlnp | grep -E ':80|:443'
   ```

3. **Descomentar el servicio `gateway`** en `docker-compose.yml` y los volúmenes `caddy_data` / `caddy_config`.

4. **Eliminar la red `nginx-proxy`** del docker-compose si ya no se necesita, y quitar `VIRTUAL_HOST` / `LETSENCRYPT_HOST` del frontend (Caddy se encargará del SSL).

5. **Crear/verificar el archivo `Caddyfile`** con la configuración del dominio:
   ```
   directoratlas.online {
       handle /api/* {
           reverse_proxy api:8888
       }
       handle {
           reverse_proxy frontend:3000
       }
   }
   ```

6. **Levantar todo:**
   ```bash
   docker compose up -d --build
   ```

---

## ✅ Completados

- [x] Módulo Control (backend + frontend)
- [x] Merge de rama `26-agrega-procesamiento-asíncrono-con-colas-de-trabajo` a `main`
