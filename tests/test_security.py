from datetime import timedelta

import pytest

from app.core.security import (
    criar_access_token,
    decodificar_access_token,
    hash_senha,
    verificar_senha,
)


def test_hash_nao_e_a_senha_em_texto_puro():
    senha = "senhaForte123"
    assert hash_senha(senha) != senha


def test_hash_usa_bcrypt():
    assert hash_senha("senhaForte123").startswith("$2b$")


def test_hashes_da_mesma_senha_sao_diferentes():
    """O salt aleatório garante hashes distintos para a mesma senha."""
    senha = "senhaForte123"
    assert hash_senha(senha) != hash_senha(senha)


def test_verificar_senha_correta():
    assert verificar_senha("senhaForte123", hash_senha("senhaForte123"))


def test_verificar_senha_incorreta():
    assert not verificar_senha("errada", hash_senha("senhaForte123"))


def test_verificar_senha_com_hash_invalido_nao_estoura():
    assert not verificar_senha("senhaForte123", "nao-e-um-hash")


def test_token_carrega_o_subject():
    payload = decodificar_access_token(criar_access_token(42))
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["type"] == "access"


def test_token_expirado_e_rejeitado():
    token = criar_access_token(1, expires_delta=timedelta(minutes=-1))
    assert decodificar_access_token(token) is None


def test_token_com_assinatura_adulterada_e_rejeitado():
    token = criar_access_token(1)
    adulterado = token[:-3] + ("abc" if not token.endswith("abc") else "xyz")
    assert decodificar_access_token(adulterado) is None


def test_token_lixo_e_rejeitado():
    assert decodificar_access_token("isso.nao.e.um.jwt") is None


@pytest.mark.parametrize("senha", ["a", "áéíóú", "x" * 72])
def test_ida_e_volta_de_varias_senhas(senha):
    assert verificar_senha(senha, hash_senha(senha))
