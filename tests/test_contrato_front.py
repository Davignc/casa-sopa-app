"""O front só pode chamar rotas que o backend tem (mesmo método e caminho).

Lê o código-fonte do front (frontend/src) e compara com as rotas reais da API. Se alguém
renomear uma rota num lado e esquecer do outro, este teste falha na hora, em vez de a tela
quebrar só na hora de usar. É ignorado quando a pasta do front não está presente.
"""

import re
from pathlib import Path

import pytest

from app.main import app

FRONT = Path(__file__).resolve().parent.parent / "frontend" / "src"
pytestmark = pytest.mark.skipif(not FRONT.is_dir(), reason="pasta do front-end ausente")

CHAMADA = re.compile(r"\b(?:api|baixar)\s*(?:<[^()]*?>)?\s*\(\s*([`'\"])(/[^`'\"]*)\1", re.S)


def _fechamento(texto: str, abre: int) -> int:
    """Posição do parêntese que fecha o que abre em ``abre``."""
    nivel = 0
    for i in range(abre, len(texto)):
        if texto[i] == "(":
            nivel += 1
        elif texto[i] == ")":
            nivel -= 1
            if nivel == 0:
                return i
    return len(texto)


def _chamadas() -> list[tuple[str, str, str]]:
    achadas = []
    for arquivo in sorted(FRONT.rglob("*.ts*")):
        if ".test." in arquivo.name or "test/" in arquivo.as_posix():
            continue
        texto = arquivo.read_text(encoding="utf-8")
        for m in CHAMADA.finditer(texto):
            abre = texto.index("(", m.start())
            trecho = texto[abre : _fechamento(texto, abre) + 1]
            metodo = re.search(r"method:\s*'(\w+)'", trecho)
            if metodo:
                verbo = metodo.group(1)
            elif re.search(r"\b(body|form)\s*[:,}]", trecho):
                verbo = "POST"
            else:
                verbo = "GET"
            caminho = re.sub(r"\$\{[^}]*\}", "{p}", m.group(2))
            achadas.append((verbo.upper(), caminho, arquivo.name))
    return achadas


def _rotas_da_api() -> set[tuple[str, str]]:
    """Lidas do OpenAPI (app.routes não lista as rotas dos módulos nesta versão do FastAPI)."""
    rotas = set()
    for caminho, metodos in app.openapi()["paths"].items():
        normal = re.sub(r"\{[^}]+\}", "{p}", caminho)
        for metodo in metodos:
            rotas.add((metodo.upper(), normal))
    return rotas


def test_o_leitor_encontra_as_chamadas_do_front():
    chamadas = _chamadas()

    assert len(chamadas) > 40  # se isto falhar, o leitor quebrou (não o front)
    assert ("POST", "/auth/login/json", "auth.tsx") in chamadas
    assert ("DELETE", "/clientes/{p}", "Clientes.tsx") in chamadas
    assert any(c[:2] == ("GET", "/pedidos/{p}/cupom") for c in chamadas)


def test_toda_chamada_do_front_existe_no_backend():
    rotas = _rotas_da_api()

    faltando = sorted(
        {
            f"{metodo} {caminho}  ({arquivo})"
            for metodo, caminho, arquivo in _chamadas()
            if (metodo, caminho) not in rotas
        }
    )

    assert not faltando, "O front chama rotas que a API não tem:\n" + "\n".join(faltando)


def test_o_front_nao_chama_rotas_fora_do_prefixo_conhecido():
    prefixos = {
        "auth",
        "usuarios",
        "clientes",
        "enderecos",
        "produtos",
        "estoque",
        "pedidos",
        "relatorios",
        "importacoes",
        "sistema",
    }

    for _, caminho, arquivo in _chamadas():
        assert caminho.split("/")[1] in prefixos, f"{caminho} ({arquivo})"
