"""Cadastro de produtos (RF17-RF20, RF25)."""

import logging
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NaoEncontradoError
from app.models.movimentacao import REF_AJUSTE_MANUAL, TIPO_ENTRADA
from app.models.produto import Produto
from app.models.usuario import Usuario
from app.schemas.produto import ProdutoCreate, ProdutoUpdate
from app.services import estoque as estoque_service

logger = logging.getLogger("casa_sopa.produtos")


def obter_ou_404(db: Session, id_produto: int) -> Produto:
    produto = db.get(Produto, id_produto)
    if produto is None:
        raise NaoEncontradoError("Produto não encontrado.")
    return produto


def criar(db: Session, dados: ProdutoCreate, ator: Usuario) -> Produto:
    """Cria o produto; a quantidade inicial entra no histórico como a 1ª movimentação."""
    produto = Produto(
        nome=dados.nome,
        descricao=dados.descricao,
        preco_unitario=dados.preco_unitario,
        estoque_atual=0,
        estoque_minimo=dados.estoque_minimo,
    )
    db.add(produto)
    db.flush()
    if dados.estoque_inicial > 0:
        estoque_service.movimentar(
            db,
            produto,
            tipo=TIPO_ENTRADA,
            quantidade=dados.estoque_inicial,
            referencia=REF_AJUSTE_MANUAL,
            observacao=estoque_service.com_responsavel("Estoque inicial", ator),
        )
    db.commit()
    db.refresh(produto)
    logger.info("Produto criado: id=%s por usuario=%s", produto.id_produto, ator.id_usuario)
    return produto


def listar(
    db: Session,
    *,
    busca: str | None,
    apenas_alerta: bool,
    incluir_inativos: bool,
    limit: int,
    offset: int,
) -> tuple[list[Produto], int]:
    """RF20/RF25: nome, descrição, preço e quantidade. Inativados somem por padrão (RF19)."""
    filtros: list[Any] = []
    if not incluir_inativos:
        filtros.append(Produto.is_ativo.is_(True))
    if apenas_alerta:
        filtros.append(Produto.is_ativo.is_(True))
        filtros.append(Produto.estoque_atual <= Produto.estoque_minimo)
    if busca and busca.strip():
        escapado = busca.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        padrao = f"%{escapado}%"
        filtros.append(
            or_(
                Produto.nome.ilike(padrao, escape="\\"),
                Produto.descricao.ilike(padrao, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(Produto).where(*filtros)) or 0
    itens = db.scalars(
        select(Produto).where(*filtros).order_by(Produto.nome, Produto.id_produto)
        .limit(limit).offset(offset)
    ).all()  # fmt: skip
    return list(itens), total


def atualizar(db: Session, produto: Produto, dados: ProdutoUpdate) -> Produto:
    """RF18. O preço novo vale só para pedidos futuros: os itens já gravados guardam o seu."""
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(produto, campo, valor)
    db.commit()
    db.refresh(produto)
    return produto


def inativar(db: Session, produto: Produto) -> None:
    """RF19: exclusão lógica; o histórico de vendas e movimentações é preservado."""
    produto.is_ativo = False
    db.commit()


def reativar(db: Session, produto: Produto) -> Produto:
    produto.is_ativo = True
    db.commit()
    db.refresh(produto)
    return produto
