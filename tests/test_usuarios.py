from sqlalchemy import select

from app.models.usuario import Usuario


def test_cria_usuario(client, dados_usuario):
    resposta = client.post("/usuarios", json=dados_usuario)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["email"] == dados_usuario["email"]
    assert corpo["nome"] == dados_usuario["nome"]
    assert corpo["is_ativo"] is True
    assert corpo["id_usuario"] > 0


def test_resposta_do_cadastro_nao_expoe_a_senha(client, dados_usuario):
    resposta = client.post("/usuarios", json=dados_usuario)

    corpo = resposta.json()
    assert "senha" not in corpo
    # Nem em texto puro, nem como hash, em nenhum canto do corpo.
    assert dados_usuario["senha"] not in resposta.text
    assert "$2b$" not in resposta.text


def test_senha_e_gravada_como_hash_no_banco(client, db, dados_usuario):
    client.post("/usuarios", json=dados_usuario)

    usuario = db.scalar(select(Usuario).where(Usuario.email == dados_usuario["email"]))
    assert usuario is not None
    assert usuario.senha != dados_usuario["senha"]
    assert usuario.senha.startswith("$2b$")


def test_email_duplicado_retorna_409(client, dados_usuario):
    client.post("/usuarios", json=dados_usuario)
    resposta = client.post("/usuarios", json=dados_usuario)

    assert resposta.status_code == 409
    assert "e-mail" in resposta.json()["detail"].lower()


def test_email_invalido_retorna_422(client, dados_usuario):
    resposta = client.post("/usuarios", json={**dados_usuario, "email": "nao-e-email"})

    assert resposta.status_code == 422


def test_senha_curta_retorna_422(client, dados_usuario):
    resposta = client.post("/usuarios", json={**dados_usuario, "senha": "1234"})

    assert resposta.status_code == 422


def test_senha_acima_de_72_bytes_retorna_422(client, dados_usuario):
    resposta = client.post("/usuarios", json={**dados_usuario, "senha": "a" * 73})

    assert resposta.status_code == 422


def test_campo_obrigatorio_ausente_retorna_422(client, dados_usuario):
    sem_nome = {k: v for k, v in dados_usuario.items() if k != "nome"}
    resposta = client.post("/usuarios", json=sem_nome)

    assert resposta.status_code == 422


def test_me_com_token_valido(client, token, dados_usuario):
    resposta = client.get("/usuarios/me", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 200
    assert resposta.json()["email"] == dados_usuario["email"]
    assert "senha" not in resposta.json()


def test_me_sem_token_retorna_401(client):
    assert client.get("/usuarios/me").status_code == 401


def test_me_com_token_invalido_retorna_401(client):
    resposta = client.get("/usuarios/me", headers={"Authorization": "Bearer invalido"})

    assert resposta.status_code == 401


def test_me_de_usuario_inativo_retorna_403(client, db, token, dados_usuario):
    from app.models.usuario import Usuario as U

    usuario = db.scalar(select(U).where(U.email == dados_usuario["email"]))
    usuario.is_ativo = False
    db.flush()

    resposta = client.get("/usuarios/me", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 403
