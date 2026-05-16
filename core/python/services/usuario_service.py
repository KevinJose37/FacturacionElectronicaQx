import secrets
from typing import List, Optional
from fastapi import HTTPException

from core.python.db.connection import get_pool
from core.python.auth.security import get_password_hash
from core.python.schemas.usuarios_schemas import (
    UsuarioCreate,
    UsuarioUpdate,
    UsuarioResponse,
    UsuarioCreateResponse
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
                    fecha_creacion=row[5]
                ) for row in rows
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
                (usuario.correo, hashed_password, usuario.nombre_completo, usuario.rol, True)
            )
            row = await cur.fetchone()
            
            return UsuarioCreateResponse(
                id_usuario=row[0],
                correo=row[1],
                nombre_completo=row[2],
                rol=row[3],
                activo=row[4],
                fecha_creacion=row[5],
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
                (usuario.correo, usuario.nombre_completo, usuario.rol, usuario.activo, id_usuario)
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
                fecha_creacion=row[5]
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
