"""Dados dos gráficos, contagem de pedidos e resumo das movimentações."""

from datetime import date, timedelta

import pytest

from app.core import periodos
from app.core.errors import RegraInvalidaError
from app.core.periodos import escolher_agrupamento, gerar_baldes, inicio_do_balde, janela
from app.core.tempo import agora_utc, fim_do_dia_exclusivo_utc, hoje_local
from app.models import Movimentacao, Venda
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


# --- períodos (unitários) -----------------------------------------------------------------


def test_janela_padrao_sao_os_ultimos_30_dias():
    inicio, fim = janela(None, None)

    assert fim == hoje_local()
    assert (fim - inicio).days == 29


def test_janela_valida_a_ordem_e_o_limite_de_um_ano():
    with pytest.raises(RegraInvalidaError):
        janela(date(2026, 2, 1), date(2026, 1, 1))
    with pytest.raises(RegraInvalidaError):
        janela(date(2025, 1, 1), date(2026, 6, 1))
    assert janela(date(2026, 1, 1), date(2026, 1, 1)) == (date(2026, 1, 1), date(2026, 1, 1))


@pytest.mark.parametrize(
    ("dias", "esperado"),
    [(1, "dia"), (45, "dia"), (46, "semana"), (200, "semana"), (201, "mes"), (366, "mes")],
)
def test_agrupamento_automatico_conforme_o_tamanho(dias, esperado):
    fim = date(2026, 12, 31)

    assert escolher_agrupamento(fim - timedelta(days=dias - 1), fim) == esperado


def test_baldes_por_dia_incluem_os_dois_extremos():
    baldes = gerar_baldes(date(2026, 3, 1), date(2026, 3, 5), "dia")

    assert baldes == [date(2026, 3, d) for d in range(1, 6)]


def test_baldes_por_semana_comecam_na_segunda():
    # 2026-10-28 é quarta: a primeira semana começa na segunda 2026-10-26
    baldes = gerar_baldes(date(2026, 10, 28), date(2026, 11, 10), "semana")

    assert baldes == [date(2026, 10, 26), date(2026, 11, 2), date(2026, 11, 9)]
    assert all(b.weekday() == 0 for b in baldes)


def test_baldes_por_mes_viram_o_ano_e_respeitam_bissexto():
    baldes = gerar_baldes(date(2027, 11, 15), date(2028, 3, 2), "mes")

    assert baldes == [
        date(2027, 11, 1),
        date(2027, 12, 1),
        date(2028, 1, 1),
        date(2028, 2, 1),
        date(2028, 3, 1),
    ]


@pytest.mark.parametrize(
    ("dia", "agrupar", "esperado"),
    [(date(2026, 10, 29), "dia", date(2026, 10, 29)), (date(2026, 10, 29), "semana", date(2026, 10, 26)),
     (date(2026, 10, 29), "mes", date(2026, 10, 1)), (date(2026, 10, 26), "semana", date(2026, 10, 26))],
)  # fmt: skip
def test_inicio_do_balde(dia, agrupar, esperado):
    assert inicio_do_balde(dia, agrupar) == esperado


def test_agrupamento_exportado_pelo_relatorio_e_o_mesmo():
    assert relatorio_service.escolher_agrupamento is periodos.escolher_agrupamento


# --- cenário com vendas ------------------------------------------------------------------------


@pytest.fixture
def cenario(client, headers_admin):
    def cliente(nome, fone, **end):
        return client.post(
            "/clientes",
            json={"nome": nome, "telefone": fone, "enderecos": [ENDERECO | end]},
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

    ana = cliente("Ana", "16999990001")
    bia = cliente("Bia", "16999990002", bairro="Jardim", cep="14401-111", nome_logradouro="Outra")
    return {
        "ana": (ana["id_cliente"], ana["enderecos"][0]["id_endereco"]),
        "bia": (bia["id_cliente"], bia["enderecos"][0]["id_endereco"]),
        "a": produto("Produto A", "10.00"),
        "b": produto("Produto B", "25.00"),
    }


@pytest.fixture
def vendedoras(client, db):
    saida = {}
    for i, (chave, nome, com) in enumerate([("maria", "Maria", "10"), ("joana", "Joana", "5")]):
        dados = {"nome": nome, "email": f"{chave}@x.org", "telefone": f"1698000000{i}", "cargo": "vendedora",
                 "comissao": com, "senha": "senhaForte123!"}  # fmt: skip
        u = usuario_service.criar_usuario(db, UsuarioCreate(**dados))
        token = client.post(
            "/auth/login/json", json={"email": dados["email"], "senha": dados["senha"]}
        ).json()["access_token"]
        saida[chave] = {"id": u.id_usuario, "h": {"Authorization": f"Bearer {token}"}}
    return saida


def vender(client, headers, cliente, itens, pagamento="pix", status="entregue"):
    id_cliente, id_endereco = cliente
    r = client.post(
        "/pedidos",
        json={"id_cliente": id_cliente, "id_endereco": id_endereco, "forma_pagamento": pagamento,
              "itens": [{"id_produto": p, "quantidade": q} for p, q in itens]},
        headers=headers,
    )  # fmt: skip
    assert r.status_code == 201, r.text
    id_ = r.json()["id_pedido"]
    for passo in {
        "entregue": ["confirmado", "entregue"],
        "confirmado": ["confirmado"],
        "cancelado": ["cancelado"],
        "em_aberto": [],
    }[status]:
        assert (
            client.post(
                f"/pedidos/{id_}/status", json={"status": passo}, headers=headers
            ).status_code
            == 200
        )
    return id_


@pytest.fixture
def vendas(client, cenario, vendedoras):
    m, j = vendedoras["maria"]["h"], vendedoras["joana"]["h"]
    return {
        "m1": vender(client, m, cenario["ana"], [(cenario["a"], 2)], "pix"),  # 20,00
        "m2": vender(
            client,
            m,
            cenario["ana"],
            [(cenario["a"], 3), (cenario["b"], 1)],
            "dinheiro",
            "confirmado",
        ),  # 55,00
        "j1": vender(client, j, cenario["bia"], [(cenario["b"], 4)], "pix"),  # 100,00
        "aberto": vender(client, m, cenario["bia"], [(cenario["a"], 9)], "pix", "em_aberto"),
        "cancelado": vender(client, j, cenario["bia"], [(cenario["a"], 9)], "pix", "cancelado"),
    }


def analise(client, headers, **params):
    resposta = client.get("/relatorios/analise", params=params, headers=headers)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


# --- /relatorios/analise ---------------------------------------------------------------------------


def test_analise_exige_administradora(client, headers_vendedora):
    assert client.get("/relatorios/analise").status_code == 401
    assert client.get("/relatorios/analise", headers=headers_vendedora).status_code == 403


def test_analise_vazia_traz_serie_zerada_e_listas_vazias(client, headers_admin):
    corpo = analise(client, headers_admin)

    assert corpo["agrupamento"] == "dia"
    assert len(corpo["serie"]) == 30
    assert {p["pedidos"] for p in corpo["serie"]} == {0}
    assert corpo["totais"]["valor_total"] == "0.00"
    assert (
        corpo["top_produtos"]
        == corpo["top_clientes"]
        == corpo["por_bairro"]
        == corpo["por_forma_pagamento"]
        == []
    )
    assert corpo["pedidos_por_status"] == {
        "em_aberto": 0,
        "confirmado": 0,
        "entregue": 0,
        "cancelado": 0,
    }


def test_totais_e_serie_batem(client, headers_admin, vendas):
    corpo = analise(client, headers_admin)

    assert corpo["totais"]["valor_total"] == "175.00"  # 20 + 55 + 100
    assert corpo["totais"]["quantidade_pedidos"] == 3
    assert sum(p["pedidos"] for p in corpo["serie"]) == 3
    assert sum(float(p["faturamento"]) for p in corpo["serie"]) == pytest.approx(175.0)
    assert corpo["serie"][-1]["inicio"] == hoje_local().isoformat()
    assert corpo["serie"][-1]["pedidos"] == 3  # tudo foi vendido hoje


def test_pedidos_por_status_incluem_aberto_e_cancelado(client, headers_admin, vendas):
    assert analise(client, headers_admin)["pedidos_por_status"] == {
        "em_aberto": 1, "confirmado": 1, "entregue": 2, "cancelado": 1,
    }  # fmt: skip


def test_por_forma_de_pagamento(client, headers_admin, vendas):
    formas = {f["nome"]: f for f in analise(client, headers_admin)["por_forma_pagamento"]}

    assert (formas["pix"]["quantidade"], formas["pix"]["valor"]) == (2, "120.00")
    assert (formas["dinheiro"]["quantidade"], formas["dinheiro"]["valor"]) == (1, "55.00")
    assert formas["pix"]["id"] is None


def test_produtos_mais_vendidos_por_unidades(client, headers_admin, cenario, vendas):
    produtos = analise(client, headers_admin)["top_produtos"]

    # empate em 5 unidades: desempata pelo nome. Em aberto e cancelado não contam.
    assert [(p["nome"], p["quantidade"], p["valor"]) for p in produtos] == [
        ("Produto A", 5, "50.00"),
        ("Produto B", 5, "125.00"),
    ]
    assert {p["id"] for p in produtos} == {cenario["a"], cenario["b"]}


def test_clientes_que_mais_compram_por_valor(client, headers_admin, cenario, vendas):
    clientes = analise(client, headers_admin)["top_clientes"]

    assert [(c["nome"], c["quantidade"], c["valor"]) for c in clientes] == [
        ("Bia", 1, "100.00"),
        ("Ana", 2, "75.00"),
    ]
    assert clientes[0]["id"] == cenario["bia"][0]


def test_vendas_por_bairro(client, headers_admin, vendas):
    bairros = analise(client, headers_admin)["por_bairro"]

    assert [(b["nome"], b["quantidade"], b["valor"]) for b in bairros] == [
        ("Jardim", 1, "100.00"),
        ("Centro", 2, "75.00"),
    ]


def test_por_vendedora_traz_comissao(client, headers_admin, vendas):
    v = {x["nome"]: x for x in analise(client, headers_admin)["por_vendedora"]}

    assert v["Maria"]["valor_total"] == "75.00"
    assert v["Maria"]["comissao_a_receber"] == "2.00"  # 10% de 20,00 (entregue)
    assert v["Maria"]["comissao_pendente"] == "5.50"  # 10% de 55,00 (confirmado)
    assert v["Joana"]["comissao_a_receber"] == "5.00"


def test_filtro_por_vendedora_muda_tudo(client, headers_admin, vendas, vendedoras):
    corpo = analise(client, headers_admin, id_vendedora=vendedoras["joana"]["id"])

    assert corpo["totais"]["valor_total"] == "100.00"
    assert [p["nome"] for p in corpo["top_clientes"]] == ["Bia"]
    assert [p["nome"] for p in corpo["por_vendedora"]] == ["Joana"]
    assert corpo["pedidos_por_status"] == {
        "em_aberto": 0,
        "confirmado": 0,
        "entregue": 1,
        "cancelado": 1,
    }
    assert sum(p["pedidos"] for p in corpo["serie"]) == 1


def test_vendedora_inexistente_retorna_404(client, headers_admin):
    assert (
        client.get("/relatorios/analise?id_vendedora=999999", headers=headers_admin).status_code
        == 404
    )


def test_periodo_antigo_nao_traz_as_vendas_de_hoje(client, headers_admin, vendas):
    hoje = hoje_local()

    corpo = analise(
        client,
        headers_admin,
        data_inicio=str(hoje - timedelta(days=60)),
        data_fim=str(hoje - timedelta(days=30)),
    )

    assert corpo["totais"]["valor_total"] == "0.00"
    assert corpo["periodo"]["inicio"] == str(hoje - timedelta(days=60))


def test_agrupamento_automatico_e_explicito(client, headers_admin, vendas):
    hoje = hoje_local()

    assert (
        analise(
            client, headers_admin, data_inicio=str(hoje - timedelta(days=89)), data_fim=str(hoje)
        )["agrupamento"]
        == "semana"
    )
    assert (
        analise(
            client, headers_admin, data_inicio=str(hoje - timedelta(days=300)), data_fim=str(hoje)
        )["agrupamento"]
        == "mes"
    )
    explicito = analise(client, headers_admin, agrupar="mes")
    assert explicito["agrupamento"] == "mes"
    assert len(explicito["serie"]) in (1, 2)
    assert sum(p["pedidos"] for p in explicito["serie"]) == 3


def test_serie_por_semana_so_tem_segundas(client, headers_admin, vendas):
    corpo = analise(client, headers_admin, agrupar="semana")

    assert all(date.fromisoformat(p["inicio"]).weekday() == 0 for p in corpo["serie"])
    assert sum(p["pedidos"] for p in corpo["serie"]) == 3


def test_venda_cai_no_dia_certo_pelo_horario_local(client, db, headers_admin, vendas):
    dia = hoje_local() - timedelta(days=5)
    antes_da_meia_noite = fim_do_dia_exclusivo_utc(dia) - timedelta(minutes=30)
    depois_da_meia_noite = fim_do_dia_exclusivo_utc(dia) + timedelta(minutes=30)
    db.get(Venda, vendas["m1"]).data_venda = antes_da_meia_noite
    db.get(Venda, vendas["j1"]).data_venda = depois_da_meia_noite
    db.flush()

    por_dia = {p["inicio"]: p for p in analise(client, headers_admin)["serie"]}

    assert por_dia[str(dia)]["pedidos"] == 1
    assert por_dia[str(dia)]["faturamento"] == "20.00"
    assert por_dia[str(dia + timedelta(days=1))]["faturamento"] == "100.00"


@pytest.mark.parametrize(
    "query",
    [
        "agrupar=ano",
        "data_inicio=2026-02-01&data_fim=2026-01-01",
        "data_inicio=2020-01-01&data_fim=2026-01-01",
        "id_vendedora=0",
    ],
)
def test_analise_com_filtro_invalido_retorna_422(client, headers_admin, query):
    assert client.get(f"/relatorios/analise?{query}", headers=headers_admin).status_code == 422


def test_rankings_sao_limitados(client, headers_admin, vendas, monkeypatch):
    monkeypatch.setattr(relatorio_service, "TOP", 1)

    corpo = analise(client, headers_admin)

    assert len(corpo["top_produtos"]) == len(corpo["top_clientes"]) == len(corpo["por_bairro"]) == 1


def test_analise_recusa_periodo_com_linhas_demais(client, headers_admin, vendas, monkeypatch):
    monkeypatch.setattr(relatorio_service, "MAX_LINHAS_ANALISE", 1)

    assert client.get("/relatorios/analise", headers=headers_admin).status_code == 422


# --- /pedidos/contagem ------------------------------------------------------------------------------


def test_contagem_exige_login(client):
    assert client.get("/pedidos/contagem").status_code == 401


def test_contagem_por_status(client, headers_vendedora, vendas):
    corpo = client.get("/pedidos/contagem", headers=headers_vendedora)

    assert corpo.status_code == 200  # "contagem" não é confundido com o id de um pedido
    assert corpo.json() == {
        "todos": 5,
        "em_aberto": 1,
        "confirmado": 1,
        "entregue": 2,
        "cancelado": 1,
    }


def test_contagem_bate_com_a_listagem(client, headers_vendedora, vendas):
    contagem = client.get("/pedidos/contagem", headers=headers_vendedora).json()

    for status in ("em_aberto", "confirmado", "entregue", "cancelado"):
        assert (
            client.get(f"/pedidos?status={status}", headers=headers_vendedora).json()["total"]
            == contagem[status]
        )
    assert client.get("/pedidos", headers=headers_vendedora).json()["total"] == contagem["todos"]


def test_contagem_respeita_os_filtros(client, headers_vendedora, cenario, vendas, vendedoras):
    por_cliente = client.get(
        f"/pedidos/contagem?id_cliente={cenario['bia'][0]}", headers=headers_vendedora
    ).json()
    por_vendedora = client.get(
        f"/pedidos/contagem?id_vendedora={vendedoras['joana']['id']}", headers=headers_vendedora
    ).json()
    por_busca = client.get("/pedidos/contagem?busca=ana", headers=headers_vendedora).json()
    antigo = client.get(
        "/pedidos/contagem?data_inicio=2000-01-01&data_fim=2000-12-31", headers=headers_vendedora
    ).json()

    assert por_cliente["todos"] == 3  # em aberto, cancelado e entregue da Bia
    assert por_vendedora == {
        "todos": 2,
        "em_aberto": 0,
        "confirmado": 0,
        "entregue": 1,
        "cancelado": 1,
    }
    assert por_busca["todos"] == 2
    assert antigo["todos"] == 0


def test_contagem_com_filtro_invalido(client, headers_vendedora):
    assert (
        client.get(
            "/pedidos/contagem?data_inicio=2026-02-01&data_fim=2026-01-01",
            headers=headers_vendedora,
        ).status_code
        == 422
    )
    assert (
        client.get("/pedidos/contagem?id_cliente=0", headers=headers_vendedora).status_code == 422
    )


# --- /estoque/movimentacoes/resumo --------------------------------------------------------------------


def test_resumo_de_movimentacoes_exige_administradora(client, headers_vendedora):
    assert client.get("/estoque/movimentacoes/resumo").status_code == 401
    assert client.get("/estoque/movimentacoes/resumo", headers=headers_vendedora).status_code == 403


def _produto(client, h, **kw):
    corpo = {
        "nome": "Saco",
        "descricao": "d",
        "preco_unitario": "10",
        "estoque_inicial": 50,
        "estoque_minimo": 5,
    } | kw
    return client.post("/produtos", json=corpo, headers=h).json()["id_produto"]


def test_resumo_traz_entradas_e_saidas_do_produto(client, headers_admin):
    id_ = _produto(client, headers_admin)  # 50 de estoque inicial = 1 entrada
    client.post(
        "/estoque/entradas", json={"id_produto": id_, "quantidade": 20}, headers=headers_admin
    )
    client.post(
        "/estoque/saidas",
        json={"id_produto": id_, "quantidade": 7, "motivo": "Perda"},
        headers=headers_admin,
    )

    corpo = client.get(
        f"/estoque/movimentacoes/resumo?id_produto={id_}", headers=headers_admin
    ).json()

    assert (corpo["total_entradas"], corpo["total_saidas"], corpo["saldo_do_periodo"]) == (
        70,
        7,
        63,
    )
    assert len(corpo["serie"]) == 30
    assert corpo["serie"][-1] == {"inicio": hoje_local().isoformat(), "entradas": 70, "saidas": 7}
    assert corpo["agrupamento"] == "dia"


def test_resumo_separa_produtos_e_soma_todos_sem_filtro(client, headers_admin):
    a = _produto(client, headers_admin, nome="A", estoque_inicial=10)
    _produto(client, headers_admin, nome="B", estoque_inicial=30)

    so_a = client.get(f"/estoque/movimentacoes/resumo?id_produto={a}", headers=headers_admin).json()
    todos = client.get("/estoque/movimentacoes/resumo", headers=headers_admin).json()

    assert so_a["total_entradas"] == 10
    assert todos["total_entradas"] == 40


def test_resumo_respeita_periodo_e_agrupamento(client, db, headers_admin):
    id_ = _produto(client, headers_admin, estoque_inicial=10)
    antiga = db.query(Movimentacao).filter_by(id_produto=id_).one()
    antiga.data_movimentacao = agora_utc() - timedelta(days=40)
    db.flush()
    hoje = hoje_local()

    recente = client.get(
        f"/estoque/movimentacoes/resumo?id_produto={id_}", headers=headers_admin
    ).json()
    amplo = client.get(
        f"/estoque/movimentacoes/resumo?id_produto={id_}&data_inicio={hoje - timedelta(days=90)}&data_fim={hoje}&agrupar=semana",
        headers=headers_admin,
    ).json()

    assert recente["total_entradas"] == 0
    assert amplo["total_entradas"] == 10
    assert amplo["agrupamento"] == "semana"
    assert all(date.fromisoformat(p["inicio"]).weekday() == 0 for p in amplo["serie"])


def test_resumo_de_produto_inexistente_e_filtros_invalidos(client, headers_admin):
    assert (
        client.get(
            "/estoque/movimentacoes/resumo?id_produto=999999", headers=headers_admin
        ).status_code
        == 404
    )
    for query in ["id_produto=0", "agrupar=ano", "data_inicio=2026-02-01&data_fim=2026-01-01"]:
        assert (
            client.get(f"/estoque/movimentacoes/resumo?{query}", headers=headers_admin).status_code
            == 422
        )
