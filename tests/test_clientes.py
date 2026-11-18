"""RF07-RF10, RN07-RN08: clientes e seus endereços."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import Cliente, ClienteEndereco, Endereco, Usuario, Venda

ENDERECO = {
    "cep": "14400-000",
    "cidade": "Franca",
    "bairro": "Centro",
    "tipo_logradouro": "Avenida",
    "nome_logradouro": "Presidente Vargas",
    "numero": "100",
}
OUTRO_ENDERECO = {
    "cep": "14401-111",
    "cidade": "Franca",
    "bairro": "Jardim Paulista",
    "tipo_logradouro": "Rua",
    "nome_logradouro": "Voluntários da Franca",
    "numero": "S/N",
    "complemento": "fundos",
    "referencia": "perto da padaria",
    "apelido": "Trabalho",
}


def _criar(client, headers, nome="Joana", telefone="16 99999-1111", enderecos=None):
    corpo = {"nome": nome, "telefone": telefone}
    if enderecos is not None:
        corpo["enderecos"] = enderecos
    return client.post("/clientes", json=corpo, headers=headers)


@pytest.fixture
def h(headers_vendedora):
    return headers_vendedora


# --- permissões --------------------------------------------------------------

ROTAS = [
    ("GET", "/clientes"),
    ("POST", "/clientes"),
    ("GET", "/clientes/1"),
    ("PATCH", "/clientes/1"),
    ("DELETE", "/clientes/1"),
    ("POST", "/clientes/1/reativar"),
    ("POST", "/clientes/1/enderecos"),
    ("PATCH", "/clientes/1/enderecos/1"),
    ("DELETE", "/clientes/1/enderecos/1"),
]


@pytest.mark.parametrize(("metodo", "rota"), ROTAS)
def test_sem_token_recebe_401(client, metodo, rota):
    assert client.request(metodo, rota, json={}).status_code == 401


def test_vendedora_e_administradora_cadastram_clientes(client, headers_vendedora, headers_admin):
    assert _criar(client, headers_vendedora, telefone="16999990001").status_code == 201
    assert _criar(client, headers_admin, telefone="16999990002").status_code == 201


# --- cadastro (RF07) ---------------------------------------------------------


def test_cria_cliente_sem_endereco(client, h):
    resposta = _criar(client, h)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nome"] == "Joana"
    assert corpo["telefone"] == "16999991111"
    assert corpo["is_ativo"] is True
    assert corpo["enderecos"] == []
    assert corpo["endereco_principal"] is None


def test_registra_a_usuaria_que_cadastrou(client, db, h, dados_usuario):
    corpo = _criar(client, h).json()

    quem = db.scalar(select(Usuario).where(Usuario.email == dados_usuario["email"]))
    assert corpo["cadastrado_por"] == {"id_usuario": quem.id_usuario, "nome": quem.nome}
    assert db.get(Cliente, corpo["id_cliente"]).id_usuario == quem.id_usuario


def test_cria_com_enderecos_e_o_primeiro_vira_principal(client, h):
    corpo = _criar(client, h, enderecos=[ENDERECO, OUTRO_ENDERECO]).json()

    assert [e["principal"] for e in corpo["enderecos"]] == [True, False]
    assert corpo["endereco_principal"]["cep"] == "14400000"
    assert corpo["enderecos"][0]["endereco_formatado"] == (
        "Avenida Presidente Vargas, 100 - Centro, Franca - CEP 14400-000"
    )


def test_respeita_o_principal_informado(client, h):
    corpo = _criar(client, h, enderecos=[ENDERECO, OUTRO_ENDERECO | {"principal": True}]).json()

    assert corpo["endereco_principal"]["apelido"] == "Trabalho"
    assert sum(e["principal"] for e in corpo["enderecos"]) == 1


def test_dois_principais_retorna_422(client, h):
    enderecos = [ENDERECO | {"principal": True}, OUTRO_ENDERECO | {"principal": True}]

    assert _criar(client, h, enderecos=enderecos).status_code == 422


def test_mesmo_endereco_duas_vezes_retorna_422_e_nao_cria_o_cliente(client, db, h):
    resposta = _criar(client, h, enderecos=[ENDERECO, ENDERECO | {"numero": "200"}])

    assert resposta.status_code == 422
    assert db.scalar(select(func.count()).select_from(Cliente)) == 0


def test_complemento_e_referencia_sao_opcionais(client, h):
    endereco = _criar(client, h, enderecos=[ENDERECO]).json()["enderecos"][0]

    assert endereco["complemento"] == ""
    assert endereco["referencia"] == ""
    assert endereco["apelido"] is None


@pytest.mark.parametrize(
    "mudanca",
    [
        {"cep": "123"},
        {"cep": "abcdefgh"},
        {"cidade": ""},
        {"numero": ""},
        {"numero": "12345678901"},
        {"tipo_logradouro": "x" * 21},
        {"id_endereco": 1},
    ],
)
def test_endereco_invalido_retorna_422(client, h, mudanca):
    assert _criar(client, h, enderecos=[ENDERECO | mudanca]).status_code == 422


@pytest.mark.parametrize(
    "corpo",
    [
        {"telefone": "16999991111"},
        {"nome": "", "telefone": "16999991111"},
        {"nome": "Ana", "telefone": "123"},
        {"nome": "Ana", "telefone": "16999991111", "id_usuario": 1},
        {"nome": "Ana", "telefone": "16999991111", "is_ativo": False},
    ],
)
def test_corpo_invalido_retorna_422(client, h, corpo):
    assert client.post("/clientes", json=corpo, headers=h).status_code == 422


def test_mais_de_dez_enderecos_retorna_422(client, h):
    enderecos = [ENDERECO | {"numero": str(i), "cep": f"1440{i:04d}"} for i in range(11)]

    assert _criar(client, h, enderecos=enderecos).status_code == 422


# --- telefone único (RN07/RN08) ----------------------------------------------


def test_telefone_duplicado_retorna_409(client, h):
    _criar(client, h, telefone="16999991111")

    resposta = _criar(client, h, nome="Outra", telefone="16999991111")

    assert resposta.status_code == 409
    assert "telefone" in resposta.json()["detail"].lower()


def test_telefone_formatado_conta_como_duplicado(client, h):
    _criar(client, h, telefone="16999991111")

    assert _criar(client, h, nome="Outra", telefone="(16) 99999-1111").status_code == 409


def test_telefone_de_cliente_inativo_continua_reservado_com_dica(client, h):
    id_ = _criar(client, h, telefone="16999991111").json()["id_cliente"]
    client.delete(f"/clientes/{id_}", headers=h)

    resposta = _criar(client, h, nome="Outra", telefone="16999991111")

    assert resposta.status_code == 409
    assert "reative" in resposta.json()["detail"].lower()


def test_telefone_de_cliente_nao_conflita_com_o_de_usuario(client, h, dados_usuario):
    assert _criar(client, h, telefone=dados_usuario["telefone"]).status_code == 201


# --- endereço compartilhado (RM04) -------------------------------------------


def test_mesmo_endereco_fisico_e_reaproveitado_entre_clientes(client, db, h):
    a = _criar(client, h, telefone="16999990001", enderecos=[ENDERECO]).json()
    b = _criar(
        client,
        h,
        telefone="16999990002",
        enderecos=[ENDERECO | {"numero": "250", "cidade": "FRANCA", "bairro": "centro"}],
    ).json()

    assert a["enderecos"][0]["id_endereco"] == b["enderecos"][0]["id_endereco"]
    assert db.scalar(select(func.count()).select_from(Endereco)) == 1
    assert a["enderecos"][0]["numero"] == "100"  # o número é de cada cliente
    assert b["enderecos"][0]["numero"] == "250"


# --- listagem (RF10) ---------------------------------------------------------


def test_lista_nome_telefone_e_endereco_principal(client, h):
    _criar(client, h, nome="Ana", telefone="16999990001", enderecos=[ENDERECO, OUTRO_ENDERECO])
    _criar(client, h, nome="Bia", telefone="16999990002")

    corpo = client.get("/clientes", headers=h).json()

    assert corpo["total"] == 2
    ana, bia = corpo["itens"]
    assert (ana["nome"], ana["telefone"]) == ("Ana", "16999990001")
    assert ana["endereco_principal"]["cep"] == "14400000"
    assert bia["endereco_principal"] is None
    assert "enderecos" not in ana


def test_lista_ordenada_por_nome(client, h):
    for i, nome in enumerate(["Carla", "Ana", "Bia"]):
        _criar(client, h, nome=nome, telefone=f"1699999000{i}")

    nomes = [c["nome"] for c in client.get("/clientes", headers=h).json()["itens"]]

    assert nomes == ["Ana", "Bia", "Carla"]


def test_inativo_nao_aparece_na_listagem_por_padrao(client, h):
    id_ = _criar(client, h, nome="Sumida").json()["id_cliente"]
    client.delete(f"/clientes/{id_}", headers=h)

    assert client.get("/clientes", headers=h).json()["total"] == 0
    com_inativos = client.get("/clientes?incluir_inativos=true", headers=h).json()
    assert [c["nome"] for c in com_inativos["itens"]] == ["Sumida"]


def test_busca_por_nome_e_por_telefone_com_mascara(client, h):
    _criar(client, h, nome="Maria José", telefone="16999990001")
    _criar(client, h, nome="Pedro", telefone="16988880002")

    por_nome = client.get("/clientes?busca=josé", headers=h).json()
    por_fone = client.get("/clientes?busca=(16) 98888", headers=h).json()

    assert [c["nome"] for c in por_nome["itens"]] == ["Maria José"]
    assert [c["nome"] for c in por_fone["itens"]] == ["Pedro"]


def test_busca_trata_curingas_como_texto(client, h):
    _criar(client, h, nome="Maria")

    assert client.get("/clientes?busca=%25", headers=h).json()["total"] == 0


def test_paginacao(client, h):
    for i in range(5):
        _criar(client, h, nome=f"Cliente {i}", telefone=f"1699999000{i}")

    p1 = client.get("/clientes?limit=3", headers=h).json()
    p2 = client.get("/clientes?limit=3&offset=3", headers=h).json()

    assert p1["total"] == p2["total"] == 5
    assert (len(p1["itens"]), len(p2["itens"])) == (3, 2)


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_paginacao_invalida_retorna_422(client, h, query):
    assert client.get(f"/clientes?{query}", headers=h).status_code == 422


# --- detalhe e edição (RF08) -------------------------------------------------


def test_detalhe_e_404(client, h):
    assert client.get("/clientes/999999", headers=h).status_code == 404
    assert client.get("/clientes/0", headers=h).status_code == 422


def test_edita_nome_e_telefone(client, h):
    id_ = _criar(client, h).json()["id_cliente"]

    corpo = client.patch(
        f"/clientes/{id_}", json={"nome": "Joana Silva", "telefone": "(16) 98888-0000"}, headers=h
    ).json()

    assert (corpo["nome"], corpo["telefone"]) == ("Joana Silva", "16988880000")
    assert client.get("/clientes", headers=h).json()["itens"][0]["nome"] == "Joana Silva"


def test_telefone_de_outro_cliente_retorna_409_na_edicao(client, h):
    _criar(client, h, nome="A", telefone="16999990001")
    id_b = _criar(client, h, nome="B", telefone="16999990002").json()["id_cliente"]

    resposta = client.patch(f"/clientes/{id_b}", json={"telefone": "16999990001"}, headers=h)

    assert resposta.status_code == 409


def test_pode_reenviar_o_proprio_telefone(client, h):
    id_ = _criar(client, h, telefone="16999990001").json()["id_cliente"]

    resposta = client.patch(f"/clientes/{id_}", json={"telefone": "(16) 99999-0001"}, headers=h)

    assert resposta.status_code == 200


@pytest.mark.parametrize(
    "corpo",
    [{}, {"nome": None}, {"telefone": None}, {"nome": ""}, {"telefone": "1"}, {"is_ativo": False}],
)
def test_edicao_invalida_retorna_422(client, h, corpo):
    id_ = _criar(client, h).json()["id_cliente"]

    assert client.patch(f"/clientes/{id_}", json=corpo, headers=h).status_code == 422


def test_edicao_de_inexistente_retorna_404(client, h):
    assert client.patch("/clientes/999999", json={"nome": "X"}, headers=h).status_code == 404


# --- inativação (RF09) -------------------------------------------------------


def test_inativar_preserva_o_registro(client, db, h):
    id_ = _criar(client, h).json()["id_cliente"]

    resposta = client.delete(f"/clientes/{id_}", headers=h)

    assert resposta.status_code == 204
    assert db.get(Cliente, id_).is_ativo is False


def test_inativar_e_idempotente_e_404_para_inexistente(client, h):
    id_ = _criar(client, h).json()["id_cliente"]
    client.delete(f"/clientes/{id_}", headers=h)

    assert client.delete(f"/clientes/{id_}", headers=h).status_code == 204
    assert client.delete("/clientes/999999", headers=h).status_code == 404


def test_reativar_devolve_o_cliente_a_listagem(client, h):
    id_ = _criar(client, h).json()["id_cliente"]
    client.delete(f"/clientes/{id_}", headers=h)

    resposta = client.post(f"/clientes/{id_}/reativar", headers=h)

    assert resposta.json()["is_ativo"] is True
    assert client.get("/clientes", headers=h).json()["total"] == 1


# --- endereços do cliente (RF08) ---------------------------------------------


def _end(client, h, id_, **kw):
    return client.post(f"/clientes/{id_}/enderecos", json=ENDERECO | kw, headers=h)


def test_primeiro_endereco_adicionado_vira_principal(client, h):
    id_ = _criar(client, h).json()["id_cliente"]

    corpo = _end(client, h, id_).json()

    assert corpo["endereco_principal"]["cep"] == "14400000"


def test_segundo_endereco_nao_e_principal_a_menos_que_peca(client, h):
    id_ = _criar(client, h, enderecos=[ENDERECO]).json()["id_cliente"]

    corpo = client.post(f"/clientes/{id_}/enderecos", json=OUTRO_ENDERECO, headers=h).json()
    assert corpo["endereco_principal"]["cep"] == "14400000"

    corpo = client.post(
        f"/clientes/{id_}/enderecos",
        json=OUTRO_ENDERECO | {"cep": "14402-222", "principal": True},
        headers=h,
    ).json()
    assert corpo["endereco_principal"]["cep"] == "14402222"
    assert sum(e["principal"] for e in corpo["enderecos"]) == 1


def test_adicionar_o_mesmo_endereco_retorna_409(client, h):
    id_ = _criar(client, h, enderecos=[ENDERECO]).json()["id_cliente"]

    assert _end(client, h, id_, numero="999").status_code == 409


def test_altera_numero_apelido_e_principal(client, h):
    cliente = _criar(client, h, enderecos=[ENDERECO, OUTRO_ENDERECO]).json()
    id_, segundo = cliente["id_cliente"], cliente["enderecos"][1]["id_endereco"]

    corpo = client.patch(
        f"/clientes/{id_}/enderecos/{segundo}",
        json={"numero": "55B", "apelido": "Casa da mãe", "principal": True},
        headers=h,
    ).json()

    principal = corpo["endereco_principal"]
    assert (principal["id_endereco"], principal["numero"]) == (segundo, "55B")
    assert principal["apelido"] == "Casa da mãe"
    assert sum(e["principal"] for e in corpo["enderecos"]) == 1


def test_nao_deixa_o_cliente_sem_principal(client, h):
    cliente = _criar(client, h, enderecos=[ENDERECO, OUTRO_ENDERECO]).json()
    principal = cliente["endereco_principal"]["id_endereco"]

    resposta = client.patch(
        f"/clientes/{cliente['id_cliente']}/enderecos/{principal}",
        json={"principal": False},
        headers=h,
    )

    assert resposta.status_code == 409


@pytest.mark.parametrize(
    "corpo",
    [{}, {"numero": None}, {"principal": None}, {"cep": "14400000"}, {"cidade": "Outra"}],
)
def test_edicao_de_endereco_invalida_retorna_422(client, h, corpo):
    cliente = _criar(client, h, enderecos=[ENDERECO]).json()
    id_end = cliente["enderecos"][0]["id_endereco"]

    resposta = client.patch(
        f"/clientes/{cliente['id_cliente']}/enderecos/{id_end}", json=corpo, headers=h
    )

    assert resposta.status_code == 422


def test_endereco_de_outro_cliente_retorna_404(client, h):
    dono = _criar(client, h, telefone="16999990001", enderecos=[ENDERECO]).json()
    outro = _criar(client, h, telefone="16999990002").json()["id_cliente"]
    id_end = dono["enderecos"][0]["id_endereco"]

    assert (
        client.patch(
            f"/clientes/{outro}/enderecos/{id_end}", json={"numero": "1"}, headers=h
        ).status_code
        == 404
    )
    assert client.delete(f"/clientes/{outro}/enderecos/{id_end}", headers=h).status_code == 404


def test_remover_endereco_nunca_usado_apaga_tudo_e_outro_vira_principal(client, db, h):
    cliente = _criar(client, h, enderecos=[ENDERECO, OUTRO_ENDERECO]).json()
    principal = cliente["endereco_principal"]["id_endereco"]

    corpo = client.delete(
        f"/clientes/{cliente['id_cliente']}/enderecos/{principal}", headers=h
    ).json()

    assert len(corpo["enderecos"]) == 1
    assert corpo["endereco_principal"]["apelido"] == "Trabalho"
    assert db.get(Endereco, principal) is None
    assert db.get(ClienteEndereco, (cliente["id_cliente"], principal)) is None


def test_remover_endereco_compartilhado_so_desfaz_o_vinculo(client, db, h):
    a = _criar(client, h, telefone="16999990001", enderecos=[ENDERECO]).json()
    b = _criar(client, h, telefone="16999990002", enderecos=[ENDERECO]).json()
    id_end = a["enderecos"][0]["id_endereco"]

    client.delete(f"/clientes/{a['id_cliente']}/enderecos/{id_end}", headers=h)

    assert db.get(Endereco, id_end) is not None
    assert client.get(f"/clientes/{b['id_cliente']}", headers=h).json()["enderecos"]
    assert client.get(f"/clientes/{a['id_cliente']}", headers=h).json()["enderecos"] == []


def _venda(db, id_cliente, id_endereco):
    usuario = db.scalar(select(Usuario))
    db.add(
        Venda(
            data_venda=datetime.now(UTC), valor_total=Decimal("0"), forma_pagamento="pix",
            status="em_aberto", id_cliente=id_cliente, id_usuario=usuario.id_usuario,
            id_endereco=id_endereco,
        )
    )  # fmt: skip
    db.flush()


def test_endereco_usado_em_pedido_e_inativado_e_nao_apagado(client, db, h):
    cliente = _criar(client, h, enderecos=[ENDERECO, OUTRO_ENDERECO]).json()
    id_, id_end = cliente["id_cliente"], cliente["enderecos"][0]["id_endereco"]
    _venda(db, id_, id_end)

    corpo = client.delete(f"/clientes/{id_}/enderecos/{id_end}", headers=h).json()

    assert [e["id_endereco"] for e in corpo["enderecos"]] == [
        cliente["enderecos"][1]["id_endereco"]
    ]
    assert db.get(Endereco, id_end).is_ativo is False  # histórico preservado
    assert db.get(ClienteEndereco, (id_, id_end)) is not None


def test_endereco_usado_em_pedido_e_compartilhado_nao_pode_ser_removido(client, db, h):
    a = _criar(client, h, telefone="16999990001", enderecos=[ENDERECO]).json()
    _criar(client, h, telefone="16999990002", enderecos=[ENDERECO])
    id_end = a["enderecos"][0]["id_endereco"]
    _venda(db, a["id_cliente"], id_end)

    resposta = client.delete(f"/clientes/{a['id_cliente']}/enderecos/{id_end}", headers=h)

    assert resposta.status_code == 409
    assert db.get(Endereco, id_end).is_ativo is True


def test_recadastrar_endereco_inativado_o_reativa(client, db, h):
    cliente = _criar(client, h, enderecos=[ENDERECO]).json()
    id_, id_end = cliente["id_cliente"], cliente["enderecos"][0]["id_endereco"]
    _venda(db, id_, id_end)
    client.delete(f"/clientes/{id_}/enderecos/{id_end}", headers=h)

    corpo = _end(client, h, id_, numero="777").json()

    assert corpo["enderecos"][0]["id_endereco"] == id_end
    assert corpo["enderecos"][0]["numero"] == "777"
    assert corpo["endereco_principal"]["id_endereco"] == id_end
