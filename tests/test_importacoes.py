import io

import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import func, select

from app.models import Cliente, Movimentacao, Produto, Venda, VendaImportada
from app.services.importacao import COLUNAS


def arquivo(tipo, linhas):
    wb = Workbook()
    ws = wb.active
    ws.title = tipo
    ws.append(COLUNAS[tipo])
    for dados in linhas:
        ws.append([dados.get(c, "") for c in COLUNAS[tipo]])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def enviar(client, headers, tipo, conteudo, token=None, nome="dados.xlsx"):
    return client.post(
        "/importacoes/confirmar" if token else "/importacoes/analisar",
        headers=headers,
        data={"tipo": tipo, **({"token": token} if token else {})},
        files={"arquivo": (nome, conteudo)},
    )


CLIENTE = {
    "nome": "Cliente antigo",
    "telefone": "16977776666",
    "cep": "14430000",
    "cidade": "Restinga",
    "bairro": "Centro",
    "tipo_logradouro": "Rua",
    "nome_logradouro": "das Flores",
    "numero": "10",
}
PRODUTO = {
    "nome": "Saco 100 L",
    "descricao": "Pacote",
    "preco_unitario": "20,50",
    "estoque_inicial": "30",
    "estoque_minimo": "5",
}
VENDA = {
    "pedido_origem": "PLANILHA-2024-001",
    "data_venda": "10/01/2024",
    "cliente_telefone": "16977776666",
    "produto": "Saco 100 L",
    "quantidade": "2",
    "preco_unitario": "12,50",
    "forma_pagamento": "pix",
    "status": "entregue",
}


def importar(client, headers, tipo, linhas):
    conteudo = arquivo(tipo, linhas)
    previa = enviar(client, headers, tipo, conteudo)
    assert previa.status_code == 200, previa.text
    assert not previa.json()["erros"], previa.json()
    resposta = enviar(client, headers, tipo, conteudo, previa.json()["token"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["concluida"]
    return resposta.json()


@pytest.mark.parametrize("tipo", ["clientes", "produtos", "vendas"])
def test_modelos_e_permissoes(client, headers_admin, headers_vendedora, tipo):
    assert client.get("/importacoes/modelo", params={"tipo": tipo}).status_code == 401
    assert (
        client.get(
            "/importacoes/modelo", params={"tipo": tipo}, headers=headers_vendedora
        ).status_code
        == 403
    )
    r = client.get("/importacoes/modelo", params={"tipo": tipo}, headers=headers_admin)
    assert r.status_code == 200
    wb = load_workbook(io.BytesIO(r.content))
    assert [c.value for c in wb[tipo][1]] == COLUNAS[tipo]
    for rota in ("analisar", "confirmar"):
        assert client.post(f"/importacoes/{rota}", headers=headers_vendedora).status_code == 403


def test_previa_nao_grava_e_confirmacao_nao_duplica(client, db, headers_admin):
    dados = arquivo("clientes", [CLIENTE])
    previa = enviar(client, headers_admin, "clientes", dados)
    assert previa.status_code == 200, previa.text
    assert previa.json()["novos"] == 1
    assert not db.scalar(select(Cliente))
    salvo = enviar(client, headers_admin, "clientes", dados, previa.json()["token"])
    assert salvo.json()["concluida"]
    assert db.scalar(select(func.count()).select_from(Cliente)) == 1
    repetido = enviar(client, headers_admin, "clientes", dados, previa.json()["token"])
    assert repetido.json()["ignorados"] == 1
    assert db.scalar(select(func.count()).select_from(Cliente)) == 1


def test_erro_na_linha_desfaz_todo_arquivo(client, db, headers_admin):
    dados = arquivo("clientes", [CLIENTE, {"nome": "Inválido", "telefone": "123"}])
    resposta = enviar(client, headers_admin, "clientes", dados).json()
    assert resposta["erros"][0]["linha"] == 3
    assert resposta["token"] is None
    assert not db.scalar(select(Cliente))


def test_confirmacao_exige_mesmo_arquivo(client, db, headers_admin):
    dados = arquivo("clientes", [CLIENTE])
    previa = enviar(client, headers_admin, "clientes", dados).json()
    outro = arquivo("clientes", [{**CLIENTE, "nome": "Outro"}])
    assert enviar(client, headers_admin, "clientes", outro, previa["token"]).status_code == 422
    assert not db.scalar(select(Cliente))


def test_historico_preserva_preco_data_e_estoque(client, db, headers_admin):
    importar(client, headers_admin, "clientes", [CLIENTE])
    importar(client, headers_admin, "produtos", [PRODUTO])
    antes = db.scalar(select(func.count()).select_from(Movimentacao))
    r = importar(client, headers_admin, "vendas", [VENDA])
    assert r["novos"] == 1
    venda = db.scalar(select(Venda))
    assert float(venda.valor_total) == 25
    assert venda.data_venda.year == 2024
    assert venda.data_pagamento is None
    assert venda.status == "entregue"
    assert db.scalar(select(Produto)).estoque_atual == 30
    assert db.scalar(select(func.count()).select_from(Movimentacao)) == antes
    r = importar(client, headers_admin, "vendas", [VENDA])
    assert r["ignorados"] == 1
    assert db.scalar(select(func.count()).select_from(Venda)) == 1
    assert db.scalar(select(func.count()).select_from(VendaImportada)) == 1


def test_pedido_com_varios_itens(client, db, headers_admin):
    importar(client, headers_admin, "clientes", [CLIENTE])
    importar(client, headers_admin, "produtos", [PRODUTO, {**PRODUTO, "nome": "Saco 50 L"}])
    r = importar(client, headers_admin, "vendas", [VENDA, {**VENDA, "produto": "Saco 50 L"}])
    assert r["novos"] == 1
    assert len(db.scalar(select(Venda)).itens) == 2
    assert float(db.scalar(select(Venda)).valor_total) == 50


@pytest.mark.parametrize(
    "alteracao",
    [
        {"produto": "Não existe"},
        {"data_venda": "01/01/2099"},
        {"status": "confirmado"},
        {"preco_unitario": "-2"},
        {"quantidade": "0"},
        {"responsavel_email": "desconhecido@example.org"},
    ],
)
def test_venda_invalida_nao_grava(client, db, headers_admin, alteracao):
    importar(client, headers_admin, "clientes", [CLIENTE])
    importar(client, headers_admin, "produtos", [PRODUTO])
    r = enviar(client, headers_admin, "vendas", arquivo("vendas", [{**VENDA, **alteracao}]))
    assert r.status_code == 200
    assert r.json()["erros"]
    assert not db.scalar(select(Venda))


def test_csv_portugues_e_duplicado_mesmo_arquivo(client, db, headers_admin):
    conteudo = "nome;telefone\nJosé;16977776666\nJosé;16977776666\n".encode("cp1252")
    r = enviar(client, headers_admin, "clientes", conteudo, nome="dados.csv")
    assert r.status_code == 200, r.text
    assert r.json()["novos"] == 1
    assert r.json()["ignorados"] == 1
    assert not db.scalar(select(Cliente))


@pytest.mark.parametrize(
    "conteudo,nome",
    [
        (b"", "dados.xlsx"),
        (b"erro", "dados.xlsx"),
        (b"nome;nome\na;b", "dados.csv"),
        (b"nome;errado\na;b", "dados.csv"),
        (b"abc", "dados.xls"),
        (b"x" * (5 * 1024 * 1024 + 1), "dados.csv"),
    ],
    ids=["vazio", "xlsx_corrompido", "colunas_repetidas", "colunas_erradas", "extensao", "grande"],
)
def test_arquivos_invalidos(client, headers_admin, conteudo, nome):
    assert enviar(client, headers_admin, "clientes", conteudo, nome=nome).status_code == 422


def test_excel_com_formula_recusado(client, headers_admin):
    conteudo = arquivo("clientes", [{**CLIENTE, "nome": '=HYPERLINK("https://example.org")'}])
    r = enviar(client, headers_admin, "clientes", conteudo)
    assert r.status_code == 422
    assert "fórmulas" in r.json()["detail"]
