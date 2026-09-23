"""Fixtures da suite.

Cada teste roda dentro de uma transação que é revertida no fim, então um teste
nunca enxerga os dados do outro. O schema é criado uma vez por sessão no banco
apontado por TEST_DATABASE_URL.
"""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://casa_sopa:casa_sopa@localhost:5432/casa_sopa_test",
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Generator[Session, None, None]:
    """Sessão ligada a uma transação externa, descartada ao fim do teste."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """TestClient com o get_db apontando para a sessão transacional do teste."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def dados_usuario() -> dict[str, str]:
    return {
        "nome": "Maria da Silva",
        "email": "maria@casadasopa.org",
        "endereco": "Rua das Flores, 100",
        "telefone": "11999998888",
        "senha": "senhaForte123",
    }


@pytest.fixture
def usuario_cadastrado(client: TestClient, dados_usuario: dict[str, str]) -> dict[str, str]:
    """Cria o usuário via API e devolve os dados usados (com a senha em claro)."""
    resposta = client.post("/usuarios", json=dados_usuario)
    assert resposta.status_code == 201, resposta.text
    return dados_usuario


@pytest.fixture
def token(client: TestClient, usuario_cadastrado: dict[str, str]) -> str:
    resposta = client.post(
        "/auth/login/json",
        json={"email": usuario_cadastrado["email"], "senha": usuario_cadastrado["senha"]},
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["access_token"]
