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
    cargo: str = "vendedora"
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


class PontoSerie(BaseModel):
    """Um ponto do gráfico de vendas ao longo do tempo (dia, semana ou mês)."""

    inicio: date
    pedidos: int
    faturamento: Decimal


class ItemRanking(BaseModel):
    """`quantidade` = unidades vendidas (produtos) ou número de pedidos (demais)."""

    id: int | None
    nome: str
    quantidade: int
    valor: Decimal


class Analise(BaseModel):
    """Tudo o que os gráficos precisam, de uma vez, para o mesmo filtro (RF27, RF28)."""

    periodo: PeriodoRead
    agrupamento: str
    totais: TotaisVendas
    serie: list[PontoSerie]
    pedidos_por_status: dict[str, int]
    por_forma_pagamento: list[ItemRanking]
    por_vendedora: list[ResumoVendedora]
    top_produtos: list[ItemRanking]
    top_clientes: list[ItemRanking]
    por_bairro: list[ItemRanking]
