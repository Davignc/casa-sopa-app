from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import DbSession, OperadorAtual
from app.core.errors import ConflitoError, RegraInvalidaError
from app.schemas.comum import Pagina
from app.schemas.pedido import (
    ContagemPedidos,
    PedidoCreate,
    PedidoRead,
    PedidoUpdate,
    StatusUpdate,
    ViaCupom,
)
from app.services import cupom as cupom_service
from app.services import logo as logo_service
from app.services import pedido as pedido_service

router = APIRouter(prefix="/pedidos", tags=["pedidos"])

IdPedido = Annotated[int, Path(gt=0)]
StatusFiltro = Literal["em_aberto", "confirmado", "entregue", "cancelado"]


@router.post("", response_model=PedidoRead, status_code=status.HTTP_201_CREATED)
def criar_pedido(dados: PedidoCreate, db: DbSession, operador: OperadorAtual) -> PedidoRead:
    """Cadastra o pedido (RF11). Nasce «em aberto».

    Envie só os produtos e as quantidades: o preço e o total são calculados pelo servidor.
    A vendedora responsável é a usuária logada (RN09).
    """
    return pedido_service.montar(pedido_service.criar(db, dados, operador))


@router.get("", response_model=Pagina[PedidoRead])
def listar_pedidos(
    db: DbSession,
    _op: OperadorAtual,
    status_pedido: Annotated[StatusFiltro | None, Query(alias="status")] = None,
    id_cliente: Annotated[int | None, Query(gt=0)] = None,
    id_vendedora: Annotated[int | None, Query(gt=0)] = None,
    busca: Annotated[str | None, Query(max_length=100, description="Nome do cliente ou nº")] = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[PedidoRead]:
    """Lista os pedidos com todas as informações (RF14), do mais recente ao mais antigo."""
    if data_inicio and data_fim and data_inicio > data_fim:
        raise RegraInvalidaError("A data inicial não pode ser depois da data final.")
    vendas, total = pedido_service.listar(
        db,
        status=status_pedido,
        id_cliente=id_cliente,
        id_vendedora=id_vendedora,
        busca=busca,
        data_inicio=data_inicio,
        data_fim=data_fim,
        limit=limit,
        offset=offset,
    )
    return Pagina[PedidoRead](
        itens=[pedido_service.montar(v) for v in vendas], total=total, limit=limit, offset=offset
    )


# "/contagem" precisa vir antes de "/{id_pedido}", senão "contagem" seria lido como id.
@router.get("/contagem", response_model=ContagemPedidos)
def contar_pedidos(
    db: DbSession,
    _op: OperadorAtual,
    id_cliente: Annotated[int | None, Query(gt=0)] = None,
    id_vendedora: Annotated[int | None, Query(gt=0)] = None,
    busca: Annotated[str | None, Query(max_length=100)] = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> ContagemPedidos:
    """Quantos pedidos há em cada situação, com os mesmos filtros da listagem."""
    if data_inicio and data_fim and data_inicio > data_fim:
        raise RegraInvalidaError("A data inicial não pode ser depois da data final.")
    return pedido_service.contar_por_status(
        db,
        id_cliente=id_cliente,
        id_vendedora=id_vendedora,
        busca=busca,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@router.get("/{id_pedido}", response_model=PedidoRead)
def ler_pedido(id_pedido: IdPedido, db: DbSession, _op: OperadorAtual) -> PedidoRead:
    return pedido_service.montar(pedido_service.obter_ou_404(db, id_pedido))


@router.patch("/{id_pedido}", response_model=PedidoRead)
def atualizar_pedido(
    id_pedido: IdPedido, dados: PedidoUpdate, db: DbSession, operador: OperadorAtual
) -> PedidoRead:
    """Edita o pedido (RF12). O total é recalculado; a vendedora responsável não muda.

    Em aberto: tudo pode mudar. Confirmado: só pagamento, endereço e observação.
    Entregue e cancelado: nada muda.
    """
    return pedido_service.montar(pedido_service.atualizar(db, id_pedido, dados, operador))


@router.delete("/{id_pedido}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_pedido(id_pedido: IdPedido, db: DbSession, operador: OperadorAtual) -> Response:
    """Exclui o pedido lançado por engano (RF13). Só «em aberto»; senão, 409.

    A confirmação ("tem certeza?") é feita pelo front antes de chamar.
    """
    pedido_service.excluir(db, id_pedido, operador)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{id_pedido}/status", response_model=PedidoRead)
def alterar_status(
    id_pedido: IdPedido, dados: StatusUpdate, db: DbSession, operador: OperadorAtual
) -> PedidoRead:
    """Muda o status (RF26): em aberto → confirmado → entregue; cancelar vale até a entrega.

    Confirmar baixa o estoque (409 se faltar). Cancelar um pedido confirmado devolve o estoque.
    """
    return pedido_service.montar(
        pedido_service.alterar_status(db, id_pedido, dados.status, operador)
    )


@router.get(
    "/{id_pedido}/cupom",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "Cupom em PDF"}},
)
def emitir_cupom(
    id_pedido: IdPedido,
    db: DbSession,
    _op: OperadorAtual,
    via: Annotated[ViaCupom, Query(description="Destinatário da via")] = "todas",
) -> Response:
    """Cupom não fiscal em PDF (RF15). `via`: interna, entregador, cliente ou todas (RF16).

    Pode ser emitido quantas vezes for preciso. Pedido cancelado não gera cupom.
    """
    pedido = pedido_service.montar(pedido_service.obter_ou_404(db, id_pedido))
    if pedido.status == "cancelado":
        raise ConflitoError("Pedido cancelado não gera cupom.")
    pdf = cupom_service.gerar_cupom_pdf(pedido, via, logo_service.obter_logo())
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="pedido-{id_pedido}-{via}.pdf"'},
    )
