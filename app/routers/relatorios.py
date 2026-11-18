from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from app.api.deps import AdminAtual, DbSession
from app.schemas.comum import Pagina
from app.schemas.pedido import PedidoRead
from app.schemas.relatorio import Analise, Dashboard, RelatorioVendas
from app.services import pedido as pedido_service
from app.services import relatorio as relatorio_service

router = APIRouter(prefix="/relatorios", tags=["relatórios"])

IdVendedora = Annotated[int | None, Query(gt=0, description="Filtra pela responsável")]
CargoFiltro = Literal["vendedora", "administradora"]


@router.get("/dashboard", response_model=Dashboard)
def dashboard(db: DbSession, _admin: AdminAtual) -> Dashboard:
    """Vendas dos últimos 30 dias (RF27). Somente a administradora.

    Conta pedidos confirmados e entregues. A comissão considera o percentual atual de cada
    vendedora: «comissoes» sobre os entregues e «comissoes_pendentes» sobre os confirmados.
    """
    return relatorio_service.dashboard(db)


@router.get("/analise", response_model=Analise)
def analise(
    db: DbSession,
    _admin: AdminAtual,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    id_vendedora: IdVendedora = None,
    agrupar: Literal["dia", "semana", "mes"] | None = None,
    cargo: CargoFiltro | None = None,
) -> Analise:
    """Dados dos gráficos para o filtro escolhido: vendas ao longo do tempo, por forma de
    pagamento, por vendedora, produtos e clientes que mais compram e vendas por bairro.

    Sem datas, usa os últimos 30 dias. Sem `agrupar`, o servidor escolhe dia, semana ou mês
    conforme o tamanho do período. Conta pedidos confirmados e entregues.
    """
    return relatorio_service.analise(
        db,
        inicio=data_inicio,
        fim=data_fim,
        id_vendedora=id_vendedora,
        agrupar=agrupar,
        cargo=cargo,
    )


@router.get("/vendas", response_model=RelatorioVendas)
def vendas_por_vendedora(
    db: DbSession,
    _admin: AdminAtual,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    id_vendedora: IdVendedora = None,
    cargo: CargoFiltro | None = None,
) -> RelatorioVendas:
    """Quantidade, valor total e comissão por vendedora, num período (RF28).

    Sem datas, usa os últimos 30 dias. O período máximo é de 1 ano.
    """
    return relatorio_service.vendas(
        db, inicio=data_inicio, fim=data_fim, id_vendedora=id_vendedora, cargo=cargo
    )


@router.get("/vendas/pedidos", response_model=Pagina[PedidoRead])
def pedidos_do_relatorio(
    db: DbSession,
    _admin: AdminAtual,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    id_vendedora: IdVendedora = None,
    status: Literal["em_aberto", "confirmado", "entregue", "cancelado"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    cargo: CargoFiltro | None = None,
) -> Pagina[PedidoRead]:
    """Lista detalhada de pedidos do período (RF28). Sem `status`, só confirmados e entregues."""
    vendas, total = relatorio_service.pedidos_do_periodo(
        db,
        inicio=data_inicio,
        fim=data_fim,
        id_vendedora=id_vendedora,
        status=status,
        limit=limit,
        offset=offset,
        cargo=cargo,
    )
    return Pagina[PedidoRead](
        itens=[pedido_service.montar(v) for v in vendas], total=total, limit=limit, offset=offset
    )


@router.get(
    "/vendas/exportar",
    response_class=Response,
    responses={200: {"description": "Arquivo .xlsx (resumo + pedidos) ou .csv (pedidos)"}},
)
def exportar_vendas(
    db: DbSession,
    _admin: AdminAtual,
    formato: Literal["xlsx", "csv"] = "xlsx",
    data_inicio: date | None = None,
    data_fim: date | None = None,
    id_vendedora: IdVendedora = None,
    cargo: CargoFiltro | None = None,
) -> Response:
    """Baixa o relatório de vendas (RF28, critério 3). Células de texto são protegidas
    contra injeção de fórmula."""
    conteudo, tipo, nome = relatorio_service.exportar(
        db,
        formato=formato,
        inicio=data_inicio,
        fim=data_fim,
        id_vendedora=id_vendedora,
        cargo=cargo,
    )
    return Response(
        content=conteudo,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
