"""Servir o front compilado: prioridade da API, cabeçalhos de segurança e cache."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.spa import CSP, montar_spa


@pytest.fixture
def web(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Sistema</title><div id=root></div>")
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log('ok')")
    (tmp_path / "segredo.txt").write_text("fora da pasta web")
    pasta = tmp_path / "pub"
    pasta.mkdir()
    for arq in ("index.html", "assets"):
        (tmp_path / arq).rename(pasta / arq)
    return pasta


@pytest.fixture
def c(web):
    app = FastAPI()

    @app.get("/clientes")
    def api():
        return {"origem": "api"}

    assert montar_spa(app, web) is True
    return TestClient(app)


def test_a_raiz_entrega_o_index_com_politica_de_seguranca(c):
    resposta = c.get("/")

    assert resposta.status_code == 200
    assert "Sistema" in resposta.text
    assert resposta.headers["content-security-policy"] == CSP
    assert resposta.headers["cache-control"] == "no-store"


def test_a_politica_so_permite_recursos_do_proprio_servidor(c):
    politica = c.get("/").headers["content-security-policy"]

    assert "default-src 'self'" in politica
    assert "script-src 'self'" in politica
    assert "'unsafe-eval'" not in politica
    assert "http" not in politica  # nenhum domínio externo liberado
    assert "frame-ancestors 'none'" in politica


def test_a_api_tem_prioridade_sobre_o_front(c):
    assert c.get("/clientes").json() == {"origem": "api"}


def test_arquivos_com_hash_podem_ficar_em_cache(c):
    resposta = c.get("/assets/app-abc123.js")

    assert resposta.status_code == 200
    assert "immutable" in resposta.headers["cache-control"]
    assert "content-security-policy" not in resposta.headers


def test_caminho_inexistente_retorna_404(c):
    assert c.get("/nao-existe.js").status_code == 404


@pytest.mark.parametrize(
    "caminho",
    ["/../segredo.txt", "/%2e%2e/segredo.txt", "/assets/../../segredo.txt", "/..%2fsegredo.txt"],
)
def test_nao_sai_da_pasta_do_front(c, caminho):
    resposta = c.get(caminho)

    assert "fora da pasta web" not in resposta.text
    assert resposta.status_code in (301, 307, 308, 400, 404)


def test_sem_front_compilado_nao_monta_nada(tmp_path):
    app = FastAPI()

    assert montar_spa(app, tmp_path / "inexistente") is False
    assert TestClient(app).get("/").status_code == 404
