"""Esquemas Pydantic para la gestión de usuarios."""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UsuarioBase(BaseModel):
    correo: EmailStr
    nombre_completo: str
    rol: str = "usuario"

class UsuarioCreate(UsuarioBase):
    pass

class UsuarioUpdate(BaseModel):
    correo: Optional[EmailStr] = None
    nombre_completo: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None

class UsuarioResponse(UsuarioBase):
    id_usuario: int
    activo: bool
    fecha_creacion: datetime

class UsuarioCreateResponse(UsuarioResponse):
    contrasena_generada: str  # Solo se retorna una vez al crear
