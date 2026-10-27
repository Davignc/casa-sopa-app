from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class PeriodoRead(BaseModel):
    inicio: date
    fim: date


class Dashboard(BaseModel):
    """Vendas do último mês (RF27): confirmadas e entregues; canceladas e em aberto não contam."""

    periodo: PeriodoRead
    total_pedidos: int
    produtos_vendidos: int
    faturamento: Decimal
    comissoes: Decimal
    comissoes_pendentes: Decimal
    pedidos_por_status: dict[str, int]


class ResumoVendedora(BaseModel):
    id_usuario: int
    nome: str
    is_ativo: bool
    comissao_percentual: Decimal | None
    quantidade_pedidos: int
    produtos_vendidos: int
    valor_total: Decimal
    comissao_a_receber: Decimal
    comissao_pendente: Decimal


class TotaisVendas(BaseModel):
    quantidade_pedidos: int
    produtos_vendidos: int
    valor_total: Decimal
    comissao_a_receber: Decimal
    comissao_pendente: Decimal


class RelatorioVendas(BaseModel):
    """Vendas por vendedora num período (RF28)."""

    periodo: PeriodoRead
    vendedoras: list[ResumoVendedora]
    totais: TotaisVendas
