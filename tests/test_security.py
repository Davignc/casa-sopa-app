from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    criar_access_token,
    decodificar_access_token,
    hash_senha,
    verificar_senha,
    versao_da_senha,
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


def _token(sub=42, **kw):
    kw.setdefault("versao_senha", "v1")
    return criar_access_token(sub, **kw)


def test_token_carrega_o_subject():
    payload = decodificar_access_token(_token(42))
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["type"] == "access"


def test_token_tem_id_unico_e_versao_da_senha():
    a, b = decodificar_access_token(_token()), decodificar_access_token(_token())
    assert a["jti"] != b["jti"]
    assert a["sv"] == "v1"


def test_token_expirado_e_rejeitado():
    assert decodificar_access_token(_token(1, expires_delta=timedelta(minutes=-1))) is None


def test_token_com_assinatura_adulterada_e_rejeitado():
    token = _token(1)
    adulterado = token[:-3] + ("abc" if not token.endswith("abc") else "xyz")
    assert decodificar_access_token(adulterado) is None


def test_token_lixo_e_rejeitado():
    assert decodificar_access_token("isso.nao.e.um.jwt") is None


def test_token_assinado_com_outra_chave_e_rejeitado():
    falso = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) + timedelta(hours=1), "iat": datetime.now(UTC),
         "jti": "x", "type": "access"},
        "outra-chave-qualquer-com-mais-de-32-caracteres",
        algorithm="HS256",
    )  # fmt: skip
    assert decodificar_access_token(falso) is None


def test_token_sem_assinatura_alg_none_e_rejeitado():
    """Ataque clássico: trocar o algoritmo por 'none' para dispensar a assinatura."""
    agora = datetime.now(UTC)
    sem_assinatura = jwt.encode(
        {"sub": "1", "exp": agora + timedelta(hours=1), "iat": agora, "jti": "x",
         "type": "access"},
        None,
        algorithm="none",
    )  # fmt: skip
    assert decodificar_access_token(sem_assinatura) is None


@pytest.mark.parametrize("faltando", ["exp", "iat", "sub", "jti"])
def test_token_sem_campo_obrigatorio_e_rejeitado(faltando):
    agora = datetime.now(UTC)
    campos = {"sub": "1", "exp": agora + timedelta(hours=1), "iat": agora, "jti": "x",
              "type": "access"}  # fmt: skip
    campos.pop(faltando)
    token = jwt.encode(campos, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert decodificar_access_token(token) is None


def test_token_de_outro_tipo_e_rejeitado():
    agora = datetime.now(UTC)
    token = jwt.encode(
        {"sub": "1", "exp": agora + timedelta(hours=1), "iat": agora, "jti": "x",
         "type": "refresh"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )  # fmt: skip
    assert decodificar_access_token(token) is None


@pytest.mark.parametrize("senha", ["a", "áéíóú", "x" * 72])
def test_ida_e_volta_de_varias_senhas(senha):
    assert verificar_senha(senha, hash_senha(senha))


def test_senha_acima_de_72_bytes_e_recusada_no_hash():
    with pytest.raises(ValueError):
        hash_senha("x" * 73)


def test_senha_acima_de_72_bytes_nunca_confere():
    assert not verificar_senha("x" * 73, hash_senha("x" * 72))


def test_versao_da_senha_muda_quando_o_hash_muda():
    assert versao_da_senha(hash_senha("senhaForte123")) != versao_da_senha(hash_senha("outra12345"))
    assert versao_da_senha("abc") == versao_da_senha("abc")
