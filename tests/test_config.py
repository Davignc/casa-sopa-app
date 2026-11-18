import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_secret_key_curta_e_recusada():
    with pytest.raises(ValidationError) as erro:
        Settings(_env_file=None, DATABASE_URL="postgresql+psycopg://x", SECRET_KEY="curta")

    assert "SECRET_KEY" in str(erro.value)


def test_secret_key_vazia_e_recusada():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, DATABASE_URL="postgresql+psycopg://x", SECRET_KEY="")


def test_secret_key_com_32_caracteres_e_aceita():
    cfg = Settings(_env_file=None, DATABASE_URL="postgresql+psycopg://x", SECRET_KEY="a" * 32)

    assert cfg.ENVIRONMENT == "development"


def _cfg(**kw):
    return Settings(
        _env_file=None, DATABASE_URL="postgresql+psycopg://x", SECRET_KEY="a" * 32, **kw
    )


def test_bcrypt_fraco_e_recusado_em_producao():
    with pytest.raises(ValidationError) as erro:
        _cfg(ENVIRONMENT="production", BCRYPT_ROUNDS=4)

    assert "BCRYPT_ROUNDS" in str(erro.value)


def test_bcrypt_fraco_e_aceito_fora_de_producao():
    assert _cfg(ENVIRONMENT="development", BCRYPT_ROUNDS=4).BCRYPT_ROUNDS == 4


def test_bcrypt_padrao_e_12(monkeypatch):
    monkeypatch.delenv("BCRYPT_ROUNDS", raising=False)  # o conftest baixa para 4 nos testes

    assert _cfg().BCRYPT_ROUNDS == 12


@pytest.mark.parametrize("algoritmo", ["none", "RS256", "HS1", ""])
def test_algoritmo_do_jwt_fora_da_lista_e_recusado(algoritmo):
    with pytest.raises(ValidationError):
        _cfg(ALGORITHM=algoritmo)


@pytest.mark.parametrize(
    "campo", ["LOGIN_MAX_TENTATIVAS", "LOGIN_BLOQUEIO_MINUTOS", "ACCESS_TOKEN_EXPIRE_MINUTES"]
)
def test_limites_precisam_ser_positivos(campo):
    with pytest.raises(ValidationError):
        _cfg(**{campo: 0})
