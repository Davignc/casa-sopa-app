from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import DbSession, OperadorAtual
from app.schemas.comum import Pagina
from app.schemas.produto import ProdutoCreate, ProdutoRead, ProdutoUpdate
from app.services import produto as produto_service

router = APIRouter(prefix="/produtos", tags=["produtos"])

IdProduto = Annotated[int, Path(gt=0)]


@router.post("", response_model=ProdutoRead, status_code=status.HTTP_201_CREATED)
def criar_produto(dados: ProdutoCreate, db: DbSession, operador: OperadorAtual) -> ProdutoRead:
    """Cadastra produto (RF17). A quantidade inicial entra no histórico de estoque."""
    return ProdutoRead.model_validate(produto_service.criar(db, dados, operador))


@router.get("", response_model=Pagina[ProdutoRead])
def listar_produtos(
    db: DbSession,
    _op: OperadorAtual,
    busca: Annotated[str | None, Query(max_length=100, description="Nome ou descrição")] = None,
    apenas_alerta: Annotated[bool, Query(description="Só os com estoque baixo")] = False,
    incluir_inativos: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[ProdutoRead]:
    """Lista com nome, descrição, preço e quantidade (RF20, RF25).

    `alerta_estoque_baixo` marca os produtos no mínimo ou abaixo (RF23).
    """
    itens, total = produto_service.listar(
        db,
        busca=busca,
        apenas_alerta=apenas_alerta,
        incluir_inativos=incluir_inativos,
        limit=limit,
        offset=offset,
    )
    return Pagina[ProdutoRead](
        itens=[ProdutoRead.model_validate(p) for p in itens],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{id_produto}", response_model=ProdutoRead)
def ler_produto(id_produto: IdProduto, db: DbSession, _op: OperadorAtual) -> ProdutoRead:
    return ProdutoRead.model_validate(produto_service.obter_ou_404(db, id_produto))


@router.patch("/{id_produto}", response_model=ProdutoRead)
def atualizar_produto(
    id_produto: IdProduto, dados: ProdutoUpdate, db: DbSession, _op: OperadorAtual
) -> ProdutoRead:
    """Altera nome, descrição, preço ou estoque mínimo (RF18).

    A quantidade em estoque não muda aqui: use as entradas e saídas de `/estoque`.
    """
    produto = produto_service.obter_ou_404(db, id_produto)
    return ProdutoRead.model_validate(produto_service.atualizar(db, produto, dados))


@router.delete("/{id_produto}", status_code=status.HTTP_204_NO_CONTENT)
def inativar_produto(id_produto: IdProduto, db: DbSession, _op: OperadorAtual) -> Response:
    """Inativa o produto (exclusão lógica, RF19). A confirmação é feita pelo front."""
    produto_service.inativar(db, produto_service.obter_ou_404(db, id_produto))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{id_produto}/reativar", response_model=ProdutoRead)
def reativar_produto(id_produto: IdProduto, db: DbSession, _op: OperadorAtual) -> ProdutoRead:
    produto = produto_service.obter_ou_404(db, id_produto)
    return ProdutoRead.model_validate(produto_service.reativar(db, produto))
