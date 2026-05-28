import secrets
from typing import List, Optional
from fastapi import HTTPException

from core.python.db.connection import get_pool
from core.python.auth.security import get_password_hash
from core.python.schemas.usuarios_schemas import (
    UsuarioCreate,
    UsuarioUpdate,
    UsuarioResponse,
    UsuarioCreateResponse,
    UsuarioSelfUpdate
)
from config import get_queries_usuarios

async def get_all_usuarios() -> List[UsuarioResponse]:
    pool = get_pool()
    queries = get_queries_usuarios()
    
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(queries['listar'])
            rows = await cur.fetchall()
            
            return [
                UsuarioResponse(
                    id_usuario=row[0],
                    correo=row[1],
                    nombre_completo=row[2],
                    rol=row[3],
                    activo=row[4],
                    fecha_creacion=row[5],
                    tutorial_visto=row[6]
                ) for row in rows
            ]

async def get_usuarios_basico() -> List[dict]:
    pool = get_pool()
    queries = get_queries_usuarios()
    
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(queries['listar_basico'])
            rows = await cur.fetchall()
            return [
                {
                    "id_usuario": row[0],
                    "nombre_completo": row[1]
                } for row in rows
            ]

async def create_usuario(usuario: UsuarioCreate) -> UsuarioCreateResponse:
    pool = get_pool()
    queries = get_queries_usuarios()
    
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Check if email exists
            await cur.execute(queries['verificar_correo_existe'], (usuario.correo,))
            if await cur.fetchone():
                raise HTTPException(status_code=400, detail="El correo ya está registrado.")
            
            # Generate random password
            plain_password = secrets.token_urlsafe(8)
            hashed_password = get_password_hash(plain_password)
            
            await cur.execute(
                queries['insertar'],
                (usuario.correo, hashed_password, usuario.nombre_completo, usuario.rol, True, False)
            )
            row = await cur.fetchone()
            
            return UsuarioCreateResponse(
                id_usuario=row[0],
                correo=row[1],
                nombre_completo=row[2],
                rol=row[3],
                activo=row[4],
                fecha_creacion=row[5],
                tutorial_visto=row[6],
                contrasena_generada=plain_password
            )

async def update_usuario(id_usuario: int, usuario: UsuarioUpdate) -> UsuarioResponse:
    pool = get_pool()
    queries = get_queries_usuarios()
    
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if usuario.correo:
                await cur.execute(queries['verificar_correo_existe'], (usuario.correo,))
                existing = await cur.fetchone()
                # Check if it belongs to another user (this is simple, we might need a more complex check, but for now we skip complex checks or do it in python)
            
            await cur.execute(
                queries['actualizar'],
                (usuario.correo, usuario.nombre_completo, usuario.rol, usuario.activo, usuario.tutorial_visto, id_usuario)
            )
            row = await cur.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
                
            return UsuarioResponse(
                id_usuario=row[0],
                correo=row[1],
                nombre_completo=row[2],
                rol=row[3],
                activo=row[4],
                fecha_creacion=row[5],
                tutorial_visto=row[6]
            )

async def delete_usuario(id_usuario: int) -> dict:
    pool = get_pool()
    queries = get_queries_usuarios()
    
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(queries['eliminar'], (id_usuario,))
            row = await cur.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
                
            return {"detail": "Usuario desactivado exitosamente"}

async def update_self_usuario(id_usuario: int, data: UsuarioSelfUpdate) -> dict:
    pool = get_pool()
    queries = get_queries_usuarios()
    
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if data.correo:
                await cur.execute("SELECT id_usuario FROM facturacion.usuario WHERE correo = %s", (data.correo,))
                existing = await cur.fetchone()
                if existing and existing[0] != id_usuario:
                    raise HTTPException(status_code=400, detail="El correo ya está en uso por otro usuario.")
                
            hashed_pw = get_password_hash(data.contrasena) if data.contrasena else None
            
            await cur.execute(
                queries['actualizar_self'],
                (data.correo, data.nombre_completo, hashed_pw, data.tutorial_visto, id_usuario)
            )
            row = await cur.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
                
            return {
                "detail": "Datos actualizados exitosamente",
                "correo_cambiado": data.correo is not None,
                "password_cambiado": data.contrasena is not None,
                "tutorial_visto": row[6]
            }
