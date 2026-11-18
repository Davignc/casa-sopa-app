from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

QUANTIDADE_MAXIMA = 1_000_000
Preco = Field(ge=0, max_digits=10, decimal_places=2, description="Preço em reais, 2 casas")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProdutoCreate(_Base):
    nome: str = Field(min_length=1, max_length=150)
    descricao: str = Field(min_length=1, max_length=255)
    preco_unitario: Decimal = Preco
    estoque_inicial: int = Field(default=0, ge=0, le=QUANTIDADE_MAXIMA)
    estoque_minimo: int = Field(ge=0, le=QUANTIDADE_MAXIMA)


class ProdutoUpdate(_Base):
    """Não altera a quantidade em estoque: isso é feito por entradas e saídas (histórico)."""

    nome: str | None = Field(default=None, min_length=1, max_length=150)
    descricao: str | None = Field(default=None, min_length=1, max_length=255)
    preco_unitario: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2, description="Preço em reais"
    )
    estoque_minimo: int | None = Field(default=None, ge=0, le=QUANTIDADE_MAXIMA)

    @model_validator(mode="after")
    def _validar(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para alterar.")
        for campo in self.model_fields_set:
            if getattr(self, campo) is None:
                raise ValueError(f"O campo {campo} não pode ser nulo.")
        return self


class ProdutoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_produto: int
    nome: str
    descricao: str
    preco_unitario: Decimal
    estoque_atual: int
    estoque_minimo: int
    is_ativo: bool

    @computed_field  # type: ignore[prop-decorator]
    @property
    def alerta_estoque_baixo(self) -> bool:
        """RN14/RF23: ativo e com quantidade igual ou abaixo do mínimo."""
        return self.is_ativo and self.estoque_atual <= self.estoque_minimo


class EntradaEstoque(_Base):
    id_produto: int = Field(gt=0)
    quantidade: int = Field(ge=1, le=QUANTIDADE_MAXIMA)
    tipo: Literal["compra", "ajuste_manual"] = "compra"
    observacao: str | None = Field(default=None, min_length=1, max_length=150)


class SaidaEstoque(_Base):
    """Saída por perda ou ajuste manual (RF22): o motivo é obrigatório."""

    id_produto: int = Field(gt=0)
    quantidade: int = Field(ge=1, le=QUANTIDADE_MAXIMA)
    motivo: str = Field(min_length=3, max_length=150)


class MovimentacaoRead(BaseModel):
    id_movimentacao: int
    id_produto: int
    nome_produto: str
    tipo_movimentacao: str
    quantidade: int
    tipo_referencia: str
    id_venda: int | None
    observacao: str | None
    data_movimentacao: datetime


class MovimentacaoResultado(BaseModel):
    movimentacao: MovimentacaoRead
    produto: ProdutoRead


class PontoMovimentacao(BaseModel):
    inicio: date
    entradas: int
    saidas: int


class ResumoMovimentacoes(BaseModel):
    """Entradas e saídas ao longo do tempo (gráfico da tela de movimentações do produto)."""

    periodo_inicio: date
    periodo_fim: date
    agrupamento: str
    total_entradas: int
    total_saidas: int
    saldo_do_periodo: int
    serie: list[PontoMovimentacao]
