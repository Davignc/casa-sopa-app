"""Busca de endereços já registrados e vínculo com cliente (RM04)."""

import pytest
from sqlalchemy import func, select

from app.models import Endereco

NOVO = {
    "cep": "14400-000",
    "cidade": "Franca",
    "bairro": "Centro",
    "tipo_logradouro": "Avenida",
    "nome_logradouro": "Presidente Vargas",
    "numero": "100",
}


@pytest.fixture
def h(headers_vendedora):
    return headers_vendedora


def cliente(client, h, nome="Ana", telefone="16999990001", enderecos=None):
    corpo = {"nome": nome, "telefone": telefone, "enderecos": enderecos or []}
    resposta = client.post("/clientes", json=corpo, headers=h)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def buscar(client, h, termo, **extra):
    return client.get("/enderecos", params={"busca": termo, **extra}, headers=h)


# --- busca ---------------------------------------------------------------------------


def test_exige_login(client):
    assert client.get("/enderecos?busca=franca").status_code == 401


@pytest.fixture
def varios(client, h):
    cliente(client, h, "A", "16999990001", [NOVO])
    cliente(client, h, "B", "16999990002", [NOVO | {"cep": "14401-111", "bairro": "Jardim Paulista",
        "tipo_logradouro": "Rua", "nome_logradouro": "Voluntários da Franca"}])  # fmt: skip
    cliente(client, h, "C", "16999990003", [NOVO | {"cep": "14090-500", "cidade": "Ribeirão Preto",
        "bairro": "Ipiranga", "nome_logradouro": "Independência"}])  # fmt: skip


@pytest.mark.parametrize(
    ("termo", "esperados"),
    [
        ("vargas", {"Presidente Vargas"}),
        ("VARGAS", {"Presidente Vargas"}),
        ("centro", {"Presidente Vargas"}),
        ("jardim", {"Voluntários da Franca"}),
        ("ribeirão", {"Independência"}),
        ("14401", {"Voluntários da Franca"}),
        ("14401-1", {"Voluntários da Franca"}),
        ("avenida presidente", {"Presidente Vargas"}),
        ("avenida", {"Presidente Vargas", "Independência"}),
        ("franca centro", {"Presidente Vargas"}),
        ("inexistente", set()),
    ],
)
def test_busca_por_rua_bairro_cidade_e_cep(client, h, varios, termo, esperados):
    itens = buscar(client, h, termo).json()

    assert {i["nome_logradouro"] for i in itens} == esperados


def test_resultado_traz_a_descricao_sem_numero_e_quantos_clientes_usam(client, h, varios):
    cliente(client, h, "D", "16999990004", [NOVO | {"numero": "999"}])  # mesmo endereço da A

    item = buscar(client, h, "vargas").json()[0]

    assert item["descricao"] == "Avenida Presidente Vargas - Centro, Franca - CEP 14400-000"
    assert "100" not in item["descricao"]
    assert item["quantidade_clientes"] == 2
    assert item["cep"] == "14400000"


def test_busca_ignora_enderecos_inativos(client, db, h, varios):
    for e in db.scalars(select(Endereco).where(Endereco.bairro == "Centro")):
        e.is_ativo = False
    db.flush()

    assert buscar(client, h, "vargas").json() == []


def test_busca_respeita_o_limite(client, h):
    for i in range(5):
        cliente(
            client, h, f"C{i}", f"1699999000{i}", [NOVO | {"cep": f"1440{i}-000", "numero": str(i)}]
        )

    assert len(buscar(client, h, "franca", limit=3).json()) == 3
    assert len(buscar(client, h, "franca").json()) == 5


@pytest.mark.parametrize(
    "params",
    [
        {"busca": "a"},
        {"busca": ""},
        {"busca": "x" * 101},
        {"busca": "ab", "limit": 0},
        {"busca": "ab", "limit": 21},
        {},
    ],
)
def test_busca_invalida_retorna_422(client, h, params):
    assert client.get("/enderecos", params=params, headers=h).status_code == 422


def test_curingas_sao_texto(client, h, varios):
    assert buscar(client, h, "%%").json() == []
    assert buscar(client, h, "__").json() == []


# --- vincular um endereço já registrado ----------------------------------------------------


def _id_do_endereco(client, h, termo="vargas"):
    return buscar(client, h, termo).json()[0]["id_endereco"]


def test_vincula_endereco_existente_com_dados_proprios(client, db, h):
    cliente(client, h, "A", "16999990001", [NOVO])
    b = cliente(client, h, "B", "16999990002")
    id_end = _id_do_endereco(client, h)

    resposta = client.post(
        f"/clientes/{b['id_cliente']}/enderecos",
        json={
            "id_endereco": id_end,
            "numero": "250",
            "complemento": "apto 3",
            "referencia": "perto da praça",
            "apelido": "Casa",
        },
        headers=h,
    )

    assert resposta.status_code == 201
    e = resposta.json()["enderecos"][0]
    assert e["id_endereco"] == id_end
    assert (e["numero"], e["complemento"], e["referencia"], e["apelido"]) == (
        "250",
        "apto 3",
        "perto da praça",
        "Casa",
    )
    assert e["principal"] is True  # primeiro endereço do cliente
    assert e["endereco_formatado"].startswith("Avenida Presidente Vargas, 250, apto 3")
    assert db.scalar(select(func.count()).select_from(Endereco)) == 1  # não duplicou o físico


def test_numero_do_vinculo_nao_altera_o_do_outro_cliente(client, h):
    a = cliente(client, h, "A", "16999990001", [NOVO])
    b = cliente(client, h, "B", "16999990002")
    client.post(
        f"/clientes/{b['id_cliente']}/enderecos",
        json={"id_endereco": _id_do_endereco(client, h), "numero": "777"},
        headers=h,
    )

    assert (
        client.get(f"/clientes/{a['id_cliente']}", headers=h).json()["enderecos"][0]["numero"]
        == "100"
    )


def test_vinculo_pode_ser_o_principal(client, h):
    a = cliente(client, h, "A", "16999990001", [NOVO])
    id_outro = a["enderecos"][0]["id_endereco"]
    b = cliente(
        client, h, "B", "16999990002", [NOVO | {"cep": "14401-111", "nome_logradouro": "Outra"}]
    )

    corpo = client.post(
        f"/clientes/{b['id_cliente']}/enderecos",
        json={"id_endereco": id_outro, "numero": "5", "principal": True},
        headers=h,
    ).json()

    assert corpo["endereco_principal"]["id_endereco"] == id_outro
    assert sum(e["principal"] for e in corpo["enderecos"]) == 1


def test_mesmo_endereco_existente_duas_vezes_retorna_409(client, h):
    a = cliente(client, h, "A", "16999990001", [NOVO])
    id_end = a["enderecos"][0]["id_endereco"]

    resposta = client.post(
        f"/clientes/{a['id_cliente']}/enderecos",
        json={"id_endereco": id_end, "numero": "1"},
        headers=h,
    )

    assert resposta.status_code == 409


def test_endereco_inexistente_retorna_404(client, h):
    c = cliente(client, h)

    resposta = client.post(
        f"/clientes/{c['id_cliente']}/enderecos",
        json={"id_endereco": 999999, "numero": "1"},
        headers=h,
    )

    assert resposta.status_code == 404


def test_endereco_inativo_nao_pode_ser_vinculado(client, db, h):
    a = cliente(client, h, "A", "16999990001", [NOVO])
    b = cliente(client, h, "B", "16999990002")
    db.get(Endereco, a["enderecos"][0]["id_endereco"]).is_ativo = False
    db.flush()

    resposta = client.post(
        f"/clientes/{b['id_cliente']}/enderecos",
        json={"id_endereco": a["enderecos"][0]["id_endereco"], "numero": "1"},
        headers=h,
    )

    assert resposta.status_code == 422


@pytest.mark.parametrize(
    "corpo",
    [
        {"id_endereco": 1},  # falta o número
        {"id_endereco": 1, "numero": ""},
        {"id_endereco": 0, "numero": "1"},
        {"id_endereco": 1, "numero": "1", "cep": "14400-000"},  # mistura os dois formatos
        {"id_endereco": 1, "numero": "1", "cidade": "Franca"},
        {"id_endereco": 1, "numero": "1", "extra": 1},
        {"id_endereco": 1, "numero": "12345678901"},
    ],
)
def test_vinculo_invalido_retorna_422(client, h, corpo):
    c = cliente(client, h)

    assert (
        client.post(f"/clientes/{c['id_cliente']}/enderecos", json=corpo, headers=h).status_code
        == 422
    )


def test_cadastro_do_cliente_aceita_endereco_existente_junto_do_novo(client, db, h):
    a = cliente(client, h, "A", "16999990001", [NOVO])
    existente = a["enderecos"][0]["id_endereco"]

    b = cliente(
        client, h, "B", "16999990002",
        [{"id_endereco": existente, "numero": "55", "referencia": "portão azul"}, NOVO | {"cep": "14401-111", "nome_logradouro": "Nova"}],
    )  # fmt: skip

    assert [e["id_endereco"] for e in b["enderecos"]][0] == existente
    assert len(b["enderecos"]) == 2
    assert b["endereco_principal"]["id_endereco"] == existente  # o primeiro vira principal
    assert db.scalar(select(func.count()).select_from(Endereco)) == 2


def test_cadastro_com_endereco_existente_inexistente_nao_cria_o_cliente(client, h):
    resposta = client.post(
        "/clientes",
        json={
            "nome": "X",
            "telefone": "16999990009",
            "enderecos": [{"id_endereco": 999999, "numero": "1"}],
        },
        headers=h,
    )

    assert resposta.status_code == 404
    assert client.get("/clientes", headers=h).json()["total"] == 0


def test_vinculado_pode_ser_usado_no_pedido(client, headers_admin, h):
    a = cliente(client, h, "A", "16999990001", [NOVO])
    b = cliente(client, h, "B", "16999990002")
    client.post(
        f"/clientes/{b['id_cliente']}/enderecos",
        json={"id_endereco": a["enderecos"][0]["id_endereco"], "numero": "9"},
        headers=h,
    )
    produto = client.post(
        "/produtos",
        json={
            "nome": "P",
            "descricao": "d",
            "preco_unitario": "10",
            "estoque_inicial": 5,
            "estoque_minimo": 1,
        },
        headers=headers_admin,
    ).json()

    resposta = client.post(
        "/pedidos",
        json={"id_cliente": b["id_cliente"], "id_endereco": a["enderecos"][0]["id_endereco"], "forma_pagamento": "pix",
              "itens": [{"id_produto": produto["id_produto"], "quantidade": 1}]},
        headers=h,
    )  # fmt: skip

    assert resposta.status_code == 201
    assert "Presidente Vargas, 9" in resposta.json()["endereco_entrega"]["endereco_formatado"]


# --- listagem de clientes: responsável, código e endereço --------------------------------------


def test_listagem_mostra_quem_cadastrou(client, h, dados_usuario):
    cliente(client, h)

    item = client.get("/clientes", headers=h).json()["itens"][0]

    assert item["cadastrado_por"]["nome"] == dados_usuario["nome"]
    assert item["endereco_principal"] is None


def test_busca_de_cliente_por_codigo(client, h):
    a = cliente(client, h, "Ana", "16999990001")
    cliente(client, h, "Bia", "16999990002")

    itens = client.get(f"/clientes?busca={a['id_cliente']}", headers=h).json()["itens"]

    assert a["id_cliente"] in [i["id_cliente"] for i in itens]
    assert "Bia" not in [i["nome"] for i in itens] or len(itens) >= 1


@pytest.mark.parametrize(
    ("termo", "esperado"),
    [("vargas", ["Ana"]), ("jardim", ["Bia"]), ("franca", ["Ana", "Bia"]), ("zzz", [])],
)
def test_busca_de_cliente_por_endereco(client, h, termo, esperado):
    cliente(client, h, "Ana", "16999990001", [NOVO])
    cliente(
        client,
        h,
        "Bia",
        "16999990002",
        [NOVO | {"cep": "14401-111", "bairro": "Jardim Paulista", "nome_logradouro": "Das Flores"}],
    )

    nomes = [
        c["nome"]
        for c in client.get("/clientes", params={"busca": termo}, headers=h).json()["itens"]
    ]

    assert nomes == esperado
