import pytest
from sqlalchemy import select

from app.models.usuario import Usuario


def _cadastrar(client, headers, dados):
    return client.post("/usuarios", json=dados, headers=headers)


# --- criação: só a administradora (RN03) -------------------------------------


def test_admin_cria_usuario(client, headers_admin, dados_usuario):
    resposta = _cadastrar(client, headers_admin, dados_usuario)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["email"] == dados_usuario["email"]
    assert corpo["cargo"] == "vendedora"
    assert corpo["comissao"] == "5.00"
    assert corpo["is_ativo"] is True
    assert corpo["id_usuario"] > 0


def test_vendedora_nao_pode_cadastrar_usuario(client, headers_vendedora, dados_admin):
    resposta = _cadastrar(client, headers_vendedora, dados_admin)

    assert resposta.status_code == 403


def test_cadastro_sem_token_retorna_401(client, dados_usuario):
    assert client.post("/usuarios", json=dados_usuario).status_code == 401


def test_cadastro_nao_cria_nada_quando_negado(client, db, headers_vendedora, dados_admin):
    _cadastrar(client, headers_vendedora, dados_admin)

    assert db.scalar(select(Usuario).where(Usuario.email == dados_admin["email"])) is None


# --- segredos ----------------------------------------------------------------


def test_resposta_do_cadastro_nao_expoe_a_senha(client, headers_admin, dados_usuario):
    resposta = _cadastrar(client, headers_admin, dados_usuario)

    assert "senha" not in resposta.json()
    assert dados_usuario["senha"] not in resposta.text
    assert "$2b$" not in resposta.text


def test_senha_e_gravada_como_hash_no_banco(client, db, headers_admin, dados_usuario):
    _cadastrar(client, headers_admin, dados_usuario)

    usuario = db.scalar(select(Usuario).where(Usuario.email == dados_usuario["email"]))
    assert usuario is not None
    assert usuario.senha != dados_usuario["senha"]
    assert usuario.senha.startswith("$2b$")


# --- unicidade (RN02 + telefone) ---------------------------------------------


def test_email_duplicado_retorna_409(client, headers_admin, dados_usuario):
    _cadastrar(client, headers_admin, dados_usuario)
    outro = {**dados_usuario, "telefone": "16977776666"}
    resposta = _cadastrar(client, headers_admin, outro)

    assert resposta.status_code == 409
    assert "e-mail" in resposta.json()["detail"].lower()


def test_email_duplicado_ignora_maiusculas(client, headers_admin, dados_usuario):
    _cadastrar(client, headers_admin, dados_usuario)
    outro = {**dados_usuario, "email": "MARIA@CasaDaSopa.org", "telefone": "16977776666"}

    assert _cadastrar(client, headers_admin, outro).status_code == 409


def test_telefone_duplicado_retorna_409(client, headers_admin, dados_usuario):
    _cadastrar(client, headers_admin, dados_usuario)
    outro = {**dados_usuario, "email": "outra@casadasopa.org"}
    resposta = _cadastrar(client, headers_admin, outro)

    assert resposta.status_code == 409
    assert "telefone" in resposta.json()["detail"].lower()


def test_telefone_formatado_conta_como_duplicado(client, headers_admin, dados_usuario):
    _cadastrar(client, headers_admin, dados_usuario)
    outro = {**dados_usuario, "email": "outra@casadasopa.org", "telefone": "(16) 99999-8888"}

    assert _cadastrar(client, headers_admin, outro).status_code == 409


def test_telefone_e_gravado_so_com_digitos(client, headers_admin, dados_usuario):
    dados = {**dados_usuario, "telefone": "(16) 99999-8888"}
    resposta = _cadastrar(client, headers_admin, dados)

    assert resposta.status_code == 201
    assert resposta.json()["telefone"] == "16999998888"


# --- validação de entrada ----------------------------------------------------


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("email", "nao-e-email"),
        ("senha", "1234"),
        ("senha", "a" * 73),
        ("telefone", "123"),
        ("telefone", "abc"),
        ("cargo", "gerente"),
        ("comissao", "101"),
        ("comissao", "-1"),
        ("comissao", "5.123"),
        ("nome", ""),
    ],
)
def test_valores_invalidos_retornam_422(client, headers_admin, dados_usuario, campo, valor):
    resposta = _cadastrar(client, headers_admin, {**dados_usuario, campo: valor})

    assert resposta.status_code == 422


def test_campo_obrigatorio_ausente_retorna_422(client, headers_admin, dados_usuario):
    sem_nome = {k: v for k, v in dados_usuario.items() if k != "nome"}

    assert _cadastrar(client, headers_admin, sem_nome).status_code == 422


def test_comissao_para_administradora_retorna_422(client, headers_admin, dados_admin):
    resposta = _cadastrar(client, headers_admin, {**dados_admin, "comissao": "5.00"})

    assert resposta.status_code == 422


def test_vendedora_pode_ficar_sem_comissao(client, headers_admin, dados_usuario):
    dados = {k: v for k, v in dados_usuario.items() if k != "comissao"}
    resposta = _cadastrar(client, headers_admin, dados)

    assert resposta.status_code == 201
    assert resposta.json()["comissao"] is None


def test_campos_extras_sao_recusados(client, headers_admin, dados_usuario):
    """Impede 'mass assignment': o cliente não define campos internos."""
    resposta = _cadastrar(client, headers_admin, {**dados_usuario, "is_ativo": False})

    assert resposta.status_code == 422


# --- /me ---------------------------------------------------------------------


def test_me_com_token_valido(client, headers_vendedora, dados_usuario):
    resposta = client.get("/usuarios/me", headers=headers_vendedora)

    assert resposta.status_code == 200
    assert resposta.json()["email"] == dados_usuario["email"]
    assert "senha" not in resposta.json()


def test_me_sem_token_retorna_401(client):
    assert client.get("/usuarios/me").status_code == 401


def test_me_com_token_invalido_retorna_401(client):
    resposta = client.get("/usuarios/me", headers={"Authorization": "Bearer invalido"})

    assert resposta.status_code == 401


def test_me_de_usuario_inativo_retorna_403(client, db, headers_vendedora, dados_usuario):
    usuario = db.scalar(select(Usuario).where(Usuario.email == dados_usuario["email"]))
    usuario.is_ativo = False
    db.flush()

    assert client.get("/usuarios/me", headers=headers_vendedora).status_code == 403
