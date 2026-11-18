"""RNF07: tratamento centralizado de erros, sem vazar detalhes internos."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.errors import (
    AcessoNegadoError,
    ConflitoError,
    ErroDeNegocio,
    NaoEncontradoError,
    registrar_handlers,
)


@pytest.fixture
def app_de_teste() -> FastAPI:
    app = FastAPI()
    registrar_handlers(app)

    @app.get("/negocio")
    def _negocio():
        raise ErroDeNegocio("Regra violada.")

    @app.get("/nao-encontrado")
    def _nao_encontrado():
        raise NaoEncontradoError

    @app.get("/conflito")
    def _conflito():
        raise ConflitoError("Já existe.")

    @app.get("/negado")
    def _negado():
        raise AcessoNegadoError

    @app.get("/integridade")
    def _integridade():
        raise IntegrityError("INSERT INTO segredo ...", {}, Exception("duplicate key tabela_x"))

    @app.get("/boom")
    def _boom():
        raise RuntimeError("senha do banco: 123456")

    return app


@pytest.fixture
def c(app_de_teste: FastAPI) -> TestClient:
    return TestClient(app_de_teste, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("rota", "status", "detail"),
    [
        ("/negocio", 400, "Regra violada."),
        ("/nao-encontrado", 404, "Registro não encontrado."),
        ("/conflito", 409, "Já existe."),
        ("/negado", 403, "Acesso negado."),
    ],
)
def test_erros_de_negocio_viram_json_padronizado(c, rota, status, detail):
    resposta = c.get(rota)

    assert resposta.status_code == status
    assert resposta.json() == {"detail": detail}


def test_violacao_de_integridade_vira_409_sem_vazar_sql(c):
    resposta = c.get("/integridade")

    assert resposta.status_code == 409
    assert "INSERT" not in resposta.text
    assert "tabela_x" not in resposta.text


def test_erro_inesperado_vira_500_generico(c):
    resposta = c.get("/boom")

    assert resposta.status_code == 500
    assert "123456" not in resposta.text
    assert "RuntimeError" not in resposta.text
    assert resposta.json() == {"detail": "Erro interno. Tente novamente mais tarde."}
