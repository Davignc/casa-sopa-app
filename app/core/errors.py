"""Erros de negócio e tratamento centralizado de exceções (RNF07).

Os serviços lançam subclasses de ``ErroDeNegocio``; os handlers abaixo convertem
tudo em respostas JSON padronizadas ``{"detail": "..."}``, sem nunca vazar
detalhes internos (stack trace, SQL) para o cliente.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("casa_sopa")


class ErroDeNegocio(Exception):
    """Violação de regra de negócio. Subclasses definem o status HTTP."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = "Requisição inválida."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.detail
        super().__init__(self.detail)


class NaoEncontradoError(ErroDeNegocio):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Registro não encontrado."


class ConflitoError(ErroDeNegocio):
    status_code = status.HTTP_409_CONFLICT
    detail = "Conflito com um registro existente."


class AcessoNegadoError(ErroDeNegocio):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Acesso negado."


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(ErroDeNegocio)
    async def _erro_de_negocio(_: Request, exc: ErroDeNegocio) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(IntegrityError)
    async def _integridade(_: Request, exc: IntegrityError) -> JSONResponse:
        # Rede de segurança: uma constraint do banco foi violada e o serviço não
        # tratou antes. Registra o detalhe no log e devolve uma mensagem genérica.
        logger.warning("Violação de integridade: %s", exc.orig)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Os dados enviados violam uma regra de integridade."},
        )

    @app.exception_handler(Exception)
    async def _inesperado(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Erro não tratado", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Erro interno. Tente novamente mais tarde."},
        )
