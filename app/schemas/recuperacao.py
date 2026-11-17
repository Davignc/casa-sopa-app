from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import SENHA_MAX_BYTES


class RecuperarSenha(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=255)


class RedefinirSenha(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=1, max_length=2048)
    senha: str = Field(min_length=8, max_length=SENHA_MAX_BYTES)

    @field_validator("senha")
    @classmethod
    def senha_em_bytes(cls, valor: str) -> str:
        if len(valor.encode("utf-8")) > SENHA_MAX_BYTES:
            raise ValueError("A senha não pode passar de 72 bytes.")
        return valor
