"""O banco precisa recusar sozinho o que o modelo (script SQL) proíbe.

Cada teste tenta gravar um dado inválido direto pelo ORM e espera ``IntegrityError``.
Assim, mesmo que uma regra falhe na API, o banco continua protegendo os dados.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Cliente,
    ClienteEndereco,
    Endereco,
    ItemVenda,
    Movimentacao,
    Produto,
    Usuario,
    Venda,
)

_contador = iter(range(1, 10_000))


def _n() -> int:
    return next(_contador)


def _grava(db, *objetos):
    """Grava dentro de um SAVEPOINT: se falhar, só ele é desfeito e a sessão segue usável."""
    with db.begin_nested():
        db.add_all(objetos)
        db.flush()


def _recusa(db, *objetos):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add_all(objetos)
        db.flush()


# --- fábricas de objetos válidos ---------------------------------------------


def novo_usuario(db, **kw) -> Usuario:
    n = _n()
    dados = {
        "nome": f"Usuária {n}",
        "email": f"u{n}@x.org",
        "telefone": f"1699{n:07d}",
        "senha": "hash",
        "cargo": "vendedora",
    }
    u = Usuario(**{**dados, **kw})
    _grava(db, u)
    return u


def novo_produto(db, **kw) -> Produto:
    dados = {
        "nome": f"Saco {_n()}",
        "descricao": "Saco de lixo",
        "preco_unitario": Decimal("10.00"),
        "estoque_atual": 100,
        "estoque_minimo": 10,
    }
    p = Produto(**{**dados, **kw})
    _grava(db, p)
    return p


def novo_cliente(db, usuario=None, **kw) -> Cliente:
    usuario = usuario or novo_usuario(db)
    n = _n()
    dados = {"nome": f"Cliente {n}", "telefone": f"1698{n:07d}", "id_usuario": usuario.id_usuario}
    c = Cliente(**{**dados, **kw})
    _grava(db, c)
    return c


def novo_endereco(db) -> Endereco:
    e = Endereco(
        cidade="Franca",
        bairro="Centro",
        nome_logradouro="Presidente Vargas",
        tipo_logradouro="Avenida",
        cep="14400000",
    )
    _grava(db, e)
    return e


def vincula(db, cliente, endereco) -> ClienteEndereco:
    v = ClienteEndereco(
        id_cliente=cliente.id_cliente,
        id_endereco=endereco.id_endereco,
        numero="100",
        complemento="",
        referencia="",
    )
    _grava(db, v)
    return v


def nova_venda(db, **kw) -> Venda:
    """Venda válida: cliente com endereço vinculado e vendedora."""
    vendedora = kw.pop("vendedora", None) or novo_usuario(db)
    cliente = kw.pop("cliente", None) or novo_cliente(db, vendedora)
    id_endereco = kw.pop("id_endereco", None)
    if id_endereco is None:
        endereco = novo_endereco(db)
        vincula(db, cliente, endereco)
        id_endereco = endereco.id_endereco
    dados = {
        "data_venda": datetime.now(UTC),
        "valor_total": Decimal("0.00"),
        "forma_pagamento": "pix",
        "status": "em_aberto",
        "id_cliente": cliente.id_cliente,
        "id_usuario": vendedora.id_usuario,
        "id_endereco": id_endereco,
    }
    v = Venda(**{**dados, **kw})
    _grava(db, v)
    return v


# --- Usuario -----------------------------------------------------------------


@pytest.mark.parametrize("comissao", [Decimal("-0.01"), Decimal("100.01"), Decimal("101")])
def test_comissao_fora_de_0_a_100_e_recusada(db, comissao):
    n = _n()
    _recusa(
        db,
        Usuario(
            nome="x",
            email=f"c{n}@x.org",
            telefone=f"1697{n:07d}",
            senha="h",
            cargo="vendedora",
            comissao=comissao,
        ),
    )


@pytest.mark.parametrize("comissao", [None, Decimal("0"), Decimal("100"), Decimal("7.50")])
def test_comissao_valida_e_aceita(db, comissao):
    novo_usuario(db, comissao=comissao)


def test_email_de_usuario_e_unico(db):
    novo_usuario(db, email="dup@x.org")
    n = _n()
    _recusa(
        db,
        Usuario(nome="x", email="dup@x.org", telefone=f"1696{n:07d}", senha="h", cargo="vendedora"),
    )


def test_telefone_de_usuario_e_unico(db):
    novo_usuario(db, telefone="16955554444")
    n = _n()
    _recusa(
        db,
        Usuario(
            nome="x", email=f"t{n}@x.org", telefone="16955554444", senha="h", cargo="vendedora"
        ),
    )


def test_usuario_nasce_ativo_por_padrao(db):
    assert novo_usuario(db).is_ativo is True


# --- Produto -----------------------------------------------------------------


@pytest.mark.parametrize("campo", ["preco_unitario", "estoque_atual", "estoque_minimo"])
def test_produto_com_valor_negativo_e_recusado(db, campo):
    dados = {
        "nome": "x", "descricao": "d", "preco_unitario": Decimal("1"),
        "estoque_atual": 1, "estoque_minimo": 1,
    }  # fmt: skip
    dados[campo] = -1
    _recusa(db, Produto(**dados))


def test_estoque_baixo_quando_atinge_o_minimo(db):
    assert novo_produto(db, estoque_atual=10, estoque_minimo=10).estoque_baixo is True
    assert novo_produto(db, estoque_atual=3, estoque_minimo=10).estoque_baixo is True
    assert novo_produto(db, estoque_atual=11, estoque_minimo=10).estoque_baixo is False


# --- Cliente / Endereco ------------------------------------------------------


def test_telefone_de_cliente_e_unico(db):
    novo_cliente(db, telefone="16944443333")
    _recusa(db, Cliente(nome="x", telefone="16944443333", id_usuario=novo_usuario(db).id_usuario))


def test_cliente_exige_usuario_que_cadastrou(db):
    _recusa(db, Cliente(nome="x", telefone="16933332222", id_usuario=987654))


def test_vinculo_cliente_endereco_nao_se_repete(db):
    cliente, endereco = novo_cliente(db), novo_endereco(db)
    vincula(db, cliente, endereco)
    _recusa(
        db,
        ClienteEndereco(
            id_cliente=cliente.id_cliente, id_endereco=endereco.id_endereco,
            numero="1", complemento="", referencia="",
        ),
    )  # fmt: skip


def test_endereco_pode_ser_compartilhado_por_clientes(db):
    endereco = novo_endereco(db)
    vincula(db, novo_cliente(db), endereco)
    vincula(db, novo_cliente(db), endereco)


def test_cliente_pode_ter_varios_enderecos(db):
    cliente = novo_cliente(db)
    vincula(db, cliente, novo_endereco(db))
    vincula(db, cliente, novo_endereco(db))


# --- Vendas ------------------------------------------------------------------


def test_venda_valida_e_aceita(db):
    assert nova_venda(db).id_venda is not None


def test_venda_com_endereco_de_outro_cliente_e_recusada(db):
    """RM05: a FK composta obriga o endereço a pertencer ao cliente da venda."""
    vendedora = novo_usuario(db)
    dono = novo_cliente(db, vendedora)
    outro = novo_cliente(db, vendedora)
    endereco_do_dono = novo_endereco(db)
    vincula(db, dono, endereco_do_dono)

    with pytest.raises(IntegrityError):
        nova_venda(db, vendedora=vendedora, cliente=outro, id_endereco=endereco_do_dono.id_endereco)


def test_venda_com_endereco_nao_vinculado_ao_cliente_e_recusada(db):
    cliente = novo_cliente(db)
    solto = novo_endereco(db)  # existe, mas não está vinculado a ninguém

    with pytest.raises(IntegrityError):
        nova_venda(db, cliente=cliente, id_endereco=solto.id_endereco)


def test_venda_paga_sem_data_de_pagamento_e_recusada(db):
    with pytest.raises(IntegrityError):
        nova_venda(db, status="pago", data_pagamento=None)


def test_venda_paga_com_data_de_pagamento_e_aceita(db):
    nova_venda(db, status="pago", data_pagamento=datetime.now(UTC))


def test_venda_em_aberto_nao_exige_data_de_pagamento(db):
    assert nova_venda(db, status="em_aberto").data_pagamento is None


def test_venda_com_valor_total_negativo_e_recusada(db):
    with pytest.raises(IntegrityError):
        nova_venda(db, valor_total=Decimal("-1"))


def test_nao_apaga_cliente_com_vendas(db):
    venda = nova_venda(db)
    cliente = db.get(Cliente, venda.id_cliente)

    with pytest.raises(IntegrityError), db.begin_nested():
        db.delete(cliente)
        db.flush()


def test_nao_apaga_usuario_com_vendas(db):
    venda = nova_venda(db)
    usuario = db.get(Usuario, venda.id_usuario)

    with pytest.raises(IntegrityError), db.begin_nested():
        db.delete(usuario)
        db.flush()


# --- Item_Vendas -------------------------------------------------------------


def _item(venda, produto, preco="10.00", qtd=2, subtotal="20.00") -> ItemVenda:
    return ItemVenda(
        id_venda=venda.id_venda,
        id_produto=produto.id_produto,
        preco_unitario_v=Decimal(preco),
        quantidade=qtd,
        subtotal=Decimal(subtotal),
    )


def test_item_valido_e_aceito(db):
    _grava(db, _item(nova_venda(db), novo_produto(db)))


def test_mesmo_produto_nao_repete_na_mesma_venda(db):
    venda, produto = nova_venda(db), novo_produto(db)
    _grava(db, _item(venda, produto))
    _recusa(db, _item(venda, produto))


def test_mesmo_produto_pode_estar_em_vendas_diferentes(db):
    produto = novo_produto(db)
    _grava(db, _item(nova_venda(db), produto))
    _grava(db, _item(nova_venda(db), produto))


@pytest.mark.parametrize("qtd", [0, -1])
def test_item_com_quantidade_nao_positiva_e_recusado(db, qtd):
    _recusa(db, _item(nova_venda(db), novo_produto(db), qtd=qtd, subtotal="0.00"))


def test_item_com_subtotal_inconsistente_e_recusado(db):
    _recusa(db, _item(nova_venda(db), novo_produto(db), qtd=3, subtotal="10.00"))


def test_item_com_preco_negativo_e_recusado(db):
    _recusa(db, _item(nova_venda(db), novo_produto(db), preco="-1.00", qtd=1, subtotal="-1.00"))


def test_subtotal_arredonda_em_duas_casas(db):
    # 3.335 * 3 = 10.005 -> ROUND(..., 2) = 10.01 (arredondamento do banco, meio para cima)
    _grava(db, _item(nova_venda(db), novo_produto(db), preco="3.34", qtd=3, subtotal="10.02"))


def test_preco_do_item_nao_muda_quando_o_produto_e_reajustado(db):
    produto = novo_produto(db, preco_unitario=Decimal("10.00"))
    venda = nova_venda(db)
    _grava(db, _item(venda, produto))

    produto.preco_unitario = Decimal("99.00")
    db.flush()

    item = db.get(ItemVenda, (venda.id_venda, produto.id_produto))
    assert item.preco_unitario_v == Decimal("10.00")


def test_apagar_a_venda_apaga_os_itens(db):
    venda, produto = nova_venda(db), novo_produto(db)
    _grava(db, _item(venda, produto))

    db.delete(venda)
    db.flush()

    assert db.get(ItemVenda, (venda.id_venda, produto.id_produto)) is None


def test_nao_apaga_produto_vendido(db):
    venda, produto = nova_venda(db), novo_produto(db)
    _grava(db, _item(venda, produto))

    with pytest.raises(IntegrityError), db.begin_nested():
        db.delete(produto)
        db.flush()


# --- Movimentacoes -----------------------------------------------------------


def _mov(produto, tipo="entrada", ref="compra", qtd=5, id_venda=None) -> Movimentacao:
    return Movimentacao(
        id_produto=produto.id_produto,
        tipo_movimentacao=tipo,
        tipo_referencia=ref,
        quantidade=qtd,
        id_venda=id_venda,
    )


def test_entrada_por_compra_sem_venda_e_aceita(db):
    _grava(db, _mov(novo_produto(db), "entrada", "compra"))


def test_ajuste_manual_sem_venda_e_aceito(db):
    _grava(db, _mov(novo_produto(db), "saida", "ajuste_manual"))


def test_saida_por_venda_com_venda_e_aceita(db):
    _grava(db, _mov(novo_produto(db), "saida", "venda", id_venda=nova_venda(db).id_venda))


def test_movimentacao_de_venda_sem_id_venda_e_recusada(db):
    _recusa(db, _mov(novo_produto(db), "saida", "venda", id_venda=None))


def test_movimentacao_de_compra_com_id_venda_e_recusada(db):
    _recusa(db, _mov(novo_produto(db), "entrada", "compra", id_venda=nova_venda(db).id_venda))


@pytest.mark.parametrize("tipo", ["transferencia", "ENTRADA", ""])
def test_tipo_de_movimentacao_invalido_e_recusado(db, tipo):
    _recusa(db, _mov(novo_produto(db), tipo=tipo))


@pytest.mark.parametrize("ref", ["doacao", "Compra", ""])
def test_tipo_de_referencia_invalido_e_recusado(db, ref):
    _recusa(db, _mov(novo_produto(db), ref=ref))


@pytest.mark.parametrize("qtd", [0, -3])
def test_movimentacao_com_quantidade_nao_positiva_e_recusada(db, qtd):
    _recusa(db, _mov(novo_produto(db), qtd=qtd))


def test_movimentacao_recebe_data_automaticamente(db):
    mov = _mov(novo_produto(db))
    _grava(db, mov)

    assert mov.data_movimentacao is not None


def test_nao_apaga_venda_com_movimentacoes(db):
    venda, produto = nova_venda(db), novo_produto(db)
    _grava(db, _mov(produto, "saida", "venda", id_venda=venda.id_venda))

    with pytest.raises(IntegrityError), db.begin_nested():
        db.delete(venda)
        db.flush()


def test_consulta_de_alertas_de_estoque(db):
    """RN14: dá para listar os produtos no mínimo (ou abaixo) com uma query simples."""
    baixo = novo_produto(db, nome="BAIXO-UNICO", estoque_atual=2, estoque_minimo=5)
    novo_produto(db, nome="OK-UNICO", estoque_atual=50, estoque_minimo=5)

    nomes = db.scalars(
        select(Produto.nome).where(Produto.estoque_atual <= Produto.estoque_minimo)
    ).all()

    assert baixo.nome in nomes
    assert "OK-UNICO" not in nomes
