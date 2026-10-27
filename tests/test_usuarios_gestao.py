"""RF04, RF05, RF06 e RN04-06: gestão de usuários pela administradora."""

import itertools

import pytest
from sqlalchemy import select

from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate
from app.services import usuario as usuario_service

_n = itertools.count(1)


@pytest.fixture
def novo_usuario(db):
    """Fábrica: cria usuários direto no banco, com e-mail/telefone únicos."""

    def _criar(**kw) -> Usuario:
        n = next(_n)
        dados = {
            "nome": f"Pessoa {n:02d}",
            "email": f"pessoa{n}@casadasopa.org",
            "telefone": f"1697{n:07d}",
            "cargo": "vendedora",
            "comissao": "5.00",
            "senha": "senhaForte123",
        }
        dados.update(kw)
        return usuario_service.criar_usuario(db, UsuarioCreate(**dados))

    return _criar


def _id_admin(db, admin_cadastrada):
    return db.scalar(select(Usuario).where(Usuario.email == admin_cadastrada["email"])).id_usuario


def _login(client, email, senha):
    return client.post("/auth/login/json", json={"email": email, "senha": senha})


# --- permissões: nenhuma rota nova é aberta à vendedora ----------------------

ROTAS_DE_ADMIN = [
    ("GET", "/usuarios"),
    ("GET", "/usuarios/1"),
    ("PATCH", "/usuarios/1"),
    ("DELETE", "/usuarios/1"),
    ("POST", "/usuarios/1/reativar"),
]


@pytest.mark.parametrize(("metodo", "rota"), ROTAS_DE_ADMIN)
def test_vendedora_recebe_403(client, headers_vendedora, metodo, rota):
    resposta = client.request(metodo, rota, headers=headers_vendedora, json={"nome": "x"})

    assert resposta.status_code == 403


@pytest.mark.parametrize(("metodo", "rota"), ROTAS_DE_ADMIN)
def test_sem_token_recebe_401(client, metodo, rota):
    assert client.request(metodo, rota, json={"nome": "x"}).status_code == 401


# --- listagem (RF06) ---------------------------------------------------------


def test_admin_lista_todos_incluindo_inativos(client, headers_admin, novo_usuario):
    novo_usuario()
    inativo = novo_usuario()
    client.delete(f"/usuarios/{inativo.id_usuario}", headers=headers_admin)

    corpo = client.get("/usuarios", headers=headers_admin).json()

    assert corpo["total"] == 3  # admin + 2
    assert {u["is_ativo"] for u in corpo["itens"]} == {True, False}


def test_listagem_traz_nome_email_e_cargo_sem_senha(client, headers_admin, novo_usuario):
    novo_usuario(nome="Zélia", email="zelia@casadasopa.org")

    corpo = client.get("/usuarios", headers=headers_admin).json()

    zelia = next(u for u in corpo["itens"] if u["email"] == "zelia@casadasopa.org")
    assert zelia["nome"] == "Zélia"
    assert zelia["cargo"] == "vendedora"
    assert all("senha" not in u for u in corpo["itens"])


def test_listagem_ordenada_por_nome(client, headers_admin, novo_usuario):
    novo_usuario(nome="Beatriz")
    novo_usuario(nome="Aline")

    nomes = [u["nome"] for u in client.get("/usuarios", headers=headers_admin).json()["itens"]]

    assert nomes == sorted(nomes)


def test_filtro_por_cargo(client, headers_admin, novo_usuario):
    novo_usuario()

    itens = client.get("/usuarios?cargo=administradora", headers=headers_admin).json()["itens"]

    assert itens
    assert {u["cargo"] for u in itens} == {"administradora"}


def test_filtro_por_situacao(client, headers_admin, novo_usuario):
    inativo = novo_usuario()
    client.delete(f"/usuarios/{inativo.id_usuario}", headers=headers_admin)

    inativos = client.get("/usuarios?is_ativo=false", headers=headers_admin).json()
    ativos = client.get("/usuarios?is_ativo=true", headers=headers_admin).json()

    assert [u["id_usuario"] for u in inativos["itens"]] == [inativo.id_usuario]
    assert inativo.id_usuario not in [u["id_usuario"] for u in ativos["itens"]]


def test_busca_por_nome_ou_email_ignora_maiusculas(client, headers_admin, novo_usuario):
    novo_usuario(nome="Josefina Alves", email="jo@casadasopa.org")
    novo_usuario(nome="Outra", email="josefa@casadasopa.org")
    novo_usuario(nome="Ninguém Parecida", email="x@casadasopa.org")

    itens = client.get("/usuarios?busca=JOSEF", headers=headers_admin).json()["itens"]

    assert {u["email"] for u in itens} == {"jo@casadasopa.org", "josefa@casadasopa.org"}


def test_busca_trata_percentual_e_underscore_como_texto(client, headers_admin, novo_usuario):
    novo_usuario(nome="Maria")

    assert client.get("/usuarios?busca=%25", headers=headers_admin).json()["total"] == 0
    assert client.get("/usuarios?busca=_", headers=headers_admin).json()["total"] == 0


def test_paginacao(client, headers_admin, novo_usuario):
    for _ in range(5):
        novo_usuario()

    pag1 = client.get("/usuarios?limit=4&offset=0", headers=headers_admin).json()
    pag2 = client.get("/usuarios?limit=4&offset=4", headers=headers_admin).json()

    assert pag1["total"] == pag2["total"] == 6
    assert len(pag1["itens"]) == 4
    assert len(pag2["itens"]) == 2
    assert not {u["id_usuario"] for u in pag1["itens"]} & {u["id_usuario"] for u in pag2["itens"]}


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=101", "offset=-1", "cargo=gerente", "is_ativo=talvez"]
)
def test_parametros_invalidos_retornam_422(client, headers_admin, query):
    assert client.get(f"/usuarios?{query}", headers=headers_admin).status_code == 422


# --- detalhe -----------------------------------------------------------------


def test_admin_ve_detalhe(client, headers_admin, novo_usuario):
    u = novo_usuario()

    resposta = client.get(f"/usuarios/{u.id_usuario}", headers=headers_admin)

    assert resposta.status_code == 200
    assert resposta.json()["email"] == u.email


def test_detalhe_de_inexistente_retorna_404(client, headers_admin):
    assert client.get("/usuarios/999999", headers=headers_admin).status_code == 404


@pytest.mark.parametrize("id_", ["0", "-1", "abc"])
def test_id_invalido_retorna_422(client, headers_admin, id_):
    assert client.get(f"/usuarios/{id_}", headers=headers_admin).status_code == 422


def test_me_nao_e_confundido_com_id(client, headers_admin, dados_admin):
    assert client.get("/usuarios/me", headers=headers_admin).json()["email"] == dados_admin["email"]


# --- edição (RF04) -----------------------------------------------------------


def _patch(client, headers, id_, **campos):
    return client.patch(f"/usuarios/{id_}", json=campos, headers=headers)


def test_altera_so_os_campos_enviados(client, headers_admin, novo_usuario):
    u = novo_usuario(nome="Antigo", comissao="5.00")

    resposta = _patch(client, headers_admin, u.id_usuario, nome="Novo")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["nome"] == "Novo"
    assert corpo["email"] == u.email
    assert corpo["comissao"] == "5.00"


def test_altera_varios_campos_e_reflete_na_listagem(client, headers_admin, novo_usuario):
    u = novo_usuario()

    _patch(
        client, headers_admin, u.id_usuario,
        nome="Maria Souza", email="NOVA@CasaDaSopa.org", telefone="(16) 91234-5678", comissao="7.5",
    )  # fmt: skip

    item = client.get(f"/usuarios/{u.id_usuario}", headers=headers_admin).json()
    assert item["nome"] == "Maria Souza"
    assert item["email"] == "nova@casadasopa.org"
    assert item["telefone"] == "16912345678"
    assert item["comissao"] == "7.50"


def test_email_de_outro_usuario_retorna_409(client, headers_admin, novo_usuario):
    a, b = novo_usuario(), novo_usuario()

    resposta = _patch(client, headers_admin, b.id_usuario, email=a.email.upper())

    assert resposta.status_code == 409
    assert "e-mail" in resposta.json()["detail"].lower()


def test_telefone_de_outro_usuario_retorna_409(client, headers_admin, novo_usuario):
    a, b = novo_usuario(), novo_usuario()

    resposta = _patch(client, headers_admin, b.id_usuario, telefone=a.telefone)

    assert resposta.status_code == 409
    assert "telefone" in resposta.json()["detail"].lower()


def test_pode_reenviar_o_proprio_email_e_telefone(client, headers_admin, novo_usuario):
    u = novo_usuario()

    resposta = _patch(client, headers_admin, u.id_usuario, email=u.email, telefone=u.telefone)

    assert resposta.status_code == 200


def test_virar_administradora_zera_a_comissao(client, headers_admin, novo_usuario):
    u = novo_usuario(comissao="5.00")

    corpo = _patch(client, headers_admin, u.id_usuario, cargo="administradora").json()

    assert corpo["cargo"] == "administradora"
    assert corpo["comissao"] is None


def test_virar_vendedora_aceita_comissao(client, headers_admin, novo_usuario):
    u = novo_usuario(cargo="administradora", comissao=None)

    corpo = _patch(client, headers_admin, u.id_usuario, cargo="vendedora", comissao="3").json()

    assert corpo["cargo"] == "vendedora"
    assert corpo["comissao"] == "3.00"


def test_comissao_para_administradora_retorna_422(client, headers_admin, novo_usuario):
    u = novo_usuario(cargo="administradora", comissao=None)

    assert _patch(client, headers_admin, u.id_usuario, comissao="5").status_code == 422


def test_cargo_administradora_com_comissao_no_mesmo_pedido_retorna_422(
    client, headers_admin, novo_usuario
):
    u = novo_usuario()

    resposta = _patch(client, headers_admin, u.id_usuario, cargo="administradora", comissao="5")

    assert resposta.status_code == 422


def test_comissao_null_limpa_a_comissao(client, headers_admin, novo_usuario):
    u = novo_usuario(comissao="5.00")

    corpo = _patch(client, headers_admin, u.id_usuario, comissao=None).json()

    assert corpo["comissao"] is None


def test_administradora_nao_altera_o_proprio_cargo(client, db, headers_admin, admin_cadastrada):
    resposta = _patch(client, headers_admin, _id_admin(db, admin_cadastrada), cargo="vendedora")

    assert resposta.status_code == 409
    assert "próprio cargo" in resposta.json()["detail"]


def test_administradora_edita_os_proprios_outros_dados(client, db, headers_admin, admin_cadastrada):
    resposta = _patch(
        client,
        headers_admin,
        _id_admin(db, admin_cadastrada),
        nome="Ana Maria",
        cargo="administradora",
    )

    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Ana Maria"


def test_admin_rebaixa_outra_administradora(client, headers_admin, novo_usuario):
    outra = novo_usuario(cargo="administradora", comissao=None)

    assert _patch(client, headers_admin, outra.id_usuario, cargo="vendedora").status_code == 200


def test_edicao_de_inexistente_retorna_404(client, headers_admin):
    assert _patch(client, headers_admin, 999999, nome="X").status_code == 404


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"nome": None},
        {"email": None},
        {"senha": None},
        {"cargo": None},
        {"nome": ""},
        {"email": "nao-e-email"},
        {"telefone": "123"},
        {"cargo": "gerente"},
        {"comissao": "101"},
        {"senha": "curta"},
        {"senha": "x" * 73},
        {"is_ativo": False},
        {"id_usuario": 5},
    ],
)
def test_corpos_invalidos_retornam_422(client, headers_admin, novo_usuario, corpo):
    u = novo_usuario()

    assert (
        client.patch(f"/usuarios/{u.id_usuario}", json=corpo, headers=headers_admin).status_code
        == 422
    )


def test_edicao_invalida_nao_altera_nada(client, db, headers_admin, novo_usuario):
    u = novo_usuario(nome="Original")

    _patch(client, headers_admin, u.id_usuario, nome="Mudou", telefone="123")
    db.refresh(u)

    assert u.nome == "Original"


# --- troca de senha ----------------------------------------------------------


def test_nova_senha_vale_e_a_antiga_nao(client, headers_admin, novo_usuario):
    u = novo_usuario(senha="senhaAntiga123")

    assert _patch(client, headers_admin, u.id_usuario, senha="senhaNova12345").status_code == 200

    assert _login(client, u.email, "senhaAntiga123").status_code == 401
    assert _login(client, u.email, "senhaNova12345").status_code == 200


def test_resposta_da_edicao_nao_expoe_senha(client, headers_admin, novo_usuario):
    u = novo_usuario()

    resposta = _patch(client, headers_admin, u.id_usuario, senha="senhaNova12345")

    assert "senha" not in resposta.json()
    assert "senhaNova12345" not in resposta.text


def test_senha_nova_e_gravada_como_hash(client, db, headers_admin, novo_usuario):
    u = novo_usuario()

    _patch(client, headers_admin, u.id_usuario, senha="senhaNova12345")
    db.refresh(u)

    assert u.senha.startswith("$2b$")
    assert "senhaNova12345" not in u.senha


def test_trocar_a_senha_derruba_as_sessoes_abertas_do_usuario(client, headers_admin, novo_usuario):
    u = novo_usuario(senha="senhaAntiga123")
    token_antigo = _login(client, u.email, "senhaAntiga123").json()["access_token"]
    cabecalho = {"Authorization": f"Bearer {token_antigo}"}
    assert client.get("/usuarios/me", headers=cabecalho).status_code == 200

    _patch(client, headers_admin, u.id_usuario, senha="senhaNova12345")

    resposta = client.get("/usuarios/me", headers=cabecalho)
    assert resposta.status_code == 401
    assert "expirada" in resposta.json()["detail"].lower()


def test_trocar_dados_sem_trocar_a_senha_mantem_a_sessao(client, headers_admin, novo_usuario):
    u = novo_usuario(senha="senhaAntiga123")
    token = _login(client, u.email, "senhaAntiga123").json()["access_token"]

    _patch(client, headers_admin, u.id_usuario, nome="Outro Nome")

    resposta = client.get("/usuarios/me", headers={"Authorization": f"Bearer {token}"})
    assert resposta.status_code == 200


# --- inativação (RF05) -------------------------------------------------------


def test_inativar_retorna_204_e_preserva_o_registro(client, db, headers_admin, novo_usuario):
    u = novo_usuario()

    resposta = client.delete(f"/usuarios/{u.id_usuario}", headers=headers_admin)

    assert resposta.status_code == 204
    assert resposta.content == b""
    db.refresh(u)
    assert u.is_ativo is False  # exclusão lógica: a linha continua no banco


def test_usuario_inativado_nao_consegue_logar(client, headers_admin, novo_usuario):
    u = novo_usuario(senha="senhaForte123")
    client.delete(f"/usuarios/{u.id_usuario}", headers=headers_admin)

    assert _login(client, u.email, "senhaForte123").status_code == 401


def test_sessao_aberta_de_usuario_inativado_para_de_funcionar(client, headers_admin, novo_usuario):
    u = novo_usuario(senha="senhaForte123")
    token = _login(client, u.email, "senhaForte123").json()["access_token"]

    client.delete(f"/usuarios/{u.id_usuario}", headers=headers_admin)

    resposta = client.get("/usuarios/me", headers={"Authorization": f"Bearer {token}"})
    assert resposta.status_code == 403


def test_administradora_nao_inativa_a_propria_conta(client, db, headers_admin, admin_cadastrada):
    resposta = client.delete(f"/usuarios/{_id_admin(db, admin_cadastrada)}", headers=headers_admin)

    assert resposta.status_code == 409
    assert client.get("/usuarios/me", headers=headers_admin).status_code == 200


def test_inativar_duas_vezes_e_idempotente(client, headers_admin, novo_usuario):
    u = novo_usuario()
    client.delete(f"/usuarios/{u.id_usuario}", headers=headers_admin)

    assert client.delete(f"/usuarios/{u.id_usuario}", headers=headers_admin).status_code == 204


def test_inativar_inexistente_retorna_404(client, headers_admin):
    assert client.delete("/usuarios/999999", headers=headers_admin).status_code == 404


def test_admin_inativa_outra_administradora(client, headers_admin, novo_usuario):
    outra = novo_usuario(cargo="administradora", comissao=None)

    assert client.delete(f"/usuarios/{outra.id_usuario}", headers=headers_admin).status_code == 204


def test_email_de_inativo_continua_reservado(client, headers_admin, novo_usuario, dados_usuario):
    """O histórico é preservado: o e-mail de quem foi inativado não pode ser reutilizado."""
    u = novo_usuario(email=dados_usuario["email"], telefone="16911112222")
    client.delete(f"/usuarios/{u.id_usuario}", headers=headers_admin)

    resposta = client.post(
        "/usuarios", json=dados_usuario | {"telefone": "16933334444"}, headers=headers_admin
    )

    assert resposta.status_code == 409


# --- reativação --------------------------------------------------------------


def test_reativar_devolve_o_acesso(client, headers_admin, novo_usuario):
    u = novo_usuario(senha="senhaForte123")
    client.delete(f"/usuarios/{u.id_usuario}", headers=headers_admin)

    resposta = client.post(f"/usuarios/{u.id_usuario}/reativar", headers=headers_admin)

    assert resposta.status_code == 200
    assert resposta.json()["is_ativo"] is True
    assert _login(client, u.email, "senhaForte123").status_code == 200


def test_reativar_inexistente_retorna_404(client, headers_admin):
    assert client.post("/usuarios/999999/reativar", headers=headers_admin).status_code == 404
