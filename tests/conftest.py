"""Fixtures da suite.

Cada teste roda dentro de uma transação que é revertida no fim, então um teste
nunca enxerga os dados do outro. O schema é criado uma vez por sessão no banco
apontado por TEST_DATABASE_URL (PostgreSQL, ou ``sqlite://`` para um banco
temporário em memória, sem precisar de servidor).
"""

import os
from collections.abc import Generator

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

# bcrypt com custo mínimo: a suíte faz centenas de hashes e o custo 12 (produção) a deixaria lenta.
os.environ.setdefault("BCRYPT_ROUNDS", "4")

# Permite definir TEST_DATABASE_URL no .env (o pydantic-settings não o exporta ao ambiente).
load_dotenv()

from app.core import protecao  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import criar_engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.usuario import UsuarioCreate  # noqa: E402
from app.services import usuario as usuario_service  # noqa: E402

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://casa_sopa:casa_sopa@localhost:5432/casa_sopa_test",
)


@pytest.fixture(scope="session")
def engine():
    eng = criar_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Generator[Session, None, None]:
    """Sessão ligada a uma transação externa, descartada ao fim do teste."""
    connection = engine.connect()
    transaction = connection.begin()
    # create_savepoint: commit/rollback dentro do app valem só até o savepoint, como em
    # produção, sem derrubar os dados que o próprio teste preparou.
    session = sessionmaker(
        bind=connection,
        autocommit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )()
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


@pytest.fixture(autouse=True)
def _zerar_protecoes() -> Generator[None, None, None]:
    """Bloqueios de login e tokens revogados vivem em memória: zera entre os testes."""
    protecao.limpar_tudo()
    yield
    protecao.limpar_tudo()


def cabecalho_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient, dados: dict[str, str]) -> str:
    resposta = client.post(
        "/auth/login/json", json={"email": dados["email"], "senha": dados["senha"]}
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["access_token"]


@pytest.fixture
def dados_usuario() -> dict[str, str]:
    """Dados de uma vendedora (o cargo mais comum no sistema)."""
    return {
        "nome": "Maria da Silva",
        "email": "maria@casadasopa.org",
        "telefone": "16999998888",
        "cargo": "vendedora",
        "comissao": "5.00",
        "senha": "senhaForte123",
    }


@pytest.fixture
def dados_admin() -> dict[str, str]:
    return {
        "nome": "Ana Administradora",
        "email": "ana@casadasopa.org",
        "telefone": "16988887777",
        "cargo": "administradora",
        "senha": "adminForte123",
    }


@pytest.fixture
def usuario_cadastrado(db: Session, dados_usuario: dict[str, str]) -> dict[str, str]:
    """Cria uma vendedora direto no banco e devolve os dados (com a senha em claro)."""
    usuario_service.criar_usuario(db, UsuarioCreate(**dados_usuario))
    return dados_usuario


@pytest.fixture
def admin_cadastrada(db: Session, dados_admin: dict[str, str]) -> dict[str, str]:
    usuario_service.criar_usuario(db, UsuarioCreate(**dados_admin))
    return dados_admin


@pytest.fixture
def token(client: TestClient, usuario_cadastrado: dict[str, str]) -> str:
    """Token da vendedora."""
    return _login(client, usuario_cadastrado)


@pytest.fixture
def token_admin(client: TestClient, admin_cadastrada: dict[str, str]) -> str:
    return _login(client, admin_cadastrada)


@pytest.fixture
def headers_admin(token_admin: str) -> dict[str, str]:
    return cabecalho_auth(token_admin)


@pytest.fixture
def headers_vendedora(token: str) -> dict[str, str]:
    return cabecalho_auth(token)
