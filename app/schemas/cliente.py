import re
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.validators import normalizar_telefone


def normalizar_cep(valor: str) -> str:
    digitos = re.sub(r"\D", "", valor)
    if len(digitos) != 8:
        raise ValueError("CEP inválido: informe 8 dígitos.")
    return digitos


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EnderecoEntrada(_Base):
    """Endereço informado no cadastro do cliente (RF07)."""

    cep: str
    cidade: str = Field(min_length=1, max_length=50)
    bairro: str = Field(min_length=1, max_length=50)
    tipo_logradouro: str = Field(min_length=1, max_length=20, description='Ex.: "Avenida"')
    nome_logradouro: str = Field(
        min_length=1, max_length=100, description='Ex.: "Presidente Vargas"'
    )
    numero: str = Field(min_length=1, max_length=10, description='Aceita "123A" e "S/N"')
    complemento: str = Field(default="", max_length=50)
    referencia: str = Field(default="", max_length=50)
    apelido: str | None = Field(default=None, min_length=1, max_length=50)
    principal: bool = False

    @field_validator("cep")
    @classmethod
    def _cep(cls, v: str) -> str:
        return normalizar_cep(v)


class VinculoExistente(_Base):
    """Liga o cliente a um endereço que JÁ está registrado no sistema (achado na busca).

    Rua, bairro, cidade e CEP já existem; aqui só vão os dados do vínculo (RM04).
    """

    id_endereco: int = Field(gt=0)
    numero: str = Field(min_length=1, max_length=10, description='Aceita "123A" e "S/N"')
    complemento: str = Field(default="", max_length=50)
    referencia: str = Field(default="", max_length=50)
    apelido: str | None = Field(default=None, min_length=1, max_length=50)
    principal: bool = False


# Novo endereço completo OU vínculo com um endereço existente.
EnderecoDoCliente = EnderecoEntrada | VinculoExistente


class EnderecoVinculoUpdate(_Base):
    """Dados do vínculo cliente-endereço. A rua/bairro/cidade não mudam aqui (veja a rota)."""

    apelido: str | None = Field(default=None, min_length=1, max_length=50)
    principal: bool | None = None
    numero: str | None = Field(default=None, min_length=1, max_length=10)
    complemento: str | None = Field(default=None, max_length=50)
    referencia: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def _ao_menos_um(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para alterar.")
        for campo in ("principal", "numero", "complemento", "referencia"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"O campo {campo} não pode ser nulo.")
        return self


class ClienteCreate(_Base):
    nome: str = Field(min_length=1, max_length=150)
    telefone: str = Field(min_length=1, max_length=20)
    enderecos: list[EnderecoDoCliente] = Field(default_factory=list, max_length=10)

    @field_validator("telefone")
    @classmethod
    def _telefone(cls, v: str) -> str:
        return normalizar_telefone(v)

    @model_validator(mode="after")
    def _um_principal(self) -> Self:
        principais = [e for e in self.enderecos if e.principal]
        if len(principais) > 1:
            raise ValueError("Apenas um endereço pode ser o principal.")
        if self.enderecos and not principais:
            self.enderecos[0].principal = True  # o primeiro vira o principal
        return self


class ClienteUpdate(_Base):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    telefone: str | None = Field(default=None, min_length=1, max_length=20)

    @field_validator("telefone")
    @classmethod
    def _telefone(cls, v: str | None) -> str | None:
        return None if v is None else normalizar_telefone(v)

    @model_validator(mode="after")
    def _ao_menos_um(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para alterar.")
        for campo in ("nome", "telefone"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"O campo {campo} não pode ser nulo.")
        return self


class EnderecoRead(BaseModel):
    id_endereco: int
    cep: str
    cidade: str
    bairro: str
    tipo_logradouro: str
    nome_logradouro: str
    numero: str
    complemento: str
    referencia: str
    apelido: str | None
    principal: bool
    endereco_formatado: str


class ResponsavelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    nome: str


class ClienteResumo(BaseModel):
    """Linha da listagem (RF10): nome, telefone, endereço principal e quem cadastrou."""

    id_cliente: int
    nome: str
    telefone: str
    is_ativo: bool
    endereco_principal: EnderecoRead | None
    cadastrado_por: ResponsavelRead


class ClienteRead(ClienteResumo):
    enderecos: list[EnderecoRead]


class EnderecoBusca(BaseModel):
    """Endereço físico já registrado (resultado da busca). Sem número: ele é de cada cliente."""

    id_endereco: int
    cep: str
    cidade: str
    bairro: str
    tipo_logradouro: str
    nome_logradouro: str
    descricao: str
    quantidade_clientes: int
