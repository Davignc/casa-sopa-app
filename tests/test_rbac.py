"""RN01: cada cargo só acessa o que lhe é permitido."""

from sqlalchemy import select

from app.core.security import criar_access_token
from app.models.usuario import Usuario


def _usuario(db, email):
    return db.scalar(select(Usuario).where(Usuario.email == email))


def test_admin_passa_na_rota_de_admin(client, headers_admin, dados_usuario):
    resposta = client.post("/usuarios", json=dados_usuario, headers=headers_admin)

    assert resposta.status_code == 201


def test_vendedora_recebe_403_na_rota_de_admin(client, headers_vendedora, dados_admin):
    resposta = client.post("/usuarios", json=dados_admin, headers=headers_vendedora)

    assert resposta.status_code == 403
    assert "permissão" in resposta.json()["detail"].lower()


def test_rebaixar_admin_vale_na_hora_mesmo_com_token_antigo(
    client, db, headers_admin, admin_cadastrada, dados_usuario
):
    """O cargo é lido do banco a cada request, não gravado no token."""
    _usuario(db, admin_cadastrada["email"]).cargo = "vendedora"
    db.flush()

    resposta = client.post("/usuarios", json=dados_usuario, headers=headers_admin)

    assert resposta.status_code == 403


def test_admin_inativada_perde_acesso_na_hora(
    client, db, headers_admin, admin_cadastrada, dados_usuario
):
    _usuario(db, admin_cadastrada["email"]).is_ativo = False
    db.flush()

    resposta = client.post("/usuarios", json=dados_usuario, headers=headers_admin)

    assert resposta.status_code == 403


def test_token_de_usuario_inexistente_retorna_401(client):
    token = criar_access_token(999999)

    resposta = client.get("/usuarios/me", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 401


def test_token_com_sub_nao_numerico_retorna_401(client):
    token = criar_access_token("abc")

    resposta = client.get("/usuarios/me", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 401
