import pytest
from sqlalchemy import select

from app import cli
from app.core.security import verificar_senha
from app.models.usuario import Usuario


@pytest.fixture(autouse=True)
def _sessao_de_teste(monkeypatch, db):
    """A CLI usa a mesma sessão transacional do teste (nada vai para o banco real)."""
    monkeypatch.setattr(cli, "SessionLocal", lambda: db)


def test_criar_admin_cria_administradora_com_senha_em_hash(db):
    id_usuario = cli.criar_admin("Ana", "ana@casadasopa.org", "(16) 98888-7777", "senhaForte123")

    usuario = db.get(Usuario, id_usuario)
    assert usuario.cargo == "administradora"
    assert usuario.is_ativo is True
    assert usuario.telefone == "16988887777"
    assert usuario.senha != "senhaForte123"
    assert verificar_senha("senhaForte123", usuario.senha)


def test_criar_admin_duplicada_falha_sem_stacktrace(db):
    cli.criar_admin("Ana", "ana@casadasopa.org", "16988887777", "senhaForte123")

    with pytest.raises(SystemExit) as erro:
        cli.criar_admin("Outra", "ana@casadasopa.org", "16977776666", "senhaForte123")

    assert "e-mail" in str(erro.value)
    assert len(db.scalars(select(Usuario)).all()) == 1


@pytest.mark.parametrize(
    ("email", "telefone", "senha"),
    [
        ("invalido", "16988887777", "senhaForte123"),
        ("ana@casadasopa.org", "123", "senhaForte123"),
        ("ana@casadasopa.org", "16988887777", "curta"),
    ],
)
def test_criar_admin_com_dados_invalidos_falha(email, telefone, senha):
    with pytest.raises(SystemExit) as erro:
        cli.criar_admin("Ana", email, telefone, senha)

    assert "inválidos" in str(erro.value)


def test_main_le_a_senha_da_variavel_de_ambiente(monkeypatch, db, capsys):
    monkeypatch.setenv("CASA_SOPA_ADMIN_SENHA", "senhaForte123")

    codigo = cli.main(
        [
            "criar-admin",
            "--nome",
            "Ana",
            "--email",
            "ana@casadasopa.org",
            "--telefone",
            "16988887777",
        ]
    )

    assert codigo == 0
    assert "Administradora criada" in capsys.readouterr().out
