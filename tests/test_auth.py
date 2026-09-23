from sqlalchemy import select

from app.core.security import decodificar_access_token
from app.models.usuario import Usuario


def test_login_json_devolve_token(client, usuario_cadastrado):
    resposta = client.post(
        "/auth/login/json",
        json={"email": usuario_cadastrado["email"], "senha": usuario_cadastrado["senha"]},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    assert decodificar_access_token(corpo["access_token"]) is not None


def test_login_form_oauth2_devolve_token(client, usuario_cadastrado):
    resposta = client.post(
        "/auth/login",
        data={"username": usuario_cadastrado["email"], "password": usuario_cadastrado["senha"]},
    )

    assert resposta.status_code == 200
    assert resposta.json()["token_type"] == "bearer"


def test_token_aponta_para_o_usuario_certo(client, db, usuario_cadastrado):
    resposta = client.post(
        "/auth/login/json",
        json={"email": usuario_cadastrado["email"], "senha": usuario_cadastrado["senha"]},
    )

    payload = decodificar_access_token(resposta.json()["access_token"])
    usuario = db.scalar(select(Usuario).where(Usuario.email == usuario_cadastrado["email"]))
    assert payload["sub"] == str(usuario.id_usuario)


def test_login_com_senha_errada_retorna_401(client, usuario_cadastrado):
    resposta = client.post(
        "/auth/login/json",
        json={"email": usuario_cadastrado["email"], "senha": "senhaErrada123"},
    )

    assert resposta.status_code == 401


def test_login_com_email_inexistente_retorna_401(client, usuario_cadastrado):
    resposta = client.post(
        "/auth/login/json",
        json={"email": "ninguem@casadasopa.org", "senha": usuario_cadastrado["senha"]},
    )

    assert resposta.status_code == 401


def test_erro_de_login_nao_diz_qual_campo_falhou(client, usuario_cadastrado):
    """Mesma mensagem para senha errada e e-mail inexistente (evita enumeração)."""
    senha_errada = client.post(
        "/auth/login/json",
        json={"email": usuario_cadastrado["email"], "senha": "senhaErrada123"},
    )
    email_inexistente = client.post(
        "/auth/login/json",
        json={"email": "ninguem@casadasopa.org", "senha": usuario_cadastrado["senha"]},
    )

    assert senha_errada.json()["detail"] == email_inexistente.json()["detail"]


def test_resposta_do_login_nao_expoe_a_senha(client, usuario_cadastrado):
    resposta = client.post(
        "/auth/login/json",
        json={"email": usuario_cadastrado["email"], "senha": usuario_cadastrado["senha"]},
    )

    assert usuario_cadastrado["senha"] not in resposta.text
    assert "$2b$" not in resposta.text


def test_usuario_inativo_nao_consegue_logar(client, db, usuario_cadastrado):
    usuario = db.scalar(select(Usuario).where(Usuario.email == usuario_cadastrado["email"]))
    usuario.is_ativo = False
    db.flush()

    resposta = client.post(
        "/auth/login/json",
        json={"email": usuario_cadastrado["email"], "senha": usuario_cadastrado["senha"]},
    )

    assert resposta.status_code == 401


def test_health(client):
    resposta = client.get("/health")

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"
