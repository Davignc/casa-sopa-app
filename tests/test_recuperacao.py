from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.services import recuperacao
from app.services.usuario import buscar_por_email


@pytest.fixture
def smtp(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_USER", "ong@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", SecretStr("senha-app-teste"))
    with patch.object(recuperacao, "enviar_email") as envio:
        yield envio


def test_recuperacao_nao_revela_contas(client, usuario_cadastrado, smtp):
    real = client.post("/auth/recuperar-senha", json={"email": usuario_cadastrado["email"]})
    falso = client.post("/auth/recuperar-senha", json={"email": "ninguem@example.org"})
    assert real.status_code == falso.status_code == 202
    assert real.json() == falso.json()
    smtp.assert_called_once()
    assert "token" not in real.json()


def test_recuperacao_inativa_nao_envia(client, db, usuario_cadastrado, smtp):
    usuario = buscar_por_email(db, usuario_cadastrado["email"])
    usuario.is_ativo = False
    db.commit()
    assert client.post("/auth/recuperar-senha", json={"email": usuario.email}).status_code == 202
    smtp.assert_not_called()


def test_sem_smtp_informa_indisponibilidade(client, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_USER", "")
    assert client.post("/auth/recuperar-senha", json={"email": "x@example.org"}).status_code == 503


def test_limite_de_envios(client, usuario_cadastrado, smtp):
    for _ in range(3):
        assert (
            client.post(
                "/auth/recuperar-senha", json={"email": usuario_cadastrado["email"]}
            ).status_code
            == 202
        )
    resposta = client.post("/auth/recuperar-senha", json={"email": usuario_cadastrado["email"]})
    assert resposta.status_code == 429
    assert "Retry-After" in resposta.headers


def test_redefinicao_uso_unico_revoga_sessoes(client, db, token, usuario_cadastrado, smtp):
    client.post("/auth/recuperar-senha", json={"email": usuario_cadastrado["email"]})
    link = smtp.call_args.args[1]
    dados = {"token": link, "senha": "NovaSenha123"}
    assert client.post("/auth/redefinir-senha", json=dados).status_code == 204
    assert client.post("/auth/redefinir-senha", json=dados).status_code == 422
    assert (
        client.get("/usuarios/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    )
    assert (
        client.post(
            "/auth/login/json",
            json={"email": usuario_cadastrado["email"], "senha": usuario_cadastrado["senha"]},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login/json", json={"email": usuario_cadastrado["email"], "senha": "NovaSenha123"}
        ).status_code
        == 200
    )
    # Link de recuperação não serve como sessão.
    assert (
        client.get("/usuarios/me", headers={"Authorization": f"Bearer {link}"}).status_code == 401
    )


@pytest.mark.parametrize("caso", ["expirado", "adulterado", "acesso", "inativo", "email_alterado"])
def test_links_invalidos(client, db, usuario_cadastrado, token, caso):
    usuario = buscar_por_email(db, usuario_cadastrado["email"])
    link = recuperacao.criar_token(usuario)
    if caso == "expirado":
        dados = jwt.decode(link, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        dados["exp"] = datetime.now(UTC) - timedelta(seconds=1)
        link = jwt.encode(dados, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    elif caso == "adulterado":
        link = "invalid." + link
    elif caso == "acesso":
        link = token
    elif caso == "inativo":
        usuario.is_ativo = False
        db.commit()
    else:
        usuario.email = "outro@example.org"
        db.commit()
    assert (
        client.post(
            "/auth/redefinir-senha", json={"token": link, "senha": "NovaSenha123"}
        ).status_code
        == 422
    )


def test_senha_longa_em_bytes_recusada(client):
    assert (
        client.post("/auth/redefinir-senha", json={"token": "x", "senha": "á" * 40}).status_code
        == 422
    )


def test_smtp_envia_por_tls_sem_expor_segredo(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_USER", "ong@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", SecretStr("senha-app-teste"))
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    with patch("smtplib.SMTP") as fabrica:
        # O serviço usa o próprio objeto SMTP no bloco with.
        recuperacao.enviar_email("pessoa@example.org", "token-teste")
        conexao = fabrica.return_value
        conexao.starttls.assert_called_once()
        conexao.login.assert_called_once_with("ong@gmail.com", "senha-app-teste")
        mensagem = conexao.send_message.call_args.args[0]
        assert mensagem["To"] == "pessoa@example.org"
        assert "#/redefinir-senha?token=token-teste" in mensagem.get_content()
        assert "senha-app-teste" not in mensagem.get_content()
