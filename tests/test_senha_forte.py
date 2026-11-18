import pytest
from sqlalchemy import select

from app.core.security import hash_senha
from app.models.usuario import Usuario


@pytest.mark.parametrize(
    "senha",
    [
        "Aa1!abc",  # Menos de 8 caracteres.
        "123456789",
        "senhaforte123!",  # Sem maiúscula.
        "SENHAFORTE123!",  # Sem minúscula.
        "SenhaForte!!!",  # Sem número.
        "SenhaForte123",  # Sem símbolo.
        "SenhaForte123 ",  # Espaço não é símbolo.
        "SenhaForte123\x00",  # Controle não é símbolo.
        "Aa1!😀😀😀",  # Sete caracteres, apesar dos bytes extras dos emojis.
        "Aa1!" + "x" * 69,
        "Aa1!" + "á" * 35,  # Menos de 72 caracteres, mas mais de 72 bytes.
    ],
)
@pytest.mark.parametrize("operacao", ["cadastro", "troca"])
def test_api_recusa_senha_fraca_sem_alterar_banco(
    client, db, headers_admin, dados_usuario, usuario_cadastrado, senha, operacao
):
    usuario = db.scalar(select(Usuario).where(Usuario.email == dados_usuario["email"]))
    hash_anterior = usuario.senha
    if operacao == "cadastro":
        resposta = client.post(
            "/usuarios",
            headers=headers_admin,
            json={**dados_usuario, "email": "nova@casadasopa.org", "senha": senha},
        )
        assert db.scalar(select(Usuario).where(Usuario.email == "nova@casadasopa.org")) is None
    else:
        resposta = client.patch(
            f"/usuarios/{usuario.id_usuario}", headers=headers_admin, json={"senha": senha}
        )
        db.refresh(usuario)
        assert usuario.senha == hash_anterior
    assert resposta.status_code == 422
    assert senha not in resposta.text
    assert all("input" not in erro and "ctx" not in erro for erro in resposta.json()["detail"])


@pytest.mark.parametrize(
    "senha",
    ["Senha123!", "Senha123_", "Árvore12!", "Aa1!" + "x" * 68, "Aa1!" + "á" * 34, "  Senha123!  "],
)
@pytest.mark.parametrize("operacao", ["cadastro", "troca"])
def test_senha_forte_e_aceita_e_preservada_no_login(
    client, headers_admin, dados_usuario, usuario_cadastrado, db, senha, operacao
):
    if operacao == "cadastro":
        email = "nova@casadasopa.org"
        resposta = client.post(
            "/usuarios",
            headers=headers_admin,
            json={**dados_usuario, "email": email, "telefone": "16977776666", "senha": senha},
        )
        assert resposta.status_code == 201
    else:
        email = dados_usuario["email"]
        usuario = db.scalar(select(Usuario).where(Usuario.email == email))
        resposta = client.patch(
            f"/usuarios/{usuario.id_usuario}", headers=headers_admin, json={"senha": senha}
        )
        assert resposta.status_code == 200
    assert client.post("/auth/login/json", json={"email": email, "senha": senha}).status_code == 200
    if senha != senha.strip():
        assert (
            client.post(
                "/auth/login/json", json={"email": email, "senha": senha.strip()}
            ).status_code
            == 401
        )


def test_senha_antiga_fora_da_nova_regra_continua_valida(client, db, usuario_cadastrado):
    usuario = db.scalar(select(Usuario).where(Usuario.email == usuario_cadastrado["email"]))
    usuario.senha = hash_senha("antiga123")
    db.flush()
    assert (
        client.post(
            "/auth/login/json", json={"email": usuario.email, "senha": "antiga123"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/auth/login", data={"username": usuario.email, "password": "antiga123"}
        ).status_code
        == 200
    )
