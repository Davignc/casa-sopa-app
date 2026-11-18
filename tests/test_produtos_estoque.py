"""RF17-RF25 e RN14: produtos, estoque, movimentações e alertas."""

import pytest
from sqlalchemy import func, select

from app.models import Movimentacao, Produto

PRODUTO = {
    "nome": "Saco de lixo 100L",
    "descricao": "Pacote com 10 unidades",
    "preco_unitario": "25.90",
    "estoque_inicial": 50,
    "estoque_minimo": 10,
}


def _criar(client, headers, **kw):
    return client.post("/produtos", json=PRODUTO | kw, headers=headers)


def _entrada(client, headers, id_produto, quantidade=5, **kw):
    corpo = {"id_produto": id_produto, "quantidade": quantidade} | kw
    return client.post("/estoque/entradas", json=corpo, headers=headers)


def _saida(client, headers, id_produto, quantidade=5, motivo="Pacote rasgado", **kw):
    corpo = {"id_produto": id_produto, "quantidade": quantidade, "motivo": motivo} | kw
    return client.post("/estoque/saidas", json=corpo, headers=headers)


# --- permissões (casos de uso: produtos para ambas; estoque só a administradora) ---


@pytest.mark.parametrize(
    ("metodo", "rota"),
    [
        ("GET", "/produtos"),
        ("POST", "/produtos"),
        ("GET", "/produtos/1"),
        ("PATCH", "/produtos/1"),
        ("DELETE", "/produtos/1"),
        ("POST", "/produtos/1/reativar"),
        ("POST", "/estoque/entradas"),
        ("POST", "/estoque/saidas"),
        ("GET", "/estoque/movimentacoes"),
        ("GET", "/estoque/alertas"),
    ],
)
def test_sem_token_recebe_401(client, metodo, rota):
    assert client.request(metodo, rota, json={}).status_code == 401


@pytest.mark.parametrize(
    ("metodo", "rota"),
    [
        ("POST", "/estoque/entradas"),
        ("POST", "/estoque/saidas"),
        ("GET", "/estoque/movimentacoes"),
    ],
)
def test_estoque_e_exclusivo_da_administradora(client, headers_vendedora, metodo, rota):
    resposta = client.request(metodo, rota, json={}, headers=headers_vendedora)

    assert resposta.status_code == 403


def test_vendedora_gerencia_produtos_e_ve_alertas(client, headers_vendedora):
    id_ = _criar(client, headers_vendedora).json()["id_produto"]

    assert client.get("/produtos", headers=headers_vendedora).status_code == 200
    assert client.get("/estoque/alertas", headers=headers_vendedora).status_code == 200
    assert (
        client.patch(
            f"/produtos/{id_}", json={"nome": "Novo"}, headers=headers_vendedora
        ).status_code
        == 200
    )


# --- cadastro (RF17) ---------------------------------------------------------


def test_cria_produto(client, headers_admin):
    resposta = _criar(client, headers_admin)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nome"] == "Saco de lixo 100L"
    assert corpo["preco_unitario"] == "25.90"
    assert corpo["estoque_atual"] == 50
    assert corpo["estoque_minimo"] == 10
    assert corpo["is_ativo"] is True
    assert corpo["alerta_estoque_baixo"] is False


def test_estoque_inicial_vira_a_primeira_movimentacao(client, db, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]

    movs = db.scalars(select(Movimentacao).where(Movimentacao.id_produto == id_)).all()

    assert len(movs) == 1
    assert (movs[0].tipo_movimentacao, movs[0].quantidade) == ("entrada", 50)
    assert "Estoque inicial" in movs[0].observacao
    assert "[por Ana Administradora]" in movs[0].observacao


def test_estoque_inicial_zero_nao_gera_movimentacao(client, db, headers_admin):
    _criar(client, headers_admin, estoque_inicial=0)

    assert db.scalar(select(func.count()).select_from(Movimentacao)) == 0


def test_estoque_inicial_e_opcional(client, headers_admin):
    corpo = {k: v for k, v in PRODUTO.items() if k != "estoque_inicial"}

    resposta = client.post("/produtos", json=corpo, headers=headers_admin)

    assert resposta.json()["estoque_atual"] == 0


@pytest.mark.parametrize(
    "mudanca",
    [
        {"nome": ""},
        {"nome": "x" * 151},
        {"descricao": ""},
        {"preco_unitario": "-1"},
        {"preco_unitario": "10.999"},
        {"preco_unitario": "100000000.00"},
        {"preco_unitario": "abc"},
        {"estoque_inicial": -1},
        {"estoque_inicial": 1_000_001},
        {"estoque_minimo": -1},
        {"estoque_atual": 5},
        {"is_ativo": False},
    ],
)
def test_cadastro_invalido_retorna_422(client, headers_admin, mudanca):
    assert _criar(client, headers_admin, **mudanca).status_code == 422


def test_campos_obrigatorios(client, headers_admin):
    for faltando in ("nome", "descricao", "preco_unitario", "estoque_minimo"):
        corpo = {k: v for k, v in PRODUTO.items() if k != faltando}
        assert client.post("/produtos", json=corpo, headers=headers_admin).status_code == 422


def test_preco_zero_e_aceito(client, headers_admin):
    assert _criar(client, headers_admin, preco_unitario="0").status_code == 201


# --- listagem (RF20/RF25) ----------------------------------------------------


def test_lista_nome_descricao_preco_e_quantidade(client, headers_vendedora, headers_admin):
    _criar(client, headers_admin)

    corpo = client.get("/produtos", headers=headers_vendedora).json()

    assert corpo["total"] == 1
    item = corpo["itens"][0]
    assert {"nome", "descricao", "preco_unitario", "estoque_atual"} <= item.keys()


def test_lista_ordenada_e_paginada(client, headers_admin):
    for nome in ["Cesto", "Avental", "Balde"]:
        _criar(client, headers_admin, nome=nome)

    todos = client.get("/produtos", headers=headers_admin).json()
    pag = client.get("/produtos?limit=2&offset=2", headers=headers_admin).json()

    assert [p["nome"] for p in todos["itens"]] == ["Avental", "Balde", "Cesto"]
    assert [p["nome"] for p in pag["itens"]] == ["Cesto"]
    assert pag["total"] == 3


def test_busca_por_nome_ou_descricao(client, headers_admin):
    _criar(client, headers_admin, nome="Saco 50L", descricao="Reforçado")
    _criar(client, headers_admin, nome="Balde", descricao="Para sacos grandes")
    _criar(client, headers_admin, nome="Vassoura", descricao="Cerdas macias")

    nomes = {
        p["nome"] for p in client.get("/produtos?busca=SACO", headers=headers_admin).json()["itens"]
    }

    assert nomes == {"Saco 50L", "Balde"}


def test_inativo_some_da_listagem_por_padrao(client, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]
    client.delete(f"/produtos/{id_}", headers=headers_admin)

    assert client.get("/produtos", headers=headers_admin).json()["total"] == 0
    assert client.get("/produtos?incluir_inativos=true", headers=headers_admin).json()["total"] == 1


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_paginacao_invalida_retorna_422(client, headers_admin, query):
    assert client.get(f"/produtos?{query}", headers=headers_admin).status_code == 422


def test_detalhe(client, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]

    assert client.get(f"/produtos/{id_}", headers=headers_admin).json()["nome"] == PRODUTO["nome"]
    assert client.get("/produtos/999999", headers=headers_admin).status_code == 404
    assert client.get("/produtos/0", headers=headers_admin).status_code == 422


# --- edição (RF18) -----------------------------------------------------------


def test_edita_campos_e_reflete_na_listagem(client, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]

    corpo = client.patch(
        f"/produtos/{id_}",
        json={"nome": "Saco 200L", "preco_unitario": "30", "estoque_minimo": 20},
        headers=headers_admin,
    ).json()

    assert (corpo["nome"], corpo["preco_unitario"], corpo["estoque_minimo"]) == (
        "Saco 200L",
        "30.00",
        20,
    )
    assert client.get("/produtos", headers=headers_admin).json()["itens"][0]["nome"] == "Saco 200L"


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"nome": None},
        {"preco_unitario": None},
        {"preco_unitario": "-5"},
        {"estoque_minimo": -1},
        {"estoque_atual": 999},
        {"estoque_inicial": 999},
        {"is_ativo": False},
    ],
)
def test_edicao_invalida_retorna_422(client, headers_admin, corpo):
    id_ = _criar(client, headers_admin).json()["id_produto"]

    assert client.patch(f"/produtos/{id_}", json=corpo, headers=headers_admin).status_code == 422


def test_edicao_nao_mexe_na_quantidade(client, db, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]

    client.patch(f"/produtos/{id_}", json={"estoque_minimo": 99}, headers=headers_admin)

    assert db.get(Produto, id_).estoque_atual == 50


def test_edicao_de_inexistente_retorna_404(client, headers_admin):
    assert (
        client.patch("/produtos/999999", json={"nome": "X"}, headers=headers_admin).status_code
        == 404
    )


# --- inativação (RF19) -------------------------------------------------------


def test_inativar_preserva_o_registro_e_o_historico(client, db, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]

    assert client.delete(f"/produtos/{id_}", headers=headers_admin).status_code == 204

    assert db.get(Produto, id_).is_ativo is False
    assert db.scalar(select(func.count()).select_from(Movimentacao)) == 1


def test_inativar_e_idempotente_e_404_para_inexistente(client, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]
    client.delete(f"/produtos/{id_}", headers=headers_admin)

    assert client.delete(f"/produtos/{id_}", headers=headers_admin).status_code == 204
    assert client.delete("/produtos/999999", headers=headers_admin).status_code == 404


def test_reativar(client, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]
    client.delete(f"/produtos/{id_}", headers=headers_admin)

    assert (
        client.post(f"/produtos/{id_}/reativar", headers=headers_admin).json()["is_ativo"] is True
    )


def test_produto_inativo_nao_recebe_movimentacao(client, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]
    client.delete(f"/produtos/{id_}", headers=headers_admin)

    assert _entrada(client, headers_admin, id_).status_code == 409
    assert _saida(client, headers_admin, id_).status_code == 409


# --- entradas (RF21) ---------------------------------------------------------


def test_entrada_soma_ao_estoque_e_registra_historico(client, db, headers_admin):
    id_ = _criar(client, headers_admin, estoque_inicial=10).json()["id_produto"]

    resposta = _entrada(client, headers_admin, id_, 25, observacao="Compra do fornecedor X")

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["produto"]["estoque_atual"] == 35
    mov = corpo["movimentacao"]
    assert (mov["tipo_movimentacao"], mov["quantidade"], mov["tipo_referencia"]) == (
        "entrada",
        25,
        "compra",
    )
    assert mov["nome_produto"] == PRODUTO["nome"]
    assert mov["data_movimentacao"]
    assert "Compra do fornecedor X" in mov["observacao"]
    assert db.get(Produto, id_).estoque_atual == 35


def test_entrada_como_ajuste_manual(client, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]

    corpo = _entrada(client, headers_admin, id_, 1, tipo="ajuste_manual").json()

    assert corpo["movimentacao"]["tipo_referencia"] == "ajuste_manual"


@pytest.mark.parametrize(
    "mudanca",
    [
        {"quantidade": 0},
        {"quantidade": -3},
        {"quantidade": 1_000_001},
        {"tipo": "venda"},
        {"id_produto": 0},
        {"observacao": ""},
        {"id_venda": 1},
    ],
)
def test_entrada_invalida_retorna_422(client, headers_admin, mudanca):
    id_ = _criar(client, headers_admin).json()["id_produto"]
    corpo = {"id_produto": id_, "quantidade": 5} | mudanca

    assert client.post("/estoque/entradas", json=corpo, headers=headers_admin).status_code == 422


def test_entrada_de_produto_inexistente_retorna_404(client, headers_admin):
    assert _entrada(client, headers_admin, 999999).status_code == 404


def test_entrada_nao_passa_do_limite_do_banco(client, db, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]
    db.get(Produto, id_).estoque_atual = 2_000_000_000 - 5
    db.flush()

    resposta = _entrada(client, headers_admin, id_, 10)

    assert resposta.status_code == 422
    assert db.get(Produto, id_).estoque_atual == 2_000_000_000 - 5


# --- saídas (RF22) -----------------------------------------------------------


def test_saida_baixa_o_estoque_com_motivo_e_responsavel(client, headers_admin):
    id_ = _criar(client, headers_admin, estoque_inicial=20).json()["id_produto"]

    corpo = _saida(client, headers_admin, id_, 7, motivo="Caixa molhada").json()

    assert corpo["produto"]["estoque_atual"] == 13
    mov = corpo["movimentacao"]
    assert (mov["tipo_movimentacao"], mov["quantidade"], mov["tipo_referencia"]) == (
        "saida",
        7,
        "ajuste_manual",
    )
    assert "Caixa molhada" in mov["observacao"]
    assert "[por Ana Administradora]" in mov["observacao"]


def test_saida_pode_zerar_o_estoque(client, headers_admin):
    id_ = _criar(client, headers_admin, estoque_inicial=5).json()["id_produto"]

    assert _saida(client, headers_admin, id_, 5).json()["produto"]["estoque_atual"] == 0


def test_saida_maior_que_o_estoque_retorna_409_e_nao_altera(client, db, headers_admin):
    id_ = _criar(client, headers_admin, estoque_inicial=5).json()["id_produto"]

    resposta = _saida(client, headers_admin, id_, 6)

    assert resposta.status_code == 409
    assert "insuficiente" in resposta.json()["detail"].lower()
    assert db.get(Produto, id_).estoque_atual == 5
    assert db.scalar(select(func.count()).select_from(Movimentacao)) == 1  # só o estoque inicial


@pytest.mark.parametrize(
    "mudanca", [{"motivo": ""}, {"motivo": "ab"}, {"quantidade": 0}, {"quantidade": -1}]
)
def test_saida_invalida_retorna_422(client, headers_admin, mudanca):
    id_ = _criar(client, headers_admin).json()["id_produto"]
    corpo = {"id_produto": id_, "quantidade": 1, "motivo": "Perda"} | mudanca

    assert client.post("/estoque/saidas", json=corpo, headers=headers_admin).status_code == 422


def test_saida_exige_motivo(client, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]

    resposta = client.post(
        "/estoque/saidas", json={"id_produto": id_, "quantidade": 1}, headers=headers_admin
    )

    assert resposta.status_code == 422


def test_observacao_nunca_estoura_o_limite_do_banco(client, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]

    resposta = _saida(client, headers_admin, id_, 1, motivo="m" * 150)

    assert resposta.status_code == 201
    assert len(resposta.json()["movimentacao"]["observacao"]) <= 255


# --- histórico ---------------------------------------------------------------


def test_historico_do_mais_recente_para_o_mais_antigo(client, headers_admin):
    id_ = _criar(client, headers_admin, estoque_inicial=10).json()["id_produto"]
    _entrada(client, headers_admin, id_, 5)
    _saida(client, headers_admin, id_, 2)

    corpo = client.get("/estoque/movimentacoes", headers=headers_admin).json()

    assert corpo["total"] == 3
    assert [m["tipo_movimentacao"] for m in corpo["itens"]] == ["saida", "entrada", "entrada"]


def test_historico_filtra_por_produto_e_tipo(client, headers_admin):
    a = _criar(client, headers_admin, nome="A").json()["id_produto"]
    b = _criar(client, headers_admin, nome="B").json()["id_produto"]
    _saida(client, headers_admin, a, 1)
    _saida(client, headers_admin, b, 1)

    do_a = client.get(f"/estoque/movimentacoes?id_produto={a}", headers=headers_admin).json()
    saidas = client.get("/estoque/movimentacoes?tipo=saida", headers=headers_admin).json()

    assert {m["id_produto"] for m in do_a["itens"]} == {a}
    assert do_a["total"] == 2
    assert saidas["total"] == 2


def test_historico_filtra_por_periodo(client, headers_admin):
    id_ = _criar(client, headers_admin).json()["id_produto"]
    _entrada(client, headers_admin, id_)

    hoje = client.get(
        "/estoque/movimentacoes?data_inicio=2000-01-01&data_fim=2000-01-02", headers=headers_admin
    )
    tudo = client.get(
        "/estoque/movimentacoes?data_inicio=2000-01-01&data_fim=2100-01-01", headers=headers_admin
    )

    assert hoje.json()["total"] == 0
    assert tudo.json()["total"] == 2


@pytest.mark.parametrize(
    "query",
    [
        "data_inicio=2026-02-01&data_fim=2026-01-01",
        "tipo=venda",
        "id_produto=0",
        "data_inicio=abc",
        "limit=0",
    ],
)
def test_historico_com_filtro_invalido_retorna_422(client, headers_admin, query):
    assert client.get(f"/estoque/movimentacoes?{query}", headers=headers_admin).status_code == 422


def test_o_historico_sempre_bate_com_a_quantidade_do_produto(client, db, headers_admin):
    id_ = _criar(client, headers_admin, estoque_inicial=30).json()["id_produto"]
    _entrada(client, headers_admin, id_, 12)
    _saida(client, headers_admin, id_, 5)
    _saida(client, headers_admin, id_, 100)  # recusada

    movs = db.scalars(select(Movimentacao).where(Movimentacao.id_produto == id_)).all()
    saldo = sum(m.quantidade if m.tipo_movimentacao == "entrada" else -m.quantidade for m in movs)

    assert saldo == db.get(Produto, id_).estoque_atual == 37


# --- alertas (RF23/RN14) -----------------------------------------------------


def test_alerta_quando_atinge_o_minimo(client, headers_admin):
    id_ = _criar(client, headers_admin, estoque_inicial=12, estoque_minimo=10).json()["id_produto"]
    assert client.get("/estoque/alertas", headers=headers_admin).json() == []

    corpo = _saida(client, headers_admin, id_, 2).json()  # 12 -> 10 (= mínimo)

    assert corpo["produto"]["alerta_estoque_baixo"] is True
    alertas = client.get("/estoque/alertas", headers=headers_admin).json()
    assert [a["id_produto"] for a in alertas] == [id_]


def test_alerta_some_quando_o_estoque_se_recupera(client, headers_admin):
    id_ = _criar(client, headers_admin, estoque_inicial=5, estoque_minimo=10).json()["id_produto"]
    assert len(client.get("/estoque/alertas", headers=headers_admin).json()) == 1

    corpo = _entrada(client, headers_admin, id_, 20).json()

    assert corpo["produto"]["alerta_estoque_baixo"] is False
    assert client.get("/estoque/alertas", headers=headers_admin).json() == []


def test_alertas_ordenados_do_mais_critico(client, headers_admin):
    _criar(client, headers_admin, nome="Quase", estoque_inicial=9, estoque_minimo=10)
    _criar(client, headers_admin, nome="Zerado", estoque_inicial=0, estoque_minimo=10)

    nomes = [a["nome"] for a in client.get("/estoque/alertas", headers=headers_admin).json()]

    assert nomes == ["Zerado", "Quase"]


def test_produto_inativo_nao_gera_alerta(client, headers_admin):
    id_ = _criar(client, headers_admin, estoque_inicial=0, estoque_minimo=10).json()["id_produto"]
    client.delete(f"/produtos/{id_}", headers=headers_admin)

    assert client.get("/estoque/alertas", headers=headers_admin).json() == []
    inativo = client.get("/produtos?incluir_inativos=true", headers=headers_admin).json()["itens"][
        0
    ]
    assert inativo["alerta_estoque_baixo"] is False


def test_listagem_destaca_e_filtra_estoque_baixo(client, headers_admin):
    _criar(client, headers_admin, nome="Baixo", estoque_inicial=1, estoque_minimo=5)
    _criar(client, headers_admin, nome="Folgado", estoque_inicial=50, estoque_minimo=5)

    todos = {
        p["nome"]: p["alerta_estoque_baixo"]
        for p in client.get("/produtos", headers=headers_admin).json()["itens"]
    }
    so_alerta = client.get("/produtos?apenas_alerta=true", headers=headers_admin).json()

    assert todos == {"Baixo": True, "Folgado": False}
    assert [p["nome"] for p in so_alerta["itens"]] == ["Baixo"]
    assert so_alerta["total"] == 1
