from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import SENHA_MAX_BYTES


class UsuarioBase(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    email: EmailStr = Field(max_length=255)
    endereco: str = Field(min_length=1, max_length=255)
    telefone: str = Field(min_length=1, max_length=20)


class UsuarioCreate(UsuarioBase):
    senha: str = Field(min_length=8, max_length=SENHA_MAX_BYTES)

    @field_validator("senha")
    @classmethod
    def senha_cabe_no_bcrypt(cls, v: str) -> str:
        if len(v.encode("utf-8")) > SENHA_MAX_BYTES:
            raise ValueError(f"A senha não pode passar de {SENHA_MAX_BYTES} bytes.")
        return v


class UsuarioRead(UsuarioBase):
    """Representação pública do usuário — nunca expõe a senha."""

    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    is_ativo: bool


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str
