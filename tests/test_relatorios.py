"""RF27 e RF28: dashboard, vendas por vendedora, lista de pedidos e exportação."""

import csv
from datetime import timedelta
from decimal import Decimal
from io import BytesIO, StringIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.core.tempo import agora_utc, fim_do_dia_exclusivo_utc, hoje_local
from app.models import Usuario, Venda
from app.schemas.usuario import UsuarioCreate
from app.services import relatorio as relatorio_service
from app.services import usuario as usuario_service

ENDERECO = {
    "cep": "14400-000",
    "cidade": "Franca",
    "bairro": "Centro",
    "tipo_logradouro": "Rua",
    "nome_logradouro": "Das Flores",
    "numero": "10",
}


@pytest.fixture
def cenario(client, headers_admin):
    cliente = client.post(
        "/clientes",
        json={"nome": "Cliente Teste", "telefone": "16999990001", "enderecos": [ENDERECO]},
        headers=headers_admin,
    ).json()

    def produto(nome, preco):
        return client.post(
            "/produtos",
            json={
                "nome": nome,
                "descricao": "d",
                "preco_unitario": preco,
                "estoque_inicial": 1000,
                "estoque_minimo": 1,
            },
            headers=headers_admin,
        ).json()["id_produto"]

    return {
        "id_cliente": cliente["id_cliente"],
        "id_endereco": cliente["enderecos"][0]["id_endereco"],
        "a": produto("Produto A", "10.00"),
        "b": produto("Produto B", "25.90"),
    }


@pytest.fixture
def vendedoras(client, db):
    """Maria (10%), Joana (5%) e Sem Comissão (sem percentual)."""
    out = {}
    for chave, nome, comissao in [
        ("maria", "Maria", "10"),
        ("joana", "Joana", "5"),
        ("zero", "Zero", None),
    ]:
        dados = {
            "nome": nome,
            "email": f"{chave}@casadasopa.org",
            "telefone": f"1698{len(out):07d}",
            "cargo": "vendedora",
            "comissao": comissao,
            "senha": "senhaForte123",
        }
        usuario = usuario_service.criar_usuario(db, UsuarioCreate(**dados))
        token = client.post(
            "/auth/login/json", json={"email": dados["email"], "senha": dados["senha"]}
        ).json()["access_token"]
        out[chave] = {"id": usuario.id_usuario, "h": {"Authorization": f"Bearer {token}"}}
    return out


def pedido(client, headers, c, itens, status=None):
    resposta = client.post(
        "/pedidos",
        json={
            "id_cliente": c["id_cliente"],
            "id_endereco": c["id_endereco"],
            "forma_pagamento": "pix",
            "itens": [{"id_produto": p, "quantidade": q} for p, q in itens],
        },
        headers=headers,
    )
    assert resposta.status_code == 201, resposta.text
    id_ = resposta.json()["id_pedido"]
    caminho = {
        None: [],
        "confirmado": ["confirmado"],
        "entregue": ["confirmado", "entregue"],
        "cancelado": ["cancelado"],
    }[status]
    for passo in caminho:
        assert (
            client.post(
                f"/pedidos/{id_}/status", json={"status": passo}, headers=headers
            ).status_code
            == 200
        )
    return id_


@pytest.fixture
def vendas(client, cenario, vendedoras):
    """Maria: 20,00 entregue + 10,00 confirmado (+ 1 em aberto + 1 cancelado, que não contam).
    Joana: 77,70 entregue."""
    m, j = vendedoras["maria"]["h"], vendedoras["joana"]["h"]
    ids = {
        "maria_entregue": pedido(client, m, cenario, [(cenario["a"], 2)], "entregue"),
        "maria_confirmado": pedido(client, m, cenario, [(cenario["a"], 1)], "confirmado"),
        "maria_aberto": pedido(client, m, cenario, [(cenario["a"], 5)]),
        "maria_cancelado": pedido(client, m, cenario, [(cenario["a"], 9)], "cancelado"),
        "joana_entregue": pedido(client, j, cenario, [(cenario["b"], 3)], "entregue"),
    }
    return ids


# --- permissões ---------------------------------------------------------------------

ROTAS = [
    "/relatorios/dashboard",
    "/relatorios/vendas",
    "/relatorios/vendas/pedidos",
    "/relatorios/vendas/exportar",
]


@pytest.mark.parametrize("rota", ROTAS)
def test_sem_token_recebe_401(client, rota):
    assert client.get(rota).status_code == 401


@pytest.mark.parametrize("rota", ROTAS)
def test_vendedora_nao_acessa_relatorios(client, headers_vendedora, rota):
    assert client.get(rota, headers=headers_vendedora).status_code == 403


# --- dashboard (RF27) ------------------------------------------------------------------


def test_dashboard_conta_so_pedidos_confirmados_e_entregues(client, headers_admin, vendas):
    d = client.get("/relatorios/dashboard", headers=headers_admin).json()

    assert d["total_pedidos"] == 3
    assert d["produtos_vendidos"] == 6  # 2 + 1 + 3
    assert d["faturamento"] == "107.70"  # 20,00 + 10,00 + 77,70
    assert d["pedidos_por_status"] == {
        "em_aberto": 1,
        "confirmado": 1,
        "entregue": 2,
        "cancelado": 1,
    }


def test_dashboard_comissoes(client, headers_admin, vendas):
    d = client.get("/relatorios/dashboard", headers=headers_admin).json()

    # a receber (entregues): Maria 10% de 20,00 = 2,00; Joana 5% de 77,70 = 3,885 -> 3,89
    assert d["comissoes"] == "5.89"
    # pendente (confirmados): Maria 10% de 10,00 = 1,00
    assert d["comissoes_pendentes"] == "1.00"


def test_dashboard_periodo_sao_os_ultimos_30_dias(client, headers_admin, vendas):
    d = client.get("/relatorios/dashboard", headers=headers_admin).json()

    assert d["periodo"]["fim"] == hoje_local().isoformat()
    assert d["periodo"]["inicio"] == (hoje_local() - timedelta(days=29)).isoformat()


def test_dashboard_ignora_vendas_antigas(client, db, headers_admin, vendas):
    antigo = db.get(Venda, vendas["joana_entregue"])
    antigo.data_venda = agora_utc() - timedelta(days=45)
    db.flush()

    d = client.get("/relatorios/dashboard", headers=headers_admin).json()

    assert d["faturamento"] == "30.00"
    assert d["total_pedidos"] == 2


def test_dashboard_vazio(client, headers_admin):
    d = client.get("/relatorios/dashboard", headers=headers_admin).json()

    assert (d["total_pedidos"], d["produtos_vendidos"], d["faturamento"], d["comissoes"]) == (
        0,
        0,
        "0.00",
        "0.00",
    )
    assert d["pedidos_por_status"] == {
        "em_aberto": 0,
        "confirmado": 0,
        "entregue": 0,
        "cancelado": 0,
    }


# --- vendas por vendedora (RF28) -----------------------------------------------------------


def _por_nome(corpo):
    return {v["nome"]: v for v in corpo["vendedoras"]}


def test_vendas_por_vendedora(client, headers_admin, vendas):
    corpo = client.get("/relatorios/vendas", headers=headers_admin).json()

    v = _por_nome(corpo)
    assert (v["Maria"]["quantidade_pedidos"], v["Maria"]["produtos_vendidos"]) == (2, 3)
    assert v["Maria"]["valor_total"] == "30.00"
    assert v["Maria"]["comissao_a_receber"] == "2.00"
    assert v["Maria"]["comissao_pendente"] == "1.00"
    assert v["Maria"]["comissao_percentual"] == "10.00"
    assert (v["Joana"]["quantidade_pedidos"], v["Joana"]["valor_total"]) == (1, "77.70")
    assert v["Joana"]["comissao_a_receber"] == "3.89"
    assert "Zero" not in v  # sem vendas, não aparece (a menos que seja pedida)


def test_totais_batem_com_a_soma_das_vendedoras(client, headers_admin, vendas):
    corpo = client.get("/relatorios/vendas", headers=headers_admin).json()

    t = corpo["totais"]
    assert t["quantidade_pedidos"] == 3
    assert t["produtos_vendidos"] == 6
    assert t["valor_total"] == "107.70"
    assert t["comissao_a_receber"] == "5.89"
    assert t["comissao_pendente"] == "1.00"


def test_ordenado_por_valor_vendido(client, headers_admin, vendas):
    nomes = [
        v["nome"]
        for v in client.get("/relatorios/vendas", headers=headers_admin).json()["vendedoras"]
    ]

    assert nomes == ["Joana", "Maria"]  # 77,70 antes de 30,00


def test_filtra_por_vendedora(client, headers_admin, vendas, vendedoras):
    corpo = client.get(
        f"/relatorios/vendas?id_vendedora={vendedoras['maria']['id']}", headers=headers_admin
    ).json()

    assert [v["nome"] for v in corpo["vendedoras"]] == ["Maria"]
    assert corpo["totais"]["valor_total"] == "30.00"


def test_vendedora_sem_vendas_aparece_zerada_quando_pedida(
    client, headers_admin, vendas, vendedoras
):
    corpo = client.get(
        f"/relatorios/vendas?id_vendedora={vendedoras['zero']['id']}", headers=headers_admin
    ).json()

    v = corpo["vendedoras"][0]
    assert (v["nome"], v["quantidade_pedidos"], v["valor_total"], v["comissao_a_receber"]) == (
        "Zero",
        0,
        "0.00",
        "0.00",
    )


def test_vendedora_sem_percentual_tem_comissao_zero(client, headers_admin, cenario, vendedoras):
    pedido(client, vendedoras["zero"]["h"], cenario, [(cenario["a"], 4)], "entregue")

    v = client.get(
        f"/relatorios/vendas?id_vendedora={vendedoras['zero']['id']}", headers=headers_admin
    ).json()["vendedoras"][0]

    assert v["valor_total"] == "40.00"
    assert v["comissao_percentual"] is None
    assert v["comissao_a_receber"] == "0.00"


def test_vendedora_inexistente_ou_administradora_retorna_404(
    client, headers_admin, db, admin_cadastrada
):
    admin = db.scalar(select(Usuario).where(Usuario.email == admin_cadastrada["email"]))

    assert (
        client.get("/relatorios/vendas?id_vendedora=999999", headers=headers_admin).status_code
        == 404
    )
    assert (
        client.get(
            f"/relatorios/vendas?id_vendedora={admin.id_usuario}", headers=headers_admin
        ).status_code
        == 404
    )


def test_periodo_informado(client, db, headers_admin, vendas):
    db.get(Venda, vendas["joana_entregue"]).data_venda = agora_utc() - timedelta(days=100)
    db.flush()
    hoje = hoje_local()

    recente = client.get(
        f"/relatorios/vendas?data_inicio={hoje - timedelta(days=10)}&data_fim={hoje}",
        headers=headers_admin,
    ).json()
    antigo = client.get(
        "/relatorios/vendas"
        f"?data_inicio={hoje - timedelta(days=120)}&data_fim={hoje - timedelta(days=60)}",
        headers=headers_admin,
    ).json()

    assert recente["totais"]["valor_total"] == "30.00"
    assert [v["nome"] for v in antigo["vendedoras"]] == ["Joana"]
    assert antigo["periodo"]["inicio"] == str(hoje - timedelta(days=120))


def test_limites_do_periodo_respeitam_o_fuso_local(client, db, headers_admin, vendas):
    """Uma venda às 23h59 do último dia (horário local) entra; à 00h00 do dia seguinte, não."""
    dia = hoje_local() - timedelta(days=3)
    ultimo_instante = fim_do_dia_exclusivo_utc(dia) - timedelta(minutes=1)
    proximo_dia = fim_do_dia_exclusivo_utc(dia)
    db.get(Venda, vendas["maria_entregue"]).data_venda = ultimo_instante  # 20,00
    db.get(Venda, vendas["maria_confirmado"]).data_venda = proximo_dia  # 10,00
    db.flush()

    corpo = client.get(
        f"/relatorios/vendas?data_inicio={dia}&data_fim={dia}&id_vendedora="
        + str(db.get(Venda, vendas["maria_entregue"]).id_usuario),
        headers=headers_admin,
    ).json()

    assert corpo["totais"]["valor_total"] == "20.00"
    assert corpo["totais"]["quantidade_pedidos"] == 1


@pytest.mark.parametrize(
    "query",
    [
        "data_inicio=2026-02-01&data_fim=2026-01-01",
        "data_inicio=2020-01-01&data_fim=2026-01-01",  # mais de 1 ano
        "data_inicio=abc",
        "id_vendedora=0",
    ],
)
def test_filtros_invalidos_retornam_422(client, headers_admin, query):
    assert client.get(f"/relatorios/vendas?{query}", headers=headers_admin).status_code == 422


# --- lista de pedidos do relatório ----------------------------------------------------------


def test_lista_detalhada_traz_so_vendas_por_padrao(client, headers_admin, vendas):
    corpo = client.get("/relatorios/vendas/pedidos", headers=headers_admin).json()

    assert corpo["total"] == 3
    assert {p["status"] for p in corpo["itens"]} == {"confirmado", "entregue"}
    assert all(p["itens"] and p["cliente"] and p["vendedora"] for p in corpo["itens"])


def test_lista_detalhada_por_vendedora_e_status(client, headers_admin, vendas, vendedoras):
    maria = vendedoras["maria"]["id"]

    todos = client.get(
        f"/relatorios/vendas/pedidos?id_vendedora={maria}", headers=headers_admin
    ).json()
    abertos = client.get(
        f"/relatorios/vendas/pedidos?id_vendedora={maria}&status=em_aberto", headers=headers_admin
    ).json()

    assert todos["total"] == 2
    assert {p["vendedora"]["id_usuario"] for p in todos["itens"]} == {maria}
    assert [p["id_pedido"] for p in abertos["itens"]] == [vendas["maria_aberto"]]


def test_lista_detalhada_paginada(client, headers_admin, vendas):
    p1 = client.get("/relatorios/vendas/pedidos?limit=2", headers=headers_admin).json()
    p2 = client.get("/relatorios/vendas/pedidos?limit=2&offset=2", headers=headers_admin).json()

    assert (len(p1["itens"]), len(p2["itens"]), p1["total"]) == (2, 1, 3)


# --- exportação -----------------------------------------------------------------------------


def _planilha(resposta):
    return load_workbook(BytesIO(resposta.content))


def test_exporta_xlsx_com_resumo_e_pedidos(client, headers_admin, vendas):
    resposta = client.get("/relatorios/vendas/exportar", headers=headers_admin)

    assert resposta.status_code == 200
    assert "spreadsheetml" in resposta.headers["content-type"]
    assert resposta.headers["content-disposition"].startswith('attachment; filename="vendas_')
    assert resposta.headers["content-disposition"].endswith('.xlsx"')
    pasta = _planilha(resposta)
    assert pasta.sheetnames == ["Resumo", "Pedidos"]
    resumo = list(pasta["Resumo"].values)
    assert resumo[2][0] == "Vendedora"
    por_nome = {linha[0]: linha for linha in resumo[3:] if linha[0]}
    assert por_nome["Maria"][4] == 30.0
    assert por_nome["Joana"][5] == 3.89
    assert por_nome["TOTAL"][4] == pytest.approx(107.70)
    pedidos = list(pasta["Pedidos"].values)
    assert pedidos[0][0] == "Pedido"
    assert len(pedidos) == 1 + 3
    assert isinstance(pedidos[1][7], int | float)  # total numérico, não texto


def test_exporta_csv_para_excel_brasileiro(client, headers_admin, vendas):
    resposta = client.get("/relatorios/vendas/exportar?formato=csv", headers=headers_admin)

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/csv")
    assert resposta.content.startswith(b"\xef\xbb\xbf")  # BOM: acentos certos no Excel
    linhas = resposta.content.decode("utf-8-sig").strip().split("\r\n")
    assert linhas[0] == "Pedido;Data;Vendedora;Cliente;Situação;Pagamento;Produtos;Total"
    assert len(linhas) == 1 + 3
    assert any(linha.endswith(";77,70") for linha in linhas)  # decimal com vírgula


def test_exportacao_respeita_filtros(client, headers_admin, vendas, vendedoras):
    resposta = client.get(
        f"/relatorios/vendas/exportar?formato=csv&id_vendedora={vendedoras['joana']['id']}",
        headers=headers_admin,
    )

    assert len(resposta.content.decode("utf-8-sig").strip().split("\r\n")) == 2


@pytest.mark.parametrize("formato", ["csv", "xlsx"])
def test_exportacao_neutraliza_injecao_de_formula(
    client, headers_admin, cenario, vendedoras, formato
):
    cliente = client.post(
        "/clientes",
        json={
            "nome": '=HYPERLINK("http://mal.example","clique")',
            "telefone": "16999990055",
            "enderecos": [ENDERECO],
        },
        headers=headers_admin,
    ).json()
    c = cenario | {
        "id_cliente": cliente["id_cliente"],
        "id_endereco": cliente["enderecos"][0]["id_endereco"],
    }
    pedido(client, vendedoras["maria"]["h"], c, [(cenario["a"], 1)], "confirmado")

    resposta = client.get(f"/relatorios/vendas/exportar?formato={formato}", headers=headers_admin)

    if formato == "csv":
        linhas = list(csv.reader(StringIO(resposta.content.decode("utf-8-sig")), delimiter=";"))
        celulas = [linha[3] for linha in linhas[1:]]
        assert celulas == ['\'=HYPERLINK("http://mal.example","clique")']
        assert not any(c.startswith("=") for c in celulas)
    else:
        celulas = [linha[3] for linha in _planilha(resposta)["Pedidos"].values][1:]
        assert celulas == ['\'=HYPERLINK("http://mal.example","clique")']
        assert not any(str(c).startswith("=") for c in celulas)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("=1+1", "'=1+1"),
        ("+55", "'+55"),
        ("-2", "'-2"),
        ("@x", "'@x"),
        ("\tcmd", "'\tcmd"),
        ("Maria", "Maria"),
        ("", ""),
        (None, ""),
    ],
)
def test_texto_seguro(valor, esperado):
    assert relatorio_service._texto_seguro(valor) == esperado


def test_exportacao_grande_demais_e_recusada(client, headers_admin, vendas, monkeypatch):
    monkeypatch.setattr(relatorio_service, "MAX_LINHAS_EXPORTACAO", 2)

    assert client.get("/relatorios/vendas/exportar", headers=headers_admin).status_code == 422


@pytest.mark.parametrize(
    "query", ["formato=pdf", "formato=", "data_inicio=2026-02-01&data_fim=2026-01-01"]
)
def test_exportacao_com_parametro_invalido_retorna_422(client, headers_admin, query):
    assert (
        client.get(f"/relatorios/vendas/exportar?{query}", headers=headers_admin).status_code == 422
    )


def test_comissao_usa_arredondamento_comercial():
    assert relatorio_service._comissao(Decimal("77.70"), Decimal("5.00")) == Decimal("3.89")
    assert relatorio_service._comissao(Decimal("10.00"), None) == Decimal("0.00")
    assert relatorio_service._comissao(Decimal("10.00"), Decimal("0")) == Decimal("0.00")
