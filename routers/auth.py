"""Endpoints de autenticación OAuth2."""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from core.python.auth.security import (
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from core.python.auth.deps import get_user_by_email, get_current_active_user
from core.python.schemas.auth_schemas import Token, UserInDB

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Endpoint para autenticar un usuario usando OAuth2 (usuario y contraseña).
    Retorna un token JWT (Bearer) que debe usarse en las siguientes peticiones.
    """
    user_dict = await get_user_by_email(form_data.username)
    if not user_dict or not verify_password(form_data.password, user_dict["hash_contrasena"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_dict["correo"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

from core.python.schemas.usuarios_schemas import UsuarioSelfUpdate
from core.python.services import usuario_service

@router.get("/me", response_model=UserInDB)
async def read_users_me(current_user: UserInDB = Depends(get_current_active_user)):
    """
    Endpoint para obtener los datos del usuario autenticado actualmente.
    """
    return current_user

@router.patch("/me")
async def update_users_me(
    data: UsuarioSelfUpdate,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Actualiza los datos del propio usuario (correo, nombre, contraseña).
    """
    return await usuario_service.update_self_usuario(current_user.id_usuario, data)
