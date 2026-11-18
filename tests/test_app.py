"""Configuração geral da aplicação: cabeçalhos de segurança, CORS, docs e ciclo de vida."""

import importlib
import re

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.config import settings
from app.services import backup as backup_service


@pytest.fixture
def recarregar(monkeypatch):
    """Recarrega app.main com as configurações alteradas e restaura no fim."""

    def _recarregar(**config):
        for chave, valor in config.items():
            monkeypatch.setattr(settings, chave, valor)
        return importlib.reload(main_module).app

    yield _recarregar
    monkeypatch.undo()
    importlib.reload(main_module)


def test_health_nao_exige_login(client):
    resposta = client.get("/health")

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_respostas_da_api_trazem_cabecalhos_de_seguranca(client, headers_admin):
    resposta = client.get("/usuarios/me", headers=headers_admin)

    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["X-Frame-Options"] == "DENY"
    assert resposta.headers["Referrer-Policy"] == "no-referrer"
    assert resposta.headers["Cache-Control"] == "no-store"


def test_erros_tambem_trazem_os_cabecalhos(client):
    resposta = client.get("/usuarios/me")  # 401

    assert resposta.status_code == 401
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["Cache-Control"] == "no-store"


def test_documentacao_nao_recebe_no_store(client):
    assert "Cache-Control" not in client.get("/openapi.json").headers


def test_sem_cors_configurado_nao_ha_cabecalho_de_cors(recarregar):
    app = recarregar(CORS_ORIGINS="")

    resposta = TestClient(app).get("/health", headers={"Origin": "http://qualquer.com"})

    assert "access-control-allow-origin" not in resposta.headers


def test_cors_libera_so_a_origem_configurada(recarregar):
    app = recarregar(CORS_ORIGINS="http://localhost:5173, https://sistema.casadasopa.org")
    cliente = TestClient(app)

    permitida = cliente.get("/health", headers={"Origin": "http://localhost:5173"})
    outra = cliente.get("/health", headers={"Origin": "http://site-malicioso.com"})

    assert permitida.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in outra.headers
    assert "access-control-allow-credentials" not in permitida.headers


def test_cors_preflight_so_aceita_os_metodos_e_cabecalhos_previstos(recarregar):
    app = recarregar(CORS_ORIGINS="http://localhost:5173")

    ok = TestClient(app).options(
        "/pedidos",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    ruim = TestClient(app).options(
        "/pedidos",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PUT",
        },
    )

    assert ok.status_code == 200
    assert ruim.status_code == 400


def test_documentacao_some_em_producao(recarregar):
    app = recarregar(ENVIRONMENT="production")
    cliente = TestClient(app)

    assert cliente.get("/docs").status_code == 404
    assert cliente.get("/redoc").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404
    assert cliente.get("/health").status_code == 200


def test_documentacao_existe_em_desenvolvimento(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_ciclo_de_vida_nao_liga_o_backup_quando_desligado(monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_ENABLED", False)
    monkeypatch.setattr(backup_service, "_agendador", None)

    with TestClient(main_module.app) as c:
        assert c.get("/health").status_code == 200
        assert backup_service._agendador is None


def test_ciclo_de_vida_liga_e_desliga_o_agendador(monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_ENABLED", True)
    monkeypatch.setattr(backup_service, "_agendador", None)

    with TestClient(main_module.app):
        assert backup_service._agendador is not None
        assert backup_service._agendador.running

    assert backup_service._agendador is None


def _operacoes(app) -> list[tuple[str, str]]:
    """(método, caminho) de TODAS as rotas, lidas do OpenAPI.

    Atenção: `app.routes` não serve para isso. Nas versões novas do FastAPI ele guarda os
    módulos como "roteadores incluídos" e não lista as rotas de cada um, então uma varredura
    por ele só enxergaria /health e a documentação (e passaria sem testar nada).
    """
    operacoes = []
    for caminho, metodos in app.openapi()["paths"].items():
        for metodo in metodos:
            if metodo.upper() in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
                operacoes.append((metodo.upper(), caminho))
    return operacoes


PUBLICAS = {
    ("GET", "/health"),
    ("POST", "/auth/login"),
    ("POST", "/auth/login/json"),
    ("GET", "/sistema/logo"),  # a tela de login precisa da logo antes de entrar
}


def test_a_varredura_enxerga_todas_as_rotas(client):
    """Garante que a rede de segurança abaixo não está olhando para quase nada."""
    operacoes = _operacoes(client.app)

    assert len(operacoes) >= 50
    for esperada in [
        ("POST", "/pedidos"),
        ("DELETE", "/usuarios/{id_usuario}"),
        ("GET", "/relatorios/analise"),
        ("POST", "/sistema/backup"),
    ]:
        assert esperada in operacoes
    assert set(operacoes) >= PUBLICAS


def test_todas_as_rotas_de_dados_exigem_autenticacao(client):
    """Rede de segurança: qualquer rota nova que esqueça o login derruba este teste."""
    for metodo, caminho in _operacoes(client.app):
        if (metodo, caminho) in PUBLICAS:
            continue
        concreto = re.sub(r"\{[^}]+\}", "1", caminho)
        resposta = client.request(metodo, concreto, json={})
        assert resposta.status_code == 401, f"{metodo} {caminho} -> {resposta.status_code}"


def test_rotas_so_da_administradora_recusam_a_vendedora(client, headers_vendedora):
    """Quem não é administradora recebe 403 nas áreas restritas (cobre todas de uma vez)."""
    restritas = [
        ("GET", "/usuarios"),
        ("POST", "/usuarios"),
        ("GET", "/usuarios/1"),
        ("PATCH", "/usuarios/1"),
        ("DELETE", "/usuarios/1"),
        ("POST", "/usuarios/1/reativar"),
        ("POST", "/estoque/entradas"),
        ("POST", "/estoque/saidas"),
        ("GET", "/estoque/movimentacoes"),
        ("GET", "/estoque/movimentacoes/resumo"),
        ("GET", "/relatorios/dashboard"),
        ("GET", "/relatorios/analise"),
        ("GET", "/relatorios/vendas"),
        ("GET", "/relatorios/vendas/pedidos"),
        ("GET", "/relatorios/vendas/exportar"),
        ("GET", "/sistema/backup"),
        ("POST", "/sistema/backup"),
        ("POST", "/sistema/logo"),
        ("DELETE", "/sistema/logo"),
        ("GET", "/sistema/logo/situacao"),
    ]
    for metodo, caminho in restritas:
        resposta = client.request(metodo, caminho, json={}, headers=headers_vendedora)
        assert resposta.status_code == 403, f"{metodo} {caminho} -> {resposta.status_code}"

    # e nenhuma rota restrita ficou de fora da lista acima
    admin_ou_publica = {(m, c) for m, c in _operacoes(client.app)}
    cobertas = {(m, re.sub(r"\d+", "{x}", c)) for m, c in restritas}
    for metodo, caminho in admin_ou_publica:
        if caminho.split("/")[1] in {"usuarios", "relatorios"} or caminho.startswith(
            ("/estoque/entradas", "/estoque/saidas", "/estoque/movimentacoes", "/sistema")
        ):
            if (metodo, caminho) in PUBLICAS:
                continue
            assert (metodo, re.sub(r"\{[^}]+\}", "{x}", caminho)) in cobertas or caminho in {
                "/usuarios/me"
            }, f"rota restrita sem teste: {metodo} {caminho}"
