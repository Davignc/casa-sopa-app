from decimal import Decimal
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.core.security import SENHA_MAX_BYTES
from app.core.validators import normalizar_email, normalizar_telefone
from app.models.usuario import CARGO_VENDEDORA

Cargo = Literal["administradora", "vendedora"]


class UsuarioBase(BaseModel):
    # Campos desconhecidos são recusados (evita "mass assignment", ex.: is_ativo).
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: str = Field(min_length=1, max_length=150)
    email: EmailStr = Field(max_length=255)
    telefone: str = Field(min_length=1, max_length=20)
    cargo: Cargo
    # Percentual (0 a 100, 2 casas). Só se aplica às vendedoras (RF03/RM07).
    comissao: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)

    @field_validator("email")
    @classmethod
    def _email_minusculo(cls, v: str) -> str:
        return normalizar_email(v)

    @field_validator("telefone")
    @classmethod
    def _telefone_so_digitos(cls, v: str) -> str:
        return normalizar_telefone(v)

    @model_validator(mode="after")
    def _comissao_so_para_vendedora(self) -> Self:
        if self.comissao is not None and self.cargo != CARGO_VENDEDORA:
            raise ValueError("A comissão só se aplica a usuárias com cargo de vendedora.")
        return self


class UsuarioCreate(UsuarioBase):
    senha: str = Field(min_length=8, max_length=SENHA_MAX_BYTES)

    @field_validator("senha")
    @classmethod
    def senha_cabe_no_bcrypt(cls, v: str) -> str:
        if len(v.encode("utf-8")) > SENHA_MAX_BYTES:
            raise ValueError(f"A senha não pode passar de {SENHA_MAX_BYTES} bytes.")
        return v


class UsuarioUpdate(BaseModel):
    """Alteração parcial (PATCH): só os campos enviados são alterados (RF04).

    ``is_ativo`` não entra aqui: usa-se DELETE (inativar) e POST .../reativar.
    ``comissao: null`` limpa a comissão.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = Field(default=None, max_length=255)
    telefone: str | None = Field(default=None, min_length=1, max_length=20)
    cargo: Cargo | None = None
    comissao: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    senha: str | None = Field(default=None, min_length=8, max_length=SENHA_MAX_BYTES)

    @field_validator("email")
    @classmethod
    def _email_minusculo(cls, v: str | None) -> str | None:
        return None if v is None else normalizar_email(v)

    @field_validator("telefone")
    @classmethod
    def _telefone_so_digitos(cls, v: str | None) -> str | None:
        return None if v is None else normalizar_telefone(v)

    @field_validator("senha")
    @classmethod
    def _senha_cabe_no_bcrypt(cls, v: str | None) -> str | None:
        if v is not None and len(v.encode("utf-8")) > SENHA_MAX_BYTES:
            raise ValueError(f"A senha não pode passar de {SENHA_MAX_BYTES} bytes.")
        return v

    @model_validator(mode="after")
    def _validacoes_gerais(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para alterar.")
        for campo in ("nome", "email", "telefone", "cargo", "senha"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"O campo {campo} não pode ser nulo.")
        if self.comissao is not None and self.cargo not in (None, CARGO_VENDEDORA):
            raise ValueError("A comissão só se aplica a usuárias com cargo de vendedora.")
        return self


class UsuarioRead(BaseModel):
    """Representação pública do usuário — nunca expõe a senha."""

    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    nome: str
    email: EmailStr
    telefone: str
    cargo: str
    comissao: Decimal | None
    is_ativo: bool


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str

    @field_validator("email")
    @classmethod
    def _email_minusculo(cls, v: str) -> str:
        return normalizar_email(v)
