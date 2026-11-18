"""Serve o front-end compilado (pasta ``app/web``) pelo próprio backend.

Assim o sistema roda com um único comando e **sem CORS**: página e API têm a mesma origem.
O front usa rotas com ``#`` (``/#/pedidos``), então não há conflito com as rotas da API.
"""

from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# A página só carrega script, estilo, imagem e dados do próprio servidor. `blob:` é para abrir
# o PDF do cupom e mostrar a logo recém-enviada. Nenhum script de terceiros é permitido.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
    "object-src 'self' blob:; frame-src 'self' blob:; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


class SpaArquivos(StaticFiles):
    """Arquivos estáticos com os cabeçalhos certos para uma aplicação de página única."""

    async def get_response(self, path: str, scope: Scope):  # type: ignore[no-untyped-def]
        resposta = await super().get_response(path, scope)
        if resposta.headers.get("content-type", "").startswith("text/html"):
            resposta.headers["Content-Security-Policy"] = CSP
            resposta.headers["Cache-Control"] = "no-store"  # sempre a versão mais nova da página
        elif Path(path).parts[:1] == ("assets",):
            # Arquivos com hash no nome nunca mudam: o navegador pode guardar por um ano.
            resposta.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resposta


def montar_spa(app: FastAPI, diretorio: Path) -> bool:
    """Monta o front na raiz, DEPOIS das rotas da API (que têm prioridade).

    Devolve False (e não monta nada) se o front ainda não foi compilado.
    """
    if not (diretorio / "index.html").is_file():
        return False
    app.mount("/", SpaArquivos(directory=diretorio, html=True), name="web")
    return True
