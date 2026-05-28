"""Esquemas Pydantic para la gestión de usuarios."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UsuarioBase(BaseModel):
    correo: str
    nombre_completo: str
    rol: str = "usuario"
    tutorial_visto: bool = False

class UsuarioCreate(UsuarioBase):
    pass

class UsuarioUpdate(BaseModel):
    correo: Optional[str] = None
    nombre_completo: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None
    tutorial_visto: Optional[bool] = None

class UsuarioResponse(UsuarioBase):
    id_usuario: int
    activo: bool
    fecha_creacion: datetime

class UsuarioCreateResponse(UsuarioResponse):
    contrasena_generada: str  # Solo se retorna una vez al crear

class UsuarioSelfUpdate(BaseModel):
    correo: Optional[str] = None
    nombre_completo: Optional[str] = None
    contrasena: Optional[str] = None
    tutorial_visto: Optional[bool] = None
