"""RF02: logout encerra a sessão e o token deixa de valer."""


def _login(client, dados):
    resposta = client.post(
        "/auth/login/json", json={"email": dados["email"], "senha": dados["senha"]}
    )
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


def test_logout_retorna_204(client, headers_vendedora):
    assert client.post("/auth/logout", headers=headers_vendedora).status_code == 204


def test_token_nao_funciona_depois_do_logout(client, headers_vendedora):
    assert client.get("/usuarios/me", headers=headers_vendedora).status_code == 200

    client.post("/auth/logout", headers=headers_vendedora)
    resposta = client.get("/usuarios/me", headers=headers_vendedora)

    assert resposta.status_code == 401
    assert "login" in resposta.json()["detail"].lower()


def test_logout_nao_derruba_outras_sessoes_do_mesmo_usuario(client, usuario_cadastrado):
    sessao_a = _login(client, usuario_cadastrado)
    sessao_b = _login(client, usuario_cadastrado)

    client.post("/auth/logout", headers=sessao_a)

    assert client.get("/usuarios/me", headers=sessao_a).status_code == 401
    assert client.get("/usuarios/me", headers=sessao_b).status_code == 200


def test_logout_duas_vezes_com_o_mesmo_token_retorna_401(client, headers_vendedora):
    client.post("/auth/logout", headers=headers_vendedora)

    assert client.post("/auth/logout", headers=headers_vendedora).status_code == 401


def test_logout_sem_token_retorna_401(client):
    assert client.post("/auth/logout").status_code == 401


def test_logout_com_token_invalido_retorna_401(client):
    resposta = client.post("/auth/logout", headers={"Authorization": "Bearer lixo"})

    assert resposta.status_code == 401


def test_depois_do_logout_da_para_entrar_de_novo(client, usuario_cadastrado):
    sessao = _login(client, usuario_cadastrado)
    client.post("/auth/logout", headers=sessao)

    nova = _login(client, usuario_cadastrado)

    assert client.get("/usuarios/me", headers=nova).status_code == 200


def test_rotas_protegidas_exigem_token_com_mensagem_clara(client):
    resposta = client.get("/usuarios/me")

    assert resposta.status_code == 401
    assert resposta.headers["WWW-Authenticate"] == "Bearer"
    assert "login" in resposta.json()["detail"].lower()
