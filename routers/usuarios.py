from typing import List
from fastapi import APIRouter, Depends, HTTPException

from core.python.auth.deps import get_current_admin_user
from core.python.schemas.auth_schemas import UserInDB
from core.python.schemas.usuarios_schemas import (
    UsuarioCreate,
    UsuarioUpdate,
    UsuarioResponse,
    UsuarioCreateResponse
)
from core.python.services import usuario_service

router = APIRouter(
    prefix="/api/usuarios",
    tags=["usuarios"],
    dependencies=[Depends(get_current_admin_user)]
)

@router.get("", response_model=List[UsuarioResponse])
async def list_usuarios():
    """Lista todos los usuarios (solo admin)."""
    return await usuario_service.get_all_usuarios()

@router.post("", response_model=UsuarioCreateResponse)
async def create_usuario(usuario: UsuarioCreate):
    """Crea un usuario nuevo con contraseña generada aleatoriamente (solo admin)."""
    return await usuario_service.create_usuario(usuario)

@router.put("/{id_usuario}", response_model=UsuarioResponse)
async def update_usuario(id_usuario: int, usuario: UsuarioUpdate):
    """Actualiza datos o estado de un usuario (solo admin)."""
    return await usuario_service.update_usuario(id_usuario, usuario)

@router.delete("/{id_usuario}")
async def delete_usuario(id_usuario: int):
    """Desactiva lógicamente a un usuario (solo admin)."""
    return await usuario_service.delete_usuario(id_usuario)
