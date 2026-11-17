import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_ITENS = 100
MAX_QUANTIDADE = 100_000


def normalizar_forma_pagamento(valor: str) -> str:
    texto = re.sub(r"\s+", " ", valor).strip().lower()
    if not 1 <= len(texto) <= 30:
        raise ValueError("A forma de pagamento deve ter de 1 a 30 caracteres.")
    return texto


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ItemEntrada(_Base):
    id_produto: int = Field(gt=0)
    quantidade: int = Field(ge=1, le=MAX_QUANTIDADE)


def _sem_repetidos(itens: list[ItemEntrada]) -> list[ItemEntrada]:
    ids = [i.id_produto for i in itens]
    if len(ids) != len(set(ids)):
        raise ValueError("Um produto só pode aparecer uma vez no pedido: some as quantidades.")
    return itens


class PedidoCreate(_Base):
    """O preço e o total NÃO são enviados: o servidor calcula com o preço do cadastro (RF11)."""

    id_cliente: int = Field(gt=0)
    id_endereco: int = Field(gt=0, description="Um dos endereços do cliente")
    forma_pagamento: str = Field(description='Ex.: "pix", "dinheiro", "cartão"')
    itens: list[ItemEntrada] = Field(min_length=1, max_length=MAX_ITENS)
    observacao: str | None = Field(default=None, min_length=1, max_length=255)
    data_pagamento: datetime | None = None
    id_vendedora: int | None = Field(
        default=None, gt=0, description="Só a administradora pode registrar em nome de outra"
    )

    @field_validator("forma_pagamento")
    @classmethod
    def _forma(cls, v: str) -> str:
        return normalizar_forma_pagamento(v)

    @field_validator("itens")
    @classmethod
    def _itens(cls, v: list[ItemEntrada]) -> list[ItemEntrada]:
        return _sem_repetidos(v)


class PedidoUpdate(_Base):
    """Não existe campo para a vendedora responsável: ela não muda (RF12, RN10)."""

    id_cliente: int | None = Field(default=None, gt=0)
    id_endereco: int | None = Field(default=None, gt=0)
    forma_pagamento: str | None = None
    itens: list[ItemEntrada] | None = Field(default=None, min_length=1, max_length=MAX_ITENS)
    observacao: str | None = Field(default=None, min_length=1, max_length=255)
    data_pagamento: datetime | None = None

    @field_validator("forma_pagamento")
    @classmethod
    def _forma(cls, v: str | None) -> str | None:
        return None if v is None else normalizar_forma_pagamento(v)

    @field_validator("itens")
    @classmethod
    def _itens(cls, v: list[ItemEntrada] | None) -> list[ItemEntrada] | None:
        return None if v is None else _sem_repetidos(v)

    @model_validator(mode="after")
    def _validar(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para alterar.")
        # observacao e data_pagamento aceitam null (limpam o valor); os demais não.
        for campo in ("id_cliente", "id_endereco", "forma_pagamento", "itens"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"O campo {campo} não pode ser nulo.")
        return self


class StatusUpdate(_Base):
    status: Literal["confirmado", "entregue", "cancelado"]


class ClientePedido(BaseModel):
    id_cliente: int
    nome: str
    telefone: str


class VendedoraPedido(BaseModel):
    id_usuario: int
    nome: str


class EnderecoPedido(BaseModel):
    id_endereco: int
    endereco_formatado: str
    apelido: str | None
    referencia: str


class ItemRead(BaseModel):
    id_produto: int
    nome_produto: str
    quantidade: int
    preco_unitario: Decimal
    subtotal: Decimal


class PedidoRead(BaseModel):
    """Todas as informações da venda (RF14)."""

    id_pedido: int
    status: str
    data_venda: datetime
    forma_pagamento: str
    observacao: str | None
    data_pagamento: datetime | None
    valor_total: Decimal
    total_produtos: int
    cliente: ClientePedido
    vendedora: VendedoraPedido
    endereco_entrega: EnderecoPedido
    itens: list[ItemRead]


ViaCupom = Literal["interna", "entregador", "cliente", "todas"]

# Reexportado para os filtros de listagem.
Periodo = tuple[date | None, date | None]


class ContagemPedidos(BaseModel):
    """Quantos pedidos há em cada situação, para o mesmo filtro (abas da tela de pedidos)."""

    todos: int
    em_aberto: int
    confirmado: int
    entregue: int
    cancelado: int
