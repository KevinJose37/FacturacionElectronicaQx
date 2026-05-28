"""Dependencias inyectables de FastAPI para requerir autenticación."""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError

from core.python.db import get_pool
from core.python.auth.security import SECRET_KEY, ALGORITHM
from core.python.schemas.auth_schemas import TokenData, UserInDB
from config import get_queries_auth

# URL a la que el frontend o swagger debe enviar las credenciales
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

async def get_user_by_email(correo: str) -> dict | None:
    """Busca un usuario por su correo electrónico en la BD."""
    pool = get_pool()
    queries = get_queries_auth()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                queries['buscar_por_correo'],
                (correo,)
            )
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "id_usuario": row[0],
                "correo": row[1],
                "nombre_completo": row[2],
                "rol": row[3],
                "activo": row[4],
                "hash_contrasena": row[5],
                "tutorial_visto": row[6]
            }

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """Valida el token JWT de la petición y devuelve el usuario asociado."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except jwt.PyJWTError:
        raise credentials_exception
    except ValidationError:
        raise credentials_exception
        
    user = await get_user_by_email(correo=token_data.username)
    if user is None:
        raise credentials_exception
        
    return UserInDB(**user)

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    """Dependencia que asegura que el usuario autenticado está activo."""
    if not current_user.activo:
        raise HTTPException(status_code=400, detail="Usuario inactivo")
    return current_user

async def get_current_admin_user(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
    """Dependencia que asegura que el usuario tiene rol de administrador."""
    if current_user.rol != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene los permisos suficientes (requiere rol admin)"
        )
    return current_user
