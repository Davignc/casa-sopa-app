from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import AdminAtual, DbSession, OperadorAtual
from app.core.errors import RegraInvalidaError
from app.schemas.comum import Pagina
from app.schemas.produto import (
    EntradaEstoque,
    MovimentacaoRead,
    MovimentacaoResultado,
    ProdutoRead,
    SaidaEstoque,
)
from app.services import estoque as estoque_service

router = APIRouter(prefix="/estoque", tags=["estoque"])


@router.post("/entradas", response_model=MovimentacaoResultado, status_code=status.HTTP_201_CREATED)
def registrar_entrada(
    dados: EntradaEstoque, db: DbSession, admin: AdminAtual
) -> MovimentacaoResultado:
    """Registra entrada de produtos e atualiza a quantidade (RF21). Somente a administradora."""
    return estoque_service.registrar_entrada(db, dados, admin)


@router.post("/saidas", response_model=MovimentacaoResultado, status_code=status.HTTP_201_CREATED)
def registrar_saida(dados: SaidaEstoque, db: DbSession, admin: AdminAtual) -> MovimentacaoResultado:
    """Registra saída por perda ou ajuste, com motivo (RF22). Somente a administradora.

    Retorna 409 se a quantidade pedida passar do que há em estoque.
    """
    return estoque_service.registrar_saida(db, dados, admin)


@router.get("/movimentacoes", response_model=Pagina[MovimentacaoRead])
def listar_movimentacoes(
    db: DbSession,
    _admin: AdminAtual,
    id_produto: Annotated[int | None, Query(gt=0)] = None,
    tipo: Literal["entrada", "saida"] | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[MovimentacaoRead]:
    """Histórico de entradas e saídas, do mais recente para o mais antigo."""
    if data_inicio and data_fim and data_inicio > data_fim:
        raise RegraInvalidaError("A data inicial não pode ser depois da data final.")
    itens, total = estoque_service.listar_movimentacoes(
        db,
        id_produto=id_produto,
        tipo=tipo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        limit=limit,
        offset=offset,
    )
    return Pagina[MovimentacaoRead](itens=itens, total=total, limit=limit, offset=offset)


@router.get("/alertas", response_model=list[ProdutoRead])
def listar_alertas(db: DbSession, _op: OperadorAtual) -> list[ProdutoRead]:
    """Produtos com estoque no mínimo ou abaixo, os mais críticos primeiro (RF23, RN14)."""
    return [ProdutoRead.model_validate(p) for p in estoque_service.listar_alertas(db)]
