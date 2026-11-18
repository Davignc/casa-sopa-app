"""Períodos e agrupamento por dia, semana ou mês (relatórios e gráficos)."""

from datetime import date, timedelta
from typing import Literal

from app.core.errors import RegraInvalidaError
from app.core.tempo import hoje_local

Agrupamento = Literal["dia", "semana", "mes"]

DIAS_PADRAO = 30
MAX_DIAS_DO_PERIODO = 366


def janela(inicio: date | None, fim: date | None) -> tuple[date, date]:
    """Período pedido, ou os últimos 30 dias (hoje incluído) se não vier nada."""
    fim = fim or hoje_local()
    inicio = inicio or (fim - timedelta(days=DIAS_PADRAO - 1))
    if inicio > fim:
        raise RegraInvalidaError("A data inicial não pode ser depois da data final.")
    if (fim - inicio).days >= MAX_DIAS_DO_PERIODO:
        raise RegraInvalidaError("O período não pode passar de 1 ano.")
    return inicio, fim


def escolher_agrupamento(inicio: date, fim: date) -> Agrupamento:
    """Para o gráfico não ficar nem vazio nem entupido: até 45 dias por dia, até ~7 meses
    por semana, acima disso por mês."""
    dias = (fim - inicio).days + 1
    if dias <= 45:
        return "dia"
    if dias <= 200:
        return "semana"
    return "mes"


def inicio_do_balde(dia: date, agrupar: Agrupamento) -> date:
    if agrupar == "dia":
        return dia
    if agrupar == "semana":
        return dia - timedelta(days=dia.weekday())  # segunda-feira
    return dia.replace(day=1)


def _proximo(balde: date, agrupar: Agrupamento) -> date:
    if agrupar == "dia":
        return balde + timedelta(days=1)
    if agrupar == "semana":
        return balde + timedelta(days=7)
    return (balde.replace(day=28) + timedelta(days=4)).replace(day=1)


def gerar_baldes(inicio: date, fim: date, agrupar: Agrupamento) -> list[date]:
    """Todos os baldes do período, inclusive os vazios (o gráfico não pode "pular" dias)."""
    baldes = []
    atual = inicio_do_balde(inicio, agrupar)
    while atual <= fim:
        baldes.append(atual)
        atual = _proximo(atual, agrupar)
    return baldes
