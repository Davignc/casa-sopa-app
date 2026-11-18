from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


def _configurar_sqlite(engine: Engine) -> None:
    """Faz o SQLite se comportar como o banco "de verdade" onde importa.

    * ``PRAGMA foreign_keys=ON``: por padrão o SQLite ignora chaves estrangeiras.
    * BEGIN explícito: sem isso o driver do Python não abre transação nem SAVEPOINT
      direito (receita oficial do SQLAlchemy).
    """

    @event.listens_for(engine, "connect")
    def _ao_conectar(dbapi_conn, _):  # type: ignore[no-untyped-def]
        dbapi_conn.isolation_level = None
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "begin")
    def _ao_iniciar(conn):  # type: ignore[no-untyped-def]
        conn.exec_driver_sql("BEGIN")


def criar_engine(url: str) -> Engine:
    """Cria o engine. PostgreSQL é o alvo; SQLite serve para dev/testes sem servidor."""
    if url.startswith("sqlite"):
        opcoes: dict = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # Banco em memória: todas as threads precisam enxergar a MESMA conexão.
            opcoes["poolclass"] = StaticPool
        engine = create_engine(url, **opcoes)
        _configurar_sqlite(engine)
        return engine
    return create_engine(url, pool_pre_ping=True)


engine = criar_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Dependência do FastAPI: abre uma sessão por request e fecha no fim."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
