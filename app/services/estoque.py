"""Estoque: entradas, saídas, histórico e alertas (RF21-RF25, RN14).

Toda alteração de ``estoque_atual`` passa por aqui e gera uma ``Movimentacao``, então a
soma do histórico sempre bate com a quantidade do produto. Os produtos são lidos com
``SELECT ... FOR UPDATE`` (em PostgreSQL) para que dois pedidos simultâneos não vendam o
mesmo item duas vezes.
"""

import logging
from collections.abc import Iterable
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflitoError, NaoEncontradoError, RegraInvalidaError
from app.core.periodos import (
    Agrupamento,
    escolher_agrupamento,
    gerar_baldes,
    inicio_do_balde,
    janela,
)
from app.core.tempo import fim_do_dia_exclusivo_utc, inicio_do_dia_utc, para_local
from app.models.movimentacao import (
    REF_AJUSTE_MANUAL,
    TIPO_ENTRADA,
    TIPO_SAIDA,
    Movimentacao,
)
from app.models.produto import Produto
from app.models.usuario import Usuario
from app.schemas.produto import (
    EntradaEstoque,
    MovimentacaoRead,
    MovimentacaoResultado,
    PontoMovimentacao,
    ProdutoRead,
    ResumoMovimentacoes,
    SaidaEstoque,
)

logger = logging.getLogger("casa_sopa.estoque")

LIMITE_ESTOQUE = 2_000_000_000  # cabe no INTEGER do banco, com folga


def travar_produtos(db: Session, ids: Iterable[int]) -> dict[int, Produto]:
    """Carrega os produtos já bloqueados, sempre em ordem de id (evita deadlock)."""
    ordenados = sorted(set(ids))
    produtos = db.scalars(
        select(Produto).where(Produto.id_produto.in_(ordenados)).order_by(Produto.id_produto)
        .with_for_update()
    ).all()  # fmt: skip
    achados = {p.id_produto: p for p in produtos}
    faltando = [i for i in ordenados if i not in achados]
    if faltando:
        raise NaoEncontradoError(f"Produto {faltando[0]} não encontrado.")
    return achados


def movimentar(
    db: Session,
    produto: Produto,
    *,
    tipo: str,
    quantidade: int,
    referencia: str,
    observacao: str | None,
    id_venda: int | None = None,
) -> Movimentacao:
    """Aplica a variação ao produto (já bloqueado) e registra no histórico. Sem commit."""
    novo = produto.estoque_atual + (quantidade if tipo == TIPO_ENTRADA else -quantidade)
    if novo < 0:
        raise ConflitoError(
            f"Estoque insuficiente de «{produto.nome}»: "
            f"disponível {produto.estoque_atual}, solicitado {quantidade}."
        )
    if novo > LIMITE_ESTOQUE:
        raise RegraInvalidaError("A quantidade em estoque ficaria acima do limite permitido.")
    produto.estoque_atual = novo
    mov = Movimentacao(
        tipo_movimentacao=tipo,
        quantidade=quantidade,
        tipo_referencia=referencia,
        observacao=observacao,
        id_venda=id_venda,
        id_produto=produto.id_produto,
    )
    mov.produto = produto
    db.add(mov)
    return mov


def com_responsavel(texto: str | None, ator: Usuario) -> str:
    """Anexa quem fez a operação. O modelo de dados não tem coluna de usuário em
    Movimentacoes, então o responsável vai junto da observação (RF22)."""
    sufixo = f"[por {ator.nome[:40]}]"
    return f"{texto} {sufixo}" if texto else sufixo


def _ler_mov(mov: Movimentacao) -> MovimentacaoRead:
    return MovimentacaoRead(
        id_movimentacao=mov.id_movimentacao,
        id_produto=mov.id_produto,
        nome_produto=mov.produto.nome,
        tipo_movimentacao=mov.tipo_movimentacao,
        quantidade=mov.quantidade,
        tipo_referencia=mov.tipo_referencia,
        id_venda=mov.id_venda,
        observacao=mov.observacao,
        data_movimentacao=mov.data_movimentacao,
    )


def _resultado(db: Session, mov: Movimentacao) -> MovimentacaoResultado:
    db.commit()
    db.refresh(mov)
    db.refresh(mov.produto)
    return MovimentacaoResultado(
        movimentacao=_ler_mov(mov), produto=ProdutoRead.model_validate(mov.produto)
    )


def _produto_ativo(db: Session, id_produto: int) -> Produto:
    produto = travar_produtos(db, [id_produto])[id_produto]
    if not produto.is_ativo:
        raise ConflitoError("O produto está inativo. Reative-o antes de movimentar o estoque.")
    return produto


def registrar_entrada(db: Session, dados: EntradaEstoque, ator: Usuario) -> MovimentacaoResultado:
    """RF21: soma ao estoque e registra data, quantidade e produto."""
    produto = _produto_ativo(db, dados.id_produto)
    mov = movimentar(
        db,
        produto,
        tipo=TIPO_ENTRADA,
        quantidade=dados.quantidade,
        referencia=dados.tipo,
        observacao=com_responsavel(dados.observacao, ator),
    )
    logger.info(
        "Entrada: produto=%s qtd=%s por usuario=%s",
        produto.id_produto,
        dados.quantidade,
        ator.id_usuario,
    )
    return _resultado(db, mov)


def registrar_saida(db: Session, dados: SaidaEstoque, ator: Usuario) -> MovimentacaoResultado:
    """RF22: baixa por perda ou ajuste, com motivo e responsável."""
    produto = _produto_ativo(db, dados.id_produto)
    mov = movimentar(
        db,
        produto,
        tipo=TIPO_SAIDA,
        quantidade=dados.quantidade,
        referencia=REF_AJUSTE_MANUAL,
        observacao=com_responsavel(dados.motivo, ator),
    )
    logger.info(
        "Saída: produto=%s qtd=%s por usuario=%s",
        produto.id_produto,
        dados.quantidade,
        ator.id_usuario,
    )
    return _resultado(db, mov)


def listar_movimentacoes(
    db: Session,
    *,
    id_produto: int | None,
    tipo: str | None,
    data_inicio: date | None,
    data_fim: date | None,
    limit: int,
    offset: int,
) -> tuple[list[MovimentacaoRead], int]:
    filtros = []
    if id_produto is not None:
        filtros.append(Movimentacao.id_produto == id_produto)
    if tipo is not None:
        filtros.append(Movimentacao.tipo_movimentacao == tipo)
    if data_inicio is not None:
        filtros.append(Movimentacao.data_movimentacao >= inicio_do_dia_utc(data_inicio))
    if data_fim is not None:
        filtros.append(Movimentacao.data_movimentacao < fim_do_dia_exclusivo_utc(data_fim))

    total = db.scalar(select(func.count()).select_from(Movimentacao).where(*filtros)) or 0
    movs = db.scalars(
        select(Movimentacao)
        .where(*filtros)
        .order_by(Movimentacao.data_movimentacao.desc(), Movimentacao.id_movimentacao.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [_ler_mov(m) for m in movs], total


def listar_alertas(db: Session) -> list[Produto]:
    """RF23: produtos ativos no mínimo (ou abaixo), os mais críticos primeiro."""
    return list(
        db.scalars(
            select(Produto)
            .where(Produto.is_ativo.is_(True), Produto.estoque_atual <= Produto.estoque_minimo)
            .order_by(Produto.estoque_atual - Produto.estoque_minimo, Produto.nome)
        ).all()
    )


def resumo_movimentacoes(
    db: Session,
    *,
    id_produto: int | None,
    data_inicio: date | None,
    data_fim: date | None,
    agrupar: str | None,
) -> ResumoMovimentacoes:
    """Entradas e saídas por dia, semana ou mês, para o gráfico. Sem datas: últimos 30 dias."""
    inicio, fim = janela(data_inicio, data_fim)
    if id_produto is not None and db.get(Produto, id_produto) is None:
        raise NaoEncontradoError("Produto não encontrado.")
    agrupamento: Agrupamento = agrupar or escolher_agrupamento(inicio, fim)  # type: ignore[assignment]
    filtros = [
        Movimentacao.data_movimentacao >= inicio_do_dia_utc(inicio),
        Movimentacao.data_movimentacao < fim_do_dia_exclusivo_utc(fim),
    ]
    if id_produto is not None:
        filtros.append(Movimentacao.id_produto == id_produto)
    linhas = db.execute(
        select(
            Movimentacao.data_movimentacao, Movimentacao.tipo_movimentacao, Movimentacao.quantidade
        ).where(*filtros)
    ).all()
    baldes = {b: [0, 0] for b in gerar_baldes(inicio, fim, agrupamento)}
    for momento, tipo, quantidade in linhas:
        balde = inicio_do_balde(para_local(momento).date(), agrupamento)
        if balde in baldes:
            baldes[balde][0 if tipo == TIPO_ENTRADA else 1] += quantidade
    entradas = sum(v[0] for v in baldes.values())
    saidas = sum(v[1] for v in baldes.values())
    return ResumoMovimentacoes(
        periodo_inicio=inicio,
        periodo_fim=fim,
        agrupamento=agrupamento,
        total_entradas=entradas,
        total_saidas=saidas,
        saldo_do_periodo=entradas - saidas,
        serie=[PontoMovimentacao(inicio=b, entradas=v[0], saidas=v[1]) for b, v in baldes.items()],
    )
