"""Esquemas Pydantic para el módulo de autenticación."""

from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class UserBase(BaseModel):
    correo: str
    nombre_completo: str
    rol: str
    tutorial_visto: bool = False

class UserInDB(UserBase):
    id_usuario: int
    activo: bool
