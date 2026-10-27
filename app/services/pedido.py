"""Pedidos: criação, edição, exclusão, status e estoque (RF11-RF16, RF24, RF26, RN09-RN13).

Princípios:
* o servidor calcula preço, subtotal e total — nada disso vem do cliente da API;
* o estoque só muda na confirmação (baixa) e no cancelamento de pedido confirmado
  (devolução), sempre gravando o histórico em ``movimentacoes``;
* as linhas do pedido e do produto são bloqueadas (``FOR UPDATE``) para que dois
  usuários não confirmem o mesmo pedido, nem vendam o mesmo estoque, ao mesmo tempo.
"""

import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import (
    AcessoNegadoError,
    ConflitoError,
    NaoEncontradoError,
    RegraInvalidaError,
)
from app.core.formatacao import formatar_endereco
from app.core.tempo import agora_utc, fim_do_dia_exclusivo_utc, inicio_do_dia_utc
from app.models.cliente import Cliente
from app.models.cliente_endereco import ClienteEndereco
from app.models.item_venda import ItemVenda
from app.models.movimentacao import REF_VENDA, TIPO_ENTRADA, TIPO_SAIDA
from app.models.produto import Produto
from app.models.usuario import CARGO_ADMINISTRADORA, CARGO_VENDEDORA, Usuario
from app.models.venda import (
    STATUS_CANCELADO,
    STATUS_CONFIRMADO,
    STATUS_EM_ABERTO,
    STATUS_ENTREGUE,
    TRANSICOES,
    Venda,
)
from app.schemas.pedido import (
    ClientePedido,
    EnderecoPedido,
    ItemEntrada,
    ItemRead,
    PedidoCreate,
    PedidoRead,
    PedidoUpdate,
    VendedoraPedido,
)
from app.services import estoque as estoque_service

logger = logging.getLogger("casa_sopa.pedidos")

_CENTAVOS = Decimal("0.01")
_TOTAL_MAXIMO = Decimal("99999999.99")  # limite do NUMERIC(10, 2)


# --- leitura -----------------------------------------------------------------


def consulta() -> Any:
    return select(Venda).options(
        selectinload(Venda.itens).selectinload(ItemVenda.produto),
        selectinload(Venda.cliente),
        selectinload(Venda.usuario),
        selectinload(Venda.endereco_entrega).selectinload(ClienteEndereco.endereco),
    )


def obter_ou_404(db: Session, id_pedido: int, *, travar: bool = False) -> Venda:
    consulta_do_pedido = consulta().where(Venda.id_venda == id_pedido)
    if travar:
        consulta_do_pedido = consulta_do_pedido.with_for_update().execution_options(
            populate_existing=True
        )
    venda = db.scalar(consulta_do_pedido)
    if venda is None:
        raise NaoEncontradoError("Pedido não encontrado.")
    return venda


def montar(venda: Venda) -> PedidoRead:
    vinculo = venda.endereco_entrega
    e = vinculo.endereco
    itens = sorted(venda.itens, key=lambda i: i.id_produto)
    return PedidoRead(
        id_pedido=venda.id_venda,
        status=venda.status,
        data_venda=venda.data_venda,
        forma_pagamento=venda.forma_pagamento,
        observacao=venda.observacao,
        data_pagamento=venda.data_pagamento,
        valor_total=venda.valor_total,
        total_produtos=sum(i.quantidade for i in itens),
        cliente=ClientePedido(
            id_cliente=venda.cliente.id_cliente,
            nome=venda.cliente.nome,
            telefone=venda.cliente.telefone,
        ),
        vendedora=VendedoraPedido(id_usuario=venda.usuario.id_usuario, nome=venda.usuario.nome),
        endereco_entrega=EnderecoPedido(
            id_endereco=e.id_endereco,
            endereco_formatado=formatar_endereco(
                tipo_logradouro=e.tipo_logradouro,
                nome_logradouro=e.nome_logradouro,
                numero=vinculo.numero,
                complemento=vinculo.complemento,
                bairro=e.bairro,
                cidade=e.cidade,
                cep=e.cep,
            ),
            apelido=vinculo.apelido,
            referencia=vinculo.referencia,
        ),
        itens=[
            ItemRead(
                id_produto=i.id_produto,
                nome_produto=i.produto.nome,
                quantidade=i.quantidade,
                preco_unitario=i.preco_unitario_v,
                subtotal=i.subtotal,
            )
            for i in itens
        ],
    )


def listar(
    db: Session,
    *,
    status: str | None,
    id_cliente: int | None,
    id_vendedora: int | None,
    busca: str | None,
    data_inicio: date | None,
    data_fim: date | None,
    limit: int,
    offset: int,
) -> tuple[list[Venda], int]:
    """RF14: do mais recente para o mais antigo. Datas valem para a data da venda."""
    filtros: list[Any] = []
    if status is not None:
        filtros.append(Venda.status == status)
    if id_cliente is not None:
        filtros.append(Venda.id_cliente == id_cliente)
    if id_vendedora is not None:
        filtros.append(Venda.id_usuario == id_vendedora)
    if data_inicio is not None:
        filtros.append(Venda.data_venda >= inicio_do_dia_utc(data_inicio))
    if data_fim is not None:
        filtros.append(Venda.data_venda < fim_do_dia_exclusivo_utc(data_fim))
    if busca and busca.strip():
        termo = busca.strip()
        escapado = termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        por_cliente = Venda.id_cliente.in_(
            select(Cliente.id_cliente).where(Cliente.nome.ilike(f"%{escapado}%", escape="\\"))
        )
        if termo.isdigit() and len(termo) <= 9:  # também aceita o nº do pedido
            filtros.append(or_(por_cliente, Venda.id_venda == int(termo)))
        else:
            filtros.append(por_cliente)

    total = db.scalar(select(func.count()).select_from(Venda).where(*filtros)) or 0
    vendas = db.scalars(
        consulta()
        .where(*filtros)
        .order_by(Venda.data_venda.desc(), Venda.id_venda.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(vendas), total


# --- validações compartilhadas -----------------------------------------------


def _cliente_ativo(db: Session, id_cliente: int) -> Cliente:
    cliente = db.get(Cliente, id_cliente)
    if cliente is None:
        raise NaoEncontradoError("Cliente não encontrado.")
    if not cliente.is_ativo:
        raise RegraInvalidaError("O cliente está inativo. Reative o cadastro para criar pedidos.")
    return cliente


def _endereco_do_cliente(db: Session, id_cliente: int, id_endereco: int) -> ClienteEndereco:
    """RM05: o endereço de entrega precisa ser um dos endereços (ativos) do cliente."""
    vinculo = db.get(ClienteEndereco, (id_cliente, id_endereco))
    if vinculo is None or not vinculo.endereco.is_ativo:
        raise RegraInvalidaError("O endereço de entrega precisa ser um dos endereços do cliente.")
    return vinculo


def _montar_itens(db: Session, entradas: list[ItemEntrada]) -> tuple[list[ItemVenda], Decimal]:
    """Preço e subtotal vêm do cadastro do produto (nunca do cliente da API)."""
    ids = [e.id_produto for e in entradas]
    produtos = {
        p.id_produto: p for p in db.scalars(select(Produto).where(Produto.id_produto.in_(ids)))
    }
    itens: list[ItemVenda] = []
    total = Decimal("0.00")
    for entrada in entradas:
        produto = produtos.get(entrada.id_produto)
        if produto is None:
            raise RegraInvalidaError(f"Produto {entrada.id_produto} não encontrado.")
        if not produto.is_ativo:
            raise RegraInvalidaError(f"O produto «{produto.nome}» está inativo.")
        preco = Decimal(produto.preco_unitario).quantize(_CENTAVOS, ROUND_HALF_UP)
        subtotal = (preco * entrada.quantidade).quantize(_CENTAVOS, ROUND_HALF_UP)
        total += subtotal
        itens.append(
            ItemVenda(
                id_produto=produto.id_produto,
                preco_unitario_v=preco,
                quantidade=entrada.quantidade,
                subtotal=subtotal,
            )
        )
    if total > _TOTAL_MAXIMO:
        raise RegraInvalidaError("O valor total do pedido ficou acima do máximo permitido.")
    return itens, total


def _vendedora_responsavel(db: Session, dados: PedidoCreate, ator: Usuario) -> Usuario:
    """RN09: a responsável é quem registra. Só a administradora registra em nome de outra."""
    if dados.id_vendedora is None or dados.id_vendedora == ator.id_usuario:
        return ator
    if ator.cargo != CARGO_ADMINISTRADORA:
        raise AcessoNegadoError("Somente a administradora pode registrar pedido em nome de outra.")
    vendedora = db.get(Usuario, dados.id_vendedora)
    if vendedora is None or not vendedora.is_ativo or vendedora.cargo != CARGO_VENDEDORA:
        raise RegraInvalidaError("A vendedora informada não existe ou está inativa.")
    return vendedora


# --- criação, edição, exclusão -----------------------------------------------


def criar(db: Session, dados: PedidoCreate, ator: Usuario) -> Venda:
    """RF11: valida, calcula o total e salva como «em aberto» (sem mexer no estoque)."""
    responsavel = _vendedora_responsavel(db, dados, ator)
    cliente = _cliente_ativo(db, dados.id_cliente)
    _endereco_do_cliente(db, cliente.id_cliente, dados.id_endereco)
    itens, total = _montar_itens(db, dados.itens)

    venda = Venda(
        data_venda=agora_utc(),
        valor_total=total,
        forma_pagamento=dados.forma_pagamento,
        status=STATUS_EM_ABERTO,
        observacao=dados.observacao,
        data_pagamento=dados.data_pagamento,
        id_cliente=cliente.id_cliente,
        id_usuario=responsavel.id_usuario,
        id_endereco=dados.id_endereco,
    )
    venda.itens = itens
    db.add(venda)
    db.commit()
    logger.info("Pedido criado: id=%s por usuario=%s", venda.id_venda, ator.id_usuario)
    return obter_ou_404(db, venda.id_venda)


def atualizar(db: Session, id_pedido: int, dados: PedidoUpdate) -> Venda:
    """RF12. Em aberto: tudo editável. Confirmado: só pagamento, endereço e observação
    (mexer nos produtos exigiria acertar o estoque: cancele e refaça). Entregue e
    cancelado são definitivos. A vendedora responsável nunca muda (RN10)."""
    venda = obter_ou_404(db, id_pedido, travar=True)
    if venda.status in (STATUS_ENTREGUE, STATUS_CANCELADO):
        raise ConflitoError(f"Pedido {venda.status} não pode mais ser alterado.")
    campos = dados.model_dump(exclude_unset=True)
    if venda.status == STATUS_CONFIRMADO and ("id_cliente" in campos or "itens" in campos):
        raise ConflitoError(
            "Pedido confirmado: só é possível alterar forma de pagamento, endereço, "
            "observação e data de pagamento. Para mudar cliente ou produtos, cancele e refaça."
        )

    id_cliente = campos.get("id_cliente", venda.id_cliente)
    if "id_cliente" in campos and campos["id_cliente"] != venda.id_cliente:
        _cliente_ativo(db, id_cliente)
        if "id_endereco" not in campos:
            raise RegraInvalidaError("Ao trocar o cliente, informe também o endereço de entrega.")
    id_endereco = campos.get("id_endereco", venda.id_endereco)
    if "id_cliente" in campos or "id_endereco" in campos:
        _endereco_do_cliente(db, id_cliente, id_endereco)

    if "itens" in campos:
        novos, total = _montar_itens(db, dados.itens or [])
        db.execute(delete(ItemVenda).where(ItemVenda.id_venda == venda.id_venda))
        db.flush()
        db.expire(venda, ["itens"])
        venda.itens.extend(novos)
        venda.valor_total = total

    for campo in ("id_cliente", "id_endereco", "forma_pagamento", "observacao", "data_pagamento"):
        if campo in campos:
            setattr(venda, campo, campos[campo])
    db.commit()
    return obter_ou_404(db, id_pedido)


def excluir(db: Session, id_pedido: int) -> None:
    """RF13/RN11: só pedidos «em aberto» (que nunca mexeram no estoque)."""
    venda = obter_ou_404(db, id_pedido, travar=True)
    if venda.status != STATUS_EM_ABERTO:
        raise ConflitoError("Só é possível excluir pedidos em aberto.")
    db.delete(venda)
    db.commit()
    logger.info("Pedido excluído: id=%s", id_pedido)


# --- status e estoque --------------------------------------------------------


def alterar_status(db: Session, id_pedido: int, novo: str, ator: Usuario) -> Venda:
    """RF26 + RF24: confirmar baixa o estoque; cancelar pedido confirmado devolve."""
    venda = obter_ou_404(db, id_pedido, travar=True)
    atual = venda.status
    if novo == atual:
        raise ConflitoError(f"O pedido já está {atual}.")
    if novo not in TRANSICOES[atual]:
        raise ConflitoError(f"Não é possível mudar o pedido de «{atual}» para «{novo}».")

    if novo == STATUS_CONFIRMADO:
        _baixar_estoque(db, venda)
    elif novo == STATUS_CANCELADO and atual == STATUS_CONFIRMADO:
        _devolver_estoque(db, venda)

    venda.status = novo
    db.commit()
    logger.info("Pedido %s: %s -> %s (usuario=%s)", id_pedido, atual, novo, ator.id_usuario)
    return obter_ou_404(db, id_pedido)


def _baixar_estoque(db: Session, venda: Venda) -> None:
    produtos = estoque_service.travar_produtos(db, [i.id_produto for i in venda.itens])
    problemas: list[str] = []
    for item in sorted(venda.itens, key=lambda i: i.id_produto):
        produto = produtos[item.id_produto]
        if not produto.is_ativo:
            problemas.append(f"«{produto.nome}» está inativo")
        elif produto.estoque_atual < item.quantidade:
            problemas.append(
                f"«{produto.nome}» (disponível {produto.estoque_atual}, pedido {item.quantidade})"
            )
    if problemas:
        raise ConflitoError("Não dá para confirmar: " + "; ".join(problemas) + ".")

    for item in sorted(venda.itens, key=lambda i: i.id_produto):
        estoque_service.movimentar(
            db,
            produtos[item.id_produto],
            tipo=TIPO_SAIDA,
            quantidade=item.quantidade,
            referencia=REF_VENDA,
            observacao=f"Pedido #{venda.id_venda}",
            id_venda=venda.id_venda,
        )


def _devolver_estoque(db: Session, venda: Venda) -> None:
    produtos = estoque_service.travar_produtos(db, [i.id_produto for i in venda.itens])
    for item in sorted(venda.itens, key=lambda i: i.id_produto):
        estoque_service.movimentar(
            db,
            produtos[item.id_produto],
            tipo=TIPO_ENTRADA,
            quantidade=item.quantidade,
            referencia=REF_VENDA,
            observacao=f"Cancelamento do pedido #{venda.id_venda}",
            id_venda=venda.id_venda,
        )
