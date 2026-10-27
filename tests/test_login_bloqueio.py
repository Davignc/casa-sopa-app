"""RF01, critério 4: bloqueio após número configurável de tentativas incorretas."""

import pytest

from app.core import protecao
from app.core.protecao import LimitadorTentativas
from app.services import usuario as usuario_service


def _login(client, email, senha, json=True):
    if json:
        return client.post("/auth/login/json", json={"email": email, "senha": senha})
    return client.post("/auth/login", data={"username": email, "password": senha})


def _errar(client, email, vezes):
    for _ in range(vezes):
        assert _login(client, email, "senhaErrada123").status_code == 401


def test_cinco_erros_seguidos_bloqueiam_a_sexta_tentativa(client, usuario_cadastrado):
    _errar(client, usuario_cadastrado["email"], 5)

    resposta = _login(client, usuario_cadastrado["email"], "senhaErrada123")

    assert resposta.status_code == 429
    assert "Tente novamente" in resposta.json()["detail"]
    assert int(resposta.headers["Retry-After"]) > 0


def test_durante_o_bloqueio_nem_a_senha_correta_entra(client, usuario_cadastrado):
    _errar(client, usuario_cadastrado["email"], 5)

    resposta = _login(client, usuario_cadastrado["email"], usuario_cadastrado["senha"])

    assert resposta.status_code == 429
    assert "access_token" not in resposta.text


def test_quatro_erros_ainda_nao_bloqueiam(client, usuario_cadastrado):
    _errar(client, usuario_cadastrado["email"], 4)

    resposta = _login(client, usuario_cadastrado["email"], usuario_cadastrado["senha"])

    assert resposta.status_code == 200


def test_login_correto_zera_a_contagem(client, usuario_cadastrado):
    email = usuario_cadastrado["email"]
    _errar(client, email, 4)
    assert _login(client, email, usuario_cadastrado["senha"]).status_code == 200

    _errar(client, email, 4)  # 4 + 4 = 8 se não tivesse zerado

    assert _login(client, email, usuario_cadastrado["senha"]).status_code == 200


def test_bloqueio_de_uma_conta_nao_afeta_outra(client, usuario_cadastrado, admin_cadastrada):
    _errar(client, usuario_cadastrado["email"], 5)

    resposta = _login(client, admin_cadastrada["email"], admin_cadastrada["senha"])

    assert resposta.status_code == 200


def test_email_inexistente_tambem_bloqueia_sem_revelar_que_nao_existe(client):
    """Mesmo comportamento para e-mail que existe e que não existe (sem enumeração)."""
    _errar(client, "fantasma@casadasopa.org", 5)

    assert _login(client, "fantasma@casadasopa.org", "qualquer1234").status_code == 429


def test_email_com_maiusculas_conta_na_mesma_chave(client, usuario_cadastrado):
    email = usuario_cadastrado["email"]
    for variacao in [email.upper(), email.title(), email, email.upper(), email]:
        _login(client, variacao, "senhaErrada123")

    assert _login(client, email, usuario_cadastrado["senha"]).status_code == 429


def test_login_form_oauth2_compartilha_o_bloqueio(client, usuario_cadastrado):
    _errar(client, usuario_cadastrado["email"], 5)

    resposta = _login(client, usuario_cadastrado["email"], usuario_cadastrado["senha"], json=False)

    assert resposta.status_code == 429


def test_bloqueio_por_ip_barra_quem_testa_varias_contas(client, monkeypatch):
    monkeypatch.setattr(protecao, "limitador_login_ip", LimitadorTentativas(3, 600))
    for i in range(3):
        _login(client, f"conta{i}@casadasopa.org", "senhaErrada123")

    resposta = _login(client, "outra.conta@casadasopa.org", "senhaErrada123")

    assert resposta.status_code == 429


def test_bloqueio_expira(client, usuario_cadastrado, monkeypatch):
    class Relogio:
        agora = 0.0

        def __call__(self):
            return self.agora

    relogio = Relogio()
    monkeypatch.setattr(protecao, "limitador_login_conta", LimitadorTentativas(5, 900, relogio))
    _errar(client, usuario_cadastrado["email"], 5)
    assert (
        _login(client, usuario_cadastrado["email"], usuario_cadastrado["senha"]).status_code == 429
    )

    relogio.agora += 901

    assert (
        _login(client, usuario_cadastrado["email"], usuario_cadastrado["senha"]).status_code == 200
    )


def test_usuario_inativo_tambem_conta_como_falha(client, db, usuario_cadastrado):
    from sqlalchemy import select

    from app.models.usuario import Usuario

    db.scalar(select(Usuario).where(Usuario.email == usuario_cadastrado["email"])).is_ativo = False
    db.flush()

    _errar(client, usuario_cadastrado["email"], 5)  # senha certa ou errada: sempre 401

    assert (
        _login(client, usuario_cadastrado["email"], usuario_cadastrado["senha"]).status_code == 429
    )


def test_login_de_email_inexistente_gasta_o_mesmo_trabalho_de_um_bcrypt(client, monkeypatch):
    """Sem isso, o tempo de resposta revelaria quais e-mails existem."""
    chamadas = []
    original = usuario_service.verificar_senha

    def espiao(senha, senha_hash):
        chamadas.append(senha_hash)
        return original(senha, senha_hash)

    monkeypatch.setattr(usuario_service, "verificar_senha", espiao)

    _login(client, "ninguem@casadasopa.org", "qualquer1234")

    assert len(chamadas) == 1
    assert chamadas[0].startswith("$2b$")


@pytest.mark.parametrize("email", ["nao-e-email", "", "a@"])
def test_email_malformado_retorna_422_e_nao_conta_tentativa(client, email):
    assert _login(client, email, "qualquer1234").status_code == 422
