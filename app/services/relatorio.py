"""Dashboard e relatórios de vendas (RF27, RF28).

Regras de contagem (os documentos não as definem, então ficam explícitas aqui):
* "venda" = pedido **confirmado** ou **entregue**, pela data da venda, no fuso local;
  pedidos em aberto e cancelados não entram nos totais;
* comissão = valor do pedido × percentual da vendedora. «A receber» considera os pedidos
  **entregues**; «pendente», os confirmados que ainda não foram entregues;
* o percentual usado é o **atual** da vendedora (o modelo de dados não guarda o percentual
  no momento da venda): mudar a comissão muda também o que se calcula do passado.
"""

import csv
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO, StringIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NaoEncontradoError, RegraInvalidaError
from app.core.tempo import fim_do_dia_exclusivo_utc, hoje_local, inicio_do_dia_utc, para_local
from app.models.item_venda import ItemVenda
from app.models.usuario import CARGO_VENDEDORA, Usuario
from app.models.venda import (
    STATUS,
    STATUS_CONFIRMADO,
    STATUS_ENTREGUE,
    Venda,
)
from app.schemas.relatorio import (
    Dashboard,
    PeriodoRead,
    RelatorioVendas,
    ResumoVendedora,
    TotaisVendas,
)
from app.services import pedido as pedido_service

STATUS_DE_VENDA = (STATUS_CONFIRMADO, STATUS_ENTREGUE)
DIAS_DO_DASHBOARD = 30
MAX_DIAS_DO_PERIODO = 366
MAX_LINHAS_EXPORTACAO = 20_000
_CENTAVOS = Decimal("0.01")


def janela(inicio: date | None, fim: date | None) -> tuple[date, date]:
    """Período pedido, ou os últimos 30 dias (hoje incluído) se não vier nada."""
    fim = fim or hoje_local()
    inicio = inicio or (fim - timedelta(days=DIAS_DO_DASHBOARD - 1))
    if inicio > fim:
        raise RegraInvalidaError("A data inicial não pode ser depois da data final.")
    if (fim - inicio).days >= MAX_DIAS_DO_PERIODO:
        raise RegraInvalidaError("O período não pode passar de 1 ano.")
    return inicio, fim


def _limites(inicio: date, fim: date) -> list[Any]:
    return [
        Venda.data_venda >= inicio_do_dia_utc(inicio),
        Venda.data_venda < fim_do_dia_exclusivo_utc(fim),
    ]


def _comissao(valor: Decimal, percentual: Decimal | None) -> Decimal:
    if not percentual:
        return Decimal("0.00")
    return (Decimal(valor) * Decimal(percentual) / 100).quantize(_CENTAVOS, ROUND_HALF_UP)


# --- dashboard ----------------------------------------------------------------


def dashboard(db: Session) -> Dashboard:
    fim = hoje_local()
    inicio = fim - timedelta(days=DIAS_DO_DASHBOARD - 1)
    limites = _limites(inicio, fim)

    por_status = {s: 0 for s in STATUS}
    for status, qtd in db.execute(
        select(Venda.status, func.count()).where(*limites).group_by(Venda.status)
    ):
        por_status[status] = qtd

    resumo = _agregar(db, inicio, fim, None)
    totais = _somar(resumo)
    return Dashboard(
        periodo=PeriodoRead(inicio=inicio, fim=fim),
        total_pedidos=totais.quantidade_pedidos,
        produtos_vendidos=totais.produtos_vendidos,
        faturamento=totais.valor_total,
        comissoes=totais.comissao_a_receber,
        comissoes_pendentes=totais.comissao_pendente,
        pedidos_por_status=por_status,
    )


# --- vendas por vendedora -------------------------------------------------------


def _agregar(
    db: Session, inicio: date, fim: date, id_vendedora: int | None
) -> list[ResumoVendedora]:
    filtros = [*_limites(inicio, fim), Venda.status.in_(STATUS_DE_VENDA)]
    if id_vendedora is not None:
        filtros.append(Venda.id_usuario == id_vendedora)

    pedidos = db.execute(
        select(Venda.id_usuario, Venda.status, func.count(), func.sum(Venda.valor_total))
        .where(*filtros)
        .group_by(Venda.id_usuario, Venda.status)
    ).all()
    unidades = {
        (u, s): int(q or 0)
        for u, s, q in db.execute(
            select(Venda.id_usuario, Venda.status, func.sum(ItemVenda.quantidade))
            .join(ItemVenda, ItemVenda.id_venda == Venda.id_venda)
            .where(*filtros)
            .group_by(Venda.id_usuario, Venda.status)
        )
    }

    ids = {p[0] for p in pedidos} | ({id_vendedora} if id_vendedora is not None else set())
    if not ids:
        return []
    usuarios = {
        u.id_usuario: u
        for u in db.scalars(select(Usuario).where(Usuario.id_usuario.in_(ids))).all()
    }

    linhas: dict[int, dict[str, Any]] = {
        i: {"qtd": 0, "unid": 0, "valor": Decimal("0.00"), "receber": Decimal("0.00"),
            "pendente": Decimal("0.00")}
        for i in ids
    }  # fmt: skip
    for id_usuario, status, qtd, valor in pedidos:
        valor = Decimal(valor or 0)
        comissao = _comissao(valor, usuarios[id_usuario].comissao)
        linha = linhas[id_usuario]
        linha["qtd"] += qtd
        linha["unid"] += unidades.get((id_usuario, status), 0)
        linha["valor"] += valor
        chave = "receber" if status == STATUS_ENTREGUE else "pendente"
        linha[chave] += comissao

    resultado = [
        ResumoVendedora(
            id_usuario=i,
            nome=usuarios[i].nome,
            is_ativo=usuarios[i].is_ativo,
            comissao_percentual=usuarios[i].comissao,
            quantidade_pedidos=linha["qtd"],
            produtos_vendidos=linha["unid"],
            valor_total=linha["valor"].quantize(_CENTAVOS),
            comissao_a_receber=linha["receber"],
            comissao_pendente=linha["pendente"],
        )
        for i, linha in linhas.items()
    ]
    return sorted(resultado, key=lambda r: (-r.valor_total, r.nome))


def _somar(resumos: list[ResumoVendedora]) -> TotaisVendas:
    return TotaisVendas(
        quantidade_pedidos=sum(r.quantidade_pedidos for r in resumos),
        produtos_vendidos=sum(r.produtos_vendidos for r in resumos),
        valor_total=sum((r.valor_total for r in resumos), Decimal("0.00")),
        comissao_a_receber=sum((r.comissao_a_receber for r in resumos), Decimal("0.00")),
        comissao_pendente=sum((r.comissao_pendente for r in resumos), Decimal("0.00")),
    )


def _vendedora_ou_404(db: Session, id_vendedora: int) -> Usuario:
    usuario = db.get(Usuario, id_vendedora)
    if usuario is None or usuario.cargo != CARGO_VENDEDORA:
        raise NaoEncontradoError("Vendedora não encontrada.")
    return usuario


def vendas(
    db: Session, *, inicio: date | None, fim: date | None, id_vendedora: int | None
) -> RelatorioVendas:
    """RF28: quantidade, valor total e comissão por vendedora, num período."""
    inicio, fim = janela(inicio, fim)
    if id_vendedora is not None:
        _vendedora_ou_404(db, id_vendedora)
    resumos = _agregar(db, inicio, fim, id_vendedora)
    return RelatorioVendas(
        periodo=PeriodoRead(inicio=inicio, fim=fim), vendedoras=resumos, totais=_somar(resumos)
    )


def pedidos_do_periodo(
    db: Session,
    *,
    inicio: date | None,
    fim: date | None,
    id_vendedora: int | None,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Venda], int]:
    """Lista detalhada dos pedidos que compõem o relatório (RF28, critério 2)."""
    inicio, fim = janela(inicio, fim)
    if id_vendedora is not None:
        _vendedora_ou_404(db, id_vendedora)
    filtros = _filtros_de_pedidos(inicio, fim, id_vendedora, status)
    total = db.scalar(select(func.count()).select_from(Venda).where(*filtros)) or 0
    itens = db.scalars(
        pedido_service.consulta()
        .where(*filtros)
        .order_by(Venda.data_venda.desc(), Venda.id_venda.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(itens), total


def _filtros_de_pedidos(
    inicio: date, fim: date, id_vendedora: int | None, status: str | None
) -> list[Any]:
    filtros = _limites(inicio, fim)
    filtros.append(Venda.status == status if status else Venda.status.in_(STATUS_DE_VENDA))
    if id_vendedora is not None:
        filtros.append(Venda.id_usuario == id_vendedora)
    return filtros


# --- exportação -----------------------------------------------------------------


def _texto_seguro(valor: object) -> str:
    """Evita injeção de fórmula: Excel/Calc executam células de texto que começam com
    = + - @ (ou tab/enter). Um nome de cliente malicioso não pode virar fórmula."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


def _brl(valor: object) -> str:
    return f"{Decimal(str(valor)):.2f}".replace(".", ",")


def exportar(
    db: Session,
    *,
    formato: str,
    inicio: date | None,
    fim: date | None,
    id_vendedora: int | None,
) -> tuple[bytes, str, str]:
    """Devolve (conteúdo, tipo MIME, nome do arquivo).

    CSV traz os pedidos; XLSX traz o resumo por vendedora e os pedidos.
    """
    inicio, fim = janela(inicio, fim)
    relatorio = vendas(db, inicio=inicio, fim=fim, id_vendedora=id_vendedora)
    filtros = _filtros_de_pedidos(inicio, fim, id_vendedora, None)
    quantidade = db.scalar(select(func.count()).select_from(Venda).where(*filtros)) or 0
    if quantidade > MAX_LINHAS_EXPORTACAO:
        raise RegraInvalidaError("Período muito grande para exportar: reduza o intervalo.")
    pedidos = db.scalars(
        pedido_service.consulta().where(*filtros).order_by(Venda.data_venda, Venda.id_venda)
    ).all()

    cabecalho = [
        "Pedido",
        "Data",
        "Vendedora",
        "Cliente",
        "Situação",
        "Pagamento",
        "Produtos",
        "Total",
    ]
    linhas = [
        [
            v.id_venda,
            para_local(v.data_venda).strftime("%d/%m/%Y %H:%M"),
            _texto_seguro(v.usuario.nome),
            _texto_seguro(v.cliente.nome),
            v.status,
            _texto_seguro(v.forma_pagamento),
            sum(i.quantidade for i in v.itens),
            v.valor_total,
        ]
        for v in pedidos
    ]
    nome = f"vendas_{inicio:%Y%m%d}_{fim:%Y%m%d}"

    if formato == "csv":
        saida = StringIO()
        escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
        escritor.writerow(cabecalho)
        for linha in linhas:
            escritor.writerow([*linha[:-1], _brl(linha[-1])])
        # BOM para o Excel brasileiro abrir os acentos corretamente.
        return saida.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", f"{nome}.csv"

    pasta = Workbook()
    resumo = pasta.active
    assert resumo is not None
    resumo.title = "Resumo"
    resumo.append(["Período", f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"])
    resumo.append([])
    resumo.append(
        ["Vendedora", "Comissão %", "Pedidos", "Produtos", "Valor total", "A receber", "Pendente"]
    )
    for r in relatorio.vendedoras:
        resumo.append([
            _texto_seguro(r.nome), float(r.comissao_percentual or 0), r.quantidade_pedidos,
            r.produtos_vendidos, float(r.valor_total), float(r.comissao_a_receber),
            float(r.comissao_pendente),
        ])  # fmt: skip
    t = relatorio.totais
    resumo.append(["TOTAL", None, t.quantidade_pedidos, t.produtos_vendidos, float(t.valor_total),
                   float(t.comissao_a_receber), float(t.comissao_pendente)])  # fmt: skip
    for celula in resumo[3]:
        celula.font = Font(bold=True)

    aba = pasta.create_sheet("Pedidos")
    aba.append(cabecalho)
    for celula in aba[1]:
        celula.font = Font(bold=True)
    for linha in linhas:
        aba.append([*linha[:-1], float(linha[-1])])
    for coluna in aba.iter_cols(min_col=8, max_col=8, min_row=2):
        for celula in coluna:
            celula.number_format = "#,##0.00"

    buffer = BytesIO()
    pasta.save(buffer)
    tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return buffer.getvalue(), tipo, f"{nome}.xlsx"
