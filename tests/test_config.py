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
