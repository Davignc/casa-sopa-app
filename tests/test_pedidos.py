"""RF11-RF16, RF24, RF26 e RN09-RN13: pedidos, status, estoque e cupom."""

from io import BytesIO

import pytest
from pypdf import PdfReader
from sqlalchemy import func, select

from app.models import ItemVenda, Movimentacao, Produto, Venda

ENDERECO = {
    "cep": "14400-000",
    "cidade": "Franca",
    "bairro": "Centro",
    "tipo_logradouro": "Avenida",
    "nome_logradouro": "Presidente Vargas",
    "numero": "100",
    "referencia": "portão azul",
}


@pytest.fixture
def h(headers_vendedora):
    return headers_vendedora


@pytest.fixture
def cenario(client, headers_admin):
    """Um cliente com endereço e dois produtos com estoque."""
    cliente = client.post(
        "/clientes",
        json={"nome": "Dona Maria", "telefone": "16999990001", "enderecos": [ENDERECO]},
        headers=headers_admin,
    ).json()

    def produto(nome, preco, estoque, minimo=5):
        return client.post(
            "/produtos",
            json={
                "nome": nome,
                "descricao": f"{nome} (pacote)",
                "preco_unitario": preco,
                "estoque_inicial": estoque,
                "estoque_minimo": minimo,
            },
            headers=headers_admin,
        ).json()

    a = produto("Saco 50L", "10.00", 100)
    b = produto("Saco 100L", "25.90", 20)
    return {
        "cliente": cliente,
        "id_cliente": cliente["id_cliente"],
        "id_endereco": cliente["enderecos"][0]["id_endereco"],
        "a": a["id_produto"],
        "b": b["id_produto"],
    }


def corpo(c, itens=None, **kw):
    itens = itens if itens is not None else [(c["a"], 2), (c["b"], 3)]
    base = {
        "id_cliente": c["id_cliente"],
        "id_endereco": c["id_endereco"],
        "forma_pagamento": "pix",
        "itens": [{"id_produto": p, "quantidade": q} for p, q in itens],
    }
    return base | kw


def criar(client, headers, c, **kw):
    return client.post("/pedidos", json=corpo(c, **kw), headers=headers)


@pytest.fixture
def pedido(client, h, cenario):
    return criar(client, h, cenario).json()


def estoque(db, id_produto):
    db.expire_all()
    return db.get(Produto, id_produto).estoque_atual


def mudar(client, headers, id_, status):
    return client.post(f"/pedidos/{id_}/status", json={"status": status}, headers=headers)


@pytest.mark.parametrize("origem", ["vendedora", "administradora"])
@pytest.mark.parametrize("acao", ["editar", "excluir", "confirmar", "cancelar", "entregar"])
def test_outra_vendedora_nao_altera_pedido_nem_estoque(
    client, db, h, headers_admin, cenario, origem, acao
):
    from app.schemas.usuario import UsuarioCreate
    from app.services.usuario import criar_usuario

    criar_usuario(
        db,
        UsuarioCreate(
            nome="Outra vendedora",
            email="outra@example.org",
            telefone="16977776666",
            cargo="vendedora",
            senha="senhaForte123",
        ),
    )
    token = client.post(
        "/auth/login/json",
        json={
            "email": "outra@example.org",
            "senha": "senhaForte123",
        },
    ).json()["access_token"]
    outra = {"Authorization": f"Bearer {token}"}
    dona = h if origem == "vendedora" else headers_admin
    p = criar(client, dona, cenario).json()
    id_ = p["id_pedido"]
    if acao == "entregar":
        assert mudar(client, dona, id_, "confirmado").status_code == 200
    antes = estoque(db, cenario["a"])
    movimentos = db.scalar(select(func.count()).select_from(Movimentacao))
    if acao == "editar":
        resposta = client.patch(f"/pedidos/{id_}", json={"observacao": "Indevida"}, headers=outra)
    elif acao == "excluir":
        resposta = client.delete(f"/pedidos/{id_}", headers=outra)
    else:
        destino = {"confirmar": "confirmado", "cancelar": "cancelado", "entregar": "entregue"}[acao]
        resposta = mudar(client, outra, id_, destino)
    assert resposta.status_code == 403
    atual = client.get(f"/pedidos/{id_}", headers=dona).json()
    assert atual["status"] == ("confirmado" if acao == "entregar" else "em_aberto")
    assert atual["observacao"] is None
    assert estoque(db, cenario["a"]) == antes
    assert db.scalar(select(func.count()).select_from(Movimentacao)) == movimentos


@pytest.mark.parametrize("ator", ["responsavel", "administradora"])
def test_responsavel_e_admin_editam_confirmam_cancelam_e_excluem(
    client, h, headers_admin, cenario, ator
):
    p = criar(client, h, cenario).json()
    headers = h if ator == "responsavel" else headers_admin
    id_ = p["id_pedido"]
    assert (
        client.patch(
            f"/pedidos/{id_}", json={"observacao": "Autorizada"}, headers=headers
        ).status_code
        == 200
    )
    assert mudar(client, headers, id_, "confirmado").status_code == 200
    assert mudar(client, headers, id_, "cancelado").status_code == 200
    outro = criar(client, h, cenario).json()["id_pedido"]
    assert client.delete(f"/pedidos/{outro}", headers=headers).status_code == 204


# --- permissões ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "rota"),
    [
        ("GET", "/pedidos"),
        ("POST", "/pedidos"),
        ("GET", "/pedidos/1"),
        ("PATCH", "/pedidos/1"),
        ("DELETE", "/pedidos/1"),
        ("POST", "/pedidos/1/status"),
        ("GET", "/pedidos/1/cupom"),
    ],
)
def test_sem_token_recebe_401(client, metodo, rota):
    assert client.request(metodo, rota, json={}).status_code == 401


def test_vendedora_e_administradora_operam_pedidos(
    client, headers_vendedora, headers_admin, cenario
):
    assert criar(client, headers_vendedora, cenario).status_code == 201
    assert criar(client, headers_admin, cenario).status_code == 201


# --- criação (RF11) --------------------------------------------------------------


def test_cria_pedido_em_aberto_com_total_calculado_no_servidor(client, h, cenario):
    resposta = criar(client, h, cenario)

    assert resposta.status_code == 201
    p = resposta.json()
    assert p["status"] == "em_aberto"
    assert p["valor_total"] == "97.70"  # 2 x 10,00 + 3 x 25,90
    assert p["total_produtos"] == 5
    assert p["forma_pagamento"] == "pix"
    assert p["data_pagamento"] is None
    assert {(i["quantidade"], i["preco_unitario"], i["subtotal"]) for i in p["itens"]} == {
        (2, "10.00", "20.00"),
        (3, "25.90", "77.70"),
    }


def test_pedido_traz_cliente_vendedora_e_endereco(client, h, cenario, dados_usuario):
    p = criar(client, h, cenario).json()

    assert p["cliente"] == {
        "id_cliente": cenario["id_cliente"],
        "nome": "Dona Maria",
        "telefone": "16999990001",
    }
    assert p["vendedora"]["nome"] == dados_usuario["nome"]
    assert p["endereco_entrega"]["endereco_formatado"].startswith("Avenida Presidente Vargas, 100")
    assert p["endereco_entrega"]["referencia"] == "portão azul"


@pytest.mark.parametrize(
    "extra",
    [
        {"valor_total": "0.01"},
        {"status": "entregue"},
        {"id_usuario": 1},
        {"data_venda": "2020-01-01T00:00:00Z"},
        {"preco_unitario": "0.01"},
    ],
)
def test_cliente_da_api_nao_define_total_status_nem_vendedora(client, h, cenario, extra):
    assert criar(client, h, cenario, **extra).status_code == 422


def test_preco_enviado_no_item_e_recusado(client, h, cenario):
    itens = [{"id_produto": cenario["a"], "quantidade": 1, "preco_unitario": "0.01"}]
    resposta = client.post("/pedidos", json=corpo(cenario) | {"itens": itens}, headers=h)

    assert resposta.status_code == 422


def test_criar_pedido_nao_mexe_no_estoque(client, db, h, cenario):
    criar(client, h, cenario)

    assert estoque(db, cenario["a"]) == 100
    assert estoque(db, cenario["b"]) == 20
    assert (
        db.scalar(
            select(func.count()).select_from(Movimentacao).where(Movimentacao.id_venda.is_not(None))
        )
        == 0
    )


def test_forma_de_pagamento_e_normalizada(client, h, cenario):
    p = criar(client, h, cenario, forma_pagamento="  CARTÃO   de Crédito ").json()

    assert p["forma_pagamento"] == "cartão de crédito"


def test_total_arredonda_em_centavos(client, h, cenario, headers_admin):
    id_ = client.post(
        "/produtos",
        json={"nome": "Caro", "descricao": "d", "preco_unitario": "33.33", "estoque_minimo": 0},
        headers=headers_admin,
    ).json()["id_produto"]

    p = criar(client, h, cenario, itens=[(id_, 3)]).json()

    assert p["valor_total"] == "99.99"


def test_pedido_guarda_o_preco_da_epoca(client, h, cenario, headers_admin):
    p = criar(client, h, cenario).json()
    client.patch(
        f"/produtos/{cenario['a']}", json={"preco_unitario": "99.00"}, headers=headers_admin
    )

    de_novo = client.get(f"/pedidos/{p['id_pedido']}", headers=h).json()

    assert de_novo["valor_total"] == "97.70"
    novo = criar(client, h, cenario, itens=[(cenario["a"], 1)]).json()
    assert novo["valor_total"] == "99.00"


@pytest.mark.parametrize(
    "mudanca",
    [
        {"itens": []},
        {"itens": [{"id_produto": 1, "quantidade": 0}]},
        {"itens": [{"id_produto": 1, "quantidade": -1}]},
        {"itens": [{"id_produto": 1, "quantidade": 100_001}]},
        {"itens": [{"id_produto": 1, "quantidade": 1}, {"id_produto": 1, "quantidade": 2}]},
        {"itens": [{"id_produto": n, "quantidade": 1} for n in range(1, 102)]},
        {"forma_pagamento": ""},
        {"forma_pagamento": "x" * 31},
        {"observacao": ""},
        {"observacao": "x" * 256},
        {"id_cliente": 0},
    ],
)
def test_pedido_invalido_retorna_422(client, h, cenario, mudanca):
    assert client.post("/pedidos", json=corpo(cenario) | mudanca, headers=h).status_code == 422


@pytest.mark.parametrize("faltando", ["id_cliente", "id_endereco", "forma_pagamento", "itens"])
def test_campos_obrigatorios(client, h, cenario, faltando):
    dados = {k: v for k, v in corpo(cenario).items() if k != faltando}

    assert client.post("/pedidos", json=dados, headers=h).status_code == 422


def test_cliente_inexistente_retorna_404(client, h, cenario):
    assert criar(client, h, cenario, id_cliente=999999).status_code == 404


def test_cliente_inativo_nao_recebe_pedido(client, h, cenario):
    client.delete(f"/clientes/{cenario['id_cliente']}", headers=h)

    assert criar(client, h, cenario).status_code == 422


def test_endereco_de_outro_cliente_e_recusado(client, h, cenario):
    outro = client.post(
        "/clientes",
        json={
            "nome": "Outro",
            "telefone": "16999990002",
            "enderecos": [ENDERECO | {"cep": "14401-111", "numero": "9"}],
        },
        headers=h,
    ).json()

    resposta = criar(client, h, cenario, id_endereco=outro["enderecos"][0]["id_endereco"])

    assert resposta.status_code == 422
    assert "endereço" in resposta.json()["detail"].lower()


def test_endereco_inexistente_e_recusado(client, h, cenario):
    assert criar(client, h, cenario, id_endereco=999999).status_code == 422


def test_produto_inexistente_ou_inativo_e_recusado(client, h, cenario):
    assert criar(client, h, cenario, itens=[(999999, 1)]).status_code == 422
    client.delete(f"/produtos/{cenario['a']}", headers=h)
    resposta = criar(client, h, cenario, itens=[(cenario["a"], 1)])
    assert resposta.status_code == 422
    assert "inativo" in resposta.json()["detail"]


def test_pedido_invalido_nao_grava_nada(client, db, h, cenario):
    criar(client, h, cenario, itens=[(cenario["a"], 1), (999999, 1)])

    assert db.scalar(select(func.count()).select_from(Venda)) == 0
    assert db.scalar(select(func.count()).select_from(ItemVenda)) == 0


def test_pedido_pode_ser_criado_sem_estoque_suficiente(client, h, cenario):
    """O estoque só é exigido na confirmação (RF24)."""
    assert criar(client, h, cenario, itens=[(cenario["b"], 500)]).status_code == 201


def test_administradora_registra_em_nome_de_uma_vendedora(
    client, db, headers_admin, cenario, dados_usuario, usuario_cadastrado
):
    from app.models import Usuario

    vendedora = db.scalar(select(Usuario).where(Usuario.email == dados_usuario["email"]))

    p = criar(client, headers_admin, cenario, id_vendedora=vendedora.id_usuario).json()

    assert p["vendedora"]["id_usuario"] == vendedora.id_usuario


def test_vendedora_nao_registra_em_nome_de_outra(client, db, h, cenario, admin_cadastrada):
    from app.models import Usuario

    admin = db.scalar(select(Usuario).where(Usuario.email == admin_cadastrada["email"]))

    assert criar(client, h, cenario, id_vendedora=admin.id_usuario).status_code == 403


def test_responsavel_precisa_ser_vendedora_ativa(
    client, db, headers_admin, cenario, admin_cadastrada
):
    from app.models import Usuario

    admin = db.scalar(select(Usuario).where(Usuario.email == admin_cadastrada["email"]))

    assert (
        criar(client, headers_admin, cenario, id_vendedora=admin.id_usuario).status_code == 201
    )  # ela mesma
    assert criar(client, headers_admin, cenario, id_vendedora=999999).status_code == 422


# --- listagem e detalhe (RF14) ---------------------------------------------------


def test_lista_com_todas_as_informacoes(client, h, cenario, pedido):
    corpo_lista = client.get("/pedidos", headers=h).json()

    assert corpo_lista["total"] == 1
    item = corpo_lista["itens"][0]
    assert {
        "id_pedido", "status", "data_venda", "forma_pagamento", "valor_total", "total_produtos",
        "cliente", "vendedora", "endereco_entrega", "itens",
    } <= item.keys()  # fmt: skip


def test_lista_do_mais_recente_para_o_mais_antigo(client, h, cenario):
    ids = [criar(client, h, cenario).json()["id_pedido"] for _ in range(3)]

    lista = [p["id_pedido"] for p in client.get("/pedidos", headers=h).json()["itens"]]

    assert lista == sorted(ids, reverse=True)


def test_filtros_da_listagem(client, h, cenario):
    a = criar(client, h, cenario).json()["id_pedido"]
    b = criar(client, h, cenario).json()["id_pedido"]
    mudar(client, h, b, "confirmado")

    def ids(query):
        return [p["id_pedido"] for p in client.get(f"/pedidos?{query}", headers=h).json()["itens"]]

    assert ids("status=em_aberto") == [a]
    assert ids("status=confirmado") == [b]
    assert sorted(ids(f"id_cliente={cenario['id_cliente']}")) == [a, b]
    assert ids("id_cliente=999999") == []
    assert ids("busca=maria") == [b, a]
    assert ids("busca=zzz") == []
    assert ids(f"busca={a}") == [a]
    assert ids("data_inicio=2000-01-01&data_fim=2000-12-31") == []
    assert sorted(ids("data_inicio=2000-01-01&data_fim=2100-01-01")) == [a, b]


def test_busca_com_numero_gigante_nao_quebra(client, h, cenario):
    assert client.get("/pedidos?busca=" + "9" * 40, headers=h).status_code == 200


def test_paginacao_dos_pedidos(client, h, cenario):
    for _ in range(3):
        criar(client, h, cenario)

    pagina = client.get("/pedidos?limit=2&offset=2", headers=h).json()

    assert pagina["total"] == 3
    assert len(pagina["itens"]) == 1


@pytest.mark.parametrize(
    "query",
    [
        "status=pago",
        "limit=0",
        "limit=101",
        "offset=-1",
        "id_cliente=0",
        "data_inicio=2026-02-01&data_fim=2026-01-01",
    ],
)
def test_filtros_invalidos_retornam_422(client, h, query):
    assert client.get(f"/pedidos?{query}", headers=h).status_code == 422


def test_detalhe_do_pedido(client, h, pedido):
    assert client.get(f"/pedidos/{pedido['id_pedido']}", headers=h).json() == pedido
    assert client.get("/pedidos/999999", headers=h).status_code == 404
    assert client.get("/pedidos/0", headers=h).status_code == 422


# --- edição (RF12) -----------------------------------------------------------------


def test_edicao_em_aberto_recalcula_o_total(client, h, cenario, pedido):
    novos = [{"id_produto": cenario["a"], "quantidade": 5}]  # mesmo produto, nova quantidade

    p = client.patch(f"/pedidos/{pedido['id_pedido']}", json={"itens": novos}, headers=h).json()

    assert p["valor_total"] == "50.00"
    assert [(i["id_produto"], i["quantidade"]) for i in p["itens"]] == [(cenario["a"], 5)]
    assert p["total_produtos"] == 5


def test_edicao_troca_produtos_e_pagamento_e_observacao(client, h, cenario, pedido):
    p = client.patch(
        f"/pedidos/{pedido['id_pedido']}",
        json={
            "itens": [{"id_produto": cenario["b"], "quantidade": 1}],
            "forma_pagamento": "Dinheiro",
            "observacao": "Entregar à tarde",
        },
        headers=h,
    ).json()

    assert p["valor_total"] == "25.90"
    assert p["forma_pagamento"] == "dinheiro"
    assert p["observacao"] == "Entregar à tarde"
    assert client.get("/pedidos", headers=h).json()["itens"][0]["valor_total"] == "25.90"


def test_edicao_pode_limpar_a_observacao(client, h, cenario):
    id_ = criar(client, h, cenario, observacao="X").json()["id_pedido"]

    p = client.patch(f"/pedidos/{id_}", json={"observacao": None}, headers=h).json()

    assert p["observacao"] is None


def test_vendedora_responsavel_nao_pode_ser_alterada(client, h, pedido):
    for campo in ("id_usuario", "id_vendedora", "vendedora"):
        resposta = client.patch(f"/pedidos/{pedido['id_pedido']}", json={campo: 1}, headers=h)
        assert resposta.status_code == 422


def test_admin_editar_nao_muda_a_vendedora(client, h, headers_admin, pedido):
    p = client.patch(
        f"/pedidos/{pedido['id_pedido']}", json={"forma_pagamento": "pix"}, headers=headers_admin
    ).json()

    assert p["vendedora"] == pedido["vendedora"]


def test_trocar_o_cliente_exige_o_endereco(client, h, cenario, pedido):
    outro = client.post(
        "/clientes",
        json={
            "nome": "Outro",
            "telefone": "16999990002",
            "enderecos": [ENDERECO | {"cep": "14401-111"}],
        },
        headers=h,
    ).json()
    rota = f"/pedidos/{pedido['id_pedido']}"

    sem_endereco = client.patch(rota, json={"id_cliente": outro["id_cliente"]}, headers=h)
    endereco_errado = client.patch(
        rota,
        json={"id_cliente": outro["id_cliente"], "id_endereco": cenario["id_endereco"]},
        headers=h,
    )
    certo = client.patch(
        rota,
        json={
            "id_cliente": outro["id_cliente"],
            "id_endereco": outro["enderecos"][0]["id_endereco"],
        },
        headers=h,
    )

    assert sem_endereco.status_code == 422
    assert endereco_errado.status_code == 422
    assert certo.status_code == 200
    assert certo.json()["cliente"]["nome"] == "Outro"


@pytest.mark.parametrize(
    "corpo_patch",
    [
        {},
        {"itens": []},
        {"itens": None},
        {"id_cliente": None},
        {"forma_pagamento": None},
        {"status": "entregue"},
        {"valor_total": "1"},
    ],
)
def test_edicao_invalida_retorna_422(client, h, pedido, corpo_patch):
    assert (
        client.patch(f"/pedidos/{pedido['id_pedido']}", json=corpo_patch, headers=h).status_code
        == 422
    )


def test_edicao_invalida_nao_altera_o_pedido(client, h, cenario, pedido):
    client.patch(
        f"/pedidos/{pedido['id_pedido']}",
        json={"itens": [{"id_produto": 999999, "quantidade": 1}]},
        headers=h,
    )

    assert client.get(f"/pedidos/{pedido['id_pedido']}", headers=h).json() == pedido


def test_pedido_confirmado_so_aceita_pagamento_endereco_e_observacao(client, h, cenario, pedido):
    id_ = pedido["id_pedido"]
    mudar(client, h, id_, "confirmado")

    ok = client.patch(
        f"/pedidos/{id_}",
        json={"forma_pagamento": "dinheiro", "observacao": "Troco para 50"},
        headers=h,
    )
    itens = client.patch(
        f"/pedidos/{id_}",
        json={"itens": [{"id_produto": cenario["a"], "quantidade": 1}]},
        headers=h,
    )
    cliente = client.patch(f"/pedidos/{id_}", json={"id_cliente": cenario["id_cliente"]}, headers=h)

    assert ok.status_code == 200
    assert ok.json()["forma_pagamento"] == "dinheiro"
    assert itens.status_code == 409
    assert cliente.status_code == 409


@pytest.mark.parametrize("final", ["entregue", "cancelado"])
def test_pedido_entregue_ou_cancelado_nao_pode_ser_editado(client, h, pedido, final):
    id_ = pedido["id_pedido"]
    if final == "entregue":
        mudar(client, h, id_, "confirmado")
    mudar(client, h, id_, final)

    assert client.patch(f"/pedidos/{id_}", json={"observacao": "x"}, headers=h).status_code == 409


def test_edicao_de_inexistente_retorna_404(client, h):
    assert client.patch("/pedidos/999999", json={"observacao": "x"}, headers=h).status_code == 404


# --- exclusão (RF13) ----------------------------------------------------------------


def test_exclui_pedido_em_aberto_e_seus_itens(client, db, h, pedido):
    assert client.delete(f"/pedidos/{pedido['id_pedido']}", headers=h).status_code == 204

    assert client.get(f"/pedidos/{pedido['id_pedido']}", headers=h).status_code == 404
    assert db.scalar(select(func.count()).select_from(ItemVenda)) == 0


@pytest.mark.parametrize("passos", [["confirmado"], ["confirmado", "entregue"], ["cancelado"]])
def test_nao_exclui_pedido_fora_de_aberto(client, h, pedido, passos):
    id_ = pedido["id_pedido"]
    for s in passos:
        mudar(client, h, id_, s)

    resposta = client.delete(f"/pedidos/{id_}", headers=h)

    assert resposta.status_code == 409
    assert "em aberto" in resposta.json()["detail"]
    assert client.get(f"/pedidos/{id_}", headers=h).status_code == 200


def test_exclusao_de_inexistente_retorna_404(client, h):
    assert client.delete("/pedidos/999999", headers=h).status_code == 404


# --- status e estoque (RF26, RF24) -----------------------------------------------------


def test_confirmar_baixa_o_estoque_e_registra_movimentacoes(client, db, h, cenario, pedido):
    resposta = mudar(client, h, pedido["id_pedido"], "confirmado")

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "confirmado"
    assert estoque(db, cenario["a"]) == 98
    assert estoque(db, cenario["b"]) == 17
    movs = db.scalars(
        select(Movimentacao).where(Movimentacao.id_venda == pedido["id_pedido"])
    ).all()
    assert len(movs) == 2
    assert {(m.tipo_movimentacao, m.tipo_referencia, m.quantidade) for m in movs} == {
        ("saida", "venda", 2),
        ("saida", "venda", 3),
    }
    assert all(f"Pedido #{pedido['id_pedido']}" in m.observacao for m in movs)


def test_confirmar_sem_estoque_suficiente_retorna_409_e_nao_altera_nada(client, db, h, cenario):
    id_ = criar(client, h, cenario, itens=[(cenario["a"], 5), (cenario["b"], 21)]).json()[
        "id_pedido"
    ]

    resposta = mudar(client, h, id_, "confirmado")

    assert resposta.status_code == 409
    assert "Saco 100L" in resposta.json()["detail"]
    assert "disponível 20" in resposta.json()["detail"]
    assert estoque(db, cenario["a"]) == 100  # nada foi baixado
    assert estoque(db, cenario["b"]) == 20
    assert client.get(f"/pedidos/{id_}", headers=h).json()["status"] == "em_aberto"
    assert (
        db.scalar(
            select(func.count()).select_from(Movimentacao).where(Movimentacao.id_venda.is_not(None))
        )
        == 0
    )


def test_confirmar_com_produto_inativado_retorna_409(client, db, h, cenario, pedido):
    client.delete(f"/produtos/{cenario['a']}", headers=h)

    resposta = mudar(client, h, pedido["id_pedido"], "confirmado")

    assert resposta.status_code == 409
    assert "inativo" in resposta.json()["detail"]
    assert estoque(db, cenario["b"]) == 20


def test_confirmar_duas_vezes_nao_baixa_duas_vezes(client, db, h, cenario, pedido):
    mudar(client, h, pedido["id_pedido"], "confirmado")

    segunda = mudar(client, h, pedido["id_pedido"], "confirmado")

    assert segunda.status_code == 409
    assert estoque(db, cenario["a"]) == 98


def test_cancelar_confirmado_devolve_o_estoque(client, db, h, cenario, pedido):
    mudar(client, h, pedido["id_pedido"], "confirmado")

    resposta = mudar(client, h, pedido["id_pedido"], "cancelado")

    assert resposta.json()["status"] == "cancelado"
    assert estoque(db, cenario["a"]) == 100
    assert estoque(db, cenario["b"]) == 20
    entradas = db.scalars(
        select(Movimentacao).where(
            Movimentacao.id_venda == pedido["id_pedido"],
            Movimentacao.tipo_movimentacao == "entrada",
        )
    ).all()
    assert len(entradas) == 2
    assert all("Cancelamento" in m.observacao for m in entradas)


def test_cancelar_em_aberto_nao_mexe_no_estoque(client, db, h, cenario, pedido):
    resposta = mudar(client, h, pedido["id_pedido"], "cancelado")

    assert resposta.json()["status"] == "cancelado"
    assert estoque(db, cenario["a"]) == 100
    assert (
        db.scalar(
            select(func.count()).select_from(Movimentacao).where(Movimentacao.id_venda.is_not(None))
        )
        == 0
    )


def test_entregar_nao_mexe_no_estoque(client, db, h, cenario, pedido):
    mudar(client, h, pedido["id_pedido"], "confirmado")

    resposta = mudar(client, h, pedido["id_pedido"], "entregue")

    assert resposta.json()["status"] == "entregue"
    assert estoque(db, cenario["a"]) == 98


@pytest.mark.parametrize(
    ("passos", "tentativa"),
    [
        ([], "entregue"),  # não entrega sem confirmar
        (["confirmado", "entregue"], "cancelado"),
        (["confirmado", "entregue"], "confirmado"),
        (["cancelado"], "confirmado"),
        (["cancelado"], "entregue"),
        (["confirmado"], "confirmado"),
    ],
)
def test_transicoes_invalidas_retornam_409(client, h, pedido, passos, tentativa):
    id_ = pedido["id_pedido"]
    for s in passos:
        assert mudar(client, h, id_, s).status_code == 200

    assert mudar(client, h, id_, tentativa).status_code == 409


@pytest.mark.parametrize("valor", ["pago", "em_aberto", "em_aberto_x", "", "ENTREGUE"])
def test_status_desconhecido_retorna_422(client, h, pedido, valor):
    resposta = client.post(
        f"/pedidos/{pedido['id_pedido']}/status", json={"status": valor}, headers=h
    )

    assert resposta.status_code == 422


def test_status_de_pedido_inexistente_retorna_404(client, h):
    assert mudar(client, h, 999999, "confirmado").status_code == 404


def test_vender_ate_o_minimo_dispara_alerta(client, db, h, headers_admin, cenario):
    id_ = criar(client, h, cenario, itens=[(cenario["b"], 16)]).json()["id_pedido"]  # 20 -> 4 (< 5)

    mudar(client, h, id_, "confirmado")

    alertas = client.get("/estoque/alertas", headers=headers_admin).json()
    assert [a["id_produto"] for a in alertas] == [cenario["b"]]


def test_historico_bate_com_o_estoque_depois_de_varios_pedidos(client, db, h, cenario):
    for qtd, destino in [(3, "entregue"), (4, "cancelado"), (2, "confirmado")]:
        id_ = criar(client, h, cenario, itens=[(cenario["a"], qtd)]).json()["id_pedido"]
        mudar(client, h, id_, "confirmado")
        if destino != "confirmado":
            if destino == "entregue":
                mudar(client, h, id_, "entregue")
            else:
                mudar(client, h, id_, "cancelado")

    movs = db.scalars(select(Movimentacao).where(Movimentacao.id_produto == cenario["a"])).all()
    saldo = sum(m.quantidade if m.tipo_movimentacao == "entrada" else -m.quantidade for m in movs)
    assert saldo == estoque(db, cenario["a"]) == 100 - 3 - 2


# --- cupom (RF15, RF16) -----------------------------------------------------------------


def _paginas(resposta):
    leitor = PdfReader(BytesIO(resposta.content))
    return [p.extract_text() for p in leitor.pages]


def test_cupom_e_um_pdf_com_os_dados_da_venda(client, h, cenario, pedido):
    resposta = client.get(f"/pedidos/{pedido['id_pedido']}/cupom?via=cliente", headers=h)

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.content.startswith(b"%PDF")
    assert f"pedido-{pedido['id_pedido']}-cliente.pdf" in resposta.headers["content-disposition"]
    paginas = _paginas(resposta)
    assert len(paginas) == 1
    texto = paginas[0]
    for esperado in [
        "Casa da Sopa de Restinga",
        "CUPOM NÃO FISCAL",
        f"Pedido nº {pedido['id_pedido']}",
        "Dona Maria",
        "(16) 99999-0001",
        "Avenida Presidente Vargas, 100",
        "Saco 50L",
        "Saco 100L",
        "R$ 10,00",
        "R$ 25,90",
        "R$ 97,70",
        "pix",
        "sem valor fiscal",
    ]:
        assert esperado in texto, esperado


def test_cupom_todas_as_vias_vem_identificadas(client, h, pedido):
    resposta = client.get(f"/pedidos/{pedido['id_pedido']}/cupom", headers=h)  # padrão: todas

    paginas = _paginas(resposta)

    assert len(paginas) == 3
    assert "VIA DA ONG" in paginas[0]
    assert "VIA DO ENTREGADOR" in paginas[1]
    assert "VIA DO CLIENTE" in paginas[2]


@pytest.mark.parametrize(
    ("via", "titulo"),
    [("interna", "VIA DA ONG"), ("entregador", "VIA DO ENTREGADOR"), ("cliente", "VIA DO CLIENTE")],
)
def test_cada_via_tem_o_seu_destinatario(client, h, pedido, via, titulo):
    resposta = client.get(f"/pedidos/{pedido['id_pedido']}/cupom?via={via}", headers=h)

    assert [titulo in p for p in _paginas(resposta)] == [True]


def test_pode_emitir_o_cupom_varias_vezes(client, h, pedido):
    rota = f"/pedidos/{pedido['id_pedido']}/cupom"

    assert client.get(rota, headers=h).status_code == 200
    assert client.get(rota, headers=h).status_code == 200


@pytest.mark.parametrize("passos", [[], ["confirmado"], ["confirmado", "entregue"]])
def test_cupom_disponivel_enquanto_o_pedido_nao_for_cancelado(client, h, pedido, passos):
    for s in passos:
        mudar(client, h, pedido["id_pedido"], s)

    assert client.get(f"/pedidos/{pedido['id_pedido']}/cupom", headers=h).status_code == 200


def test_pedido_cancelado_nao_gera_cupom(client, h, pedido):
    mudar(client, h, pedido["id_pedido"], "cancelado")

    assert client.get(f"/pedidos/{pedido['id_pedido']}/cupom", headers=h).status_code == 409


@pytest.mark.parametrize("query", ["via=gerente", "via="])
def test_via_invalida_retorna_422(client, h, pedido, query):
    assert client.get(f"/pedidos/{pedido['id_pedido']}/cupom?{query}", headers=h).status_code == 422


def test_cupom_de_inexistente_retorna_404(client, h):
    assert client.get("/pedidos/999999/cupom", headers=h).status_code == 404


def test_cupom_nao_quebra_com_marcacao_nem_caracteres_exoticos(client, h, cenario):
    cliente = client.post(
        "/clientes",
        json={
            "nome": "<b>Zé</b> & <i>Filhos</i> 😀 Łukasz",
            "telefone": "16999990077",
            "enderecos": [ENDERECO],
        },
        headers=h,
    ).json()
    c = cenario | {
        "id_cliente": cliente["id_cliente"],
        "id_endereco": cliente["enderecos"][0]["id_endereco"],
    }
    id_ = criar(client, h, c, observacao="<script>alert(1)</script> & mais").json()["id_pedido"]

    resposta = client.get(f"/pedidos/{id_}/cupom", headers=h)

    assert resposta.status_code == 200
    texto = " ".join(_paginas(resposta))
    assert "<b>Zé</b> & <i>Filhos</i>" in texto  # aparece literal, sem virar formatação
    assert "<script>alert(1)</script>" in texto
