"""Dependências compartilhadas pelos endpoints."""

import hmac
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core import protecao
from app.core.errors import AcessoNegadoError, NaoAutenticadoError
from app.core.security import decodificar_access_token, versao_da_senha
from app.db.session import get_db
from app.models.usuario import CARGO_ADMINISTRADORA, CARGOS, Usuario
from app.services import usuario as usuario_service

# auto_error=False: a mensagem de "sem token" é nossa, em português (RNF01).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_token_payload(token: Annotated[str | None, Depends(oauth2_scheme)]) -> dict[str, Any]:
    """Valida o token (assinatura, expiração) e confere se não foi encerrado no logout."""
    if token is None:
        raise NaoAutenticadoError("Faça login para continuar.")
    payload = decodificar_access_token(token)
    if payload is None:
        raise NaoAutenticadoError
    if protecao.revogador_tokens.esta_revogado(payload["jti"]):
        raise NaoAutenticadoError("Sessão encerrada. Faça login novamente.")
    return payload


TokenAtual = Annotated[dict[str, Any], Depends(get_token_payload)]


def get_usuario_atual(db: DbSession, payload: TokenAtual) -> Usuario:
    """Resolve o usuário dono do token, ou devolve 401/403."""
    try:
        id_usuario = int(payload["sub"])
    except (TypeError, ValueError):
        raise NaoAutenticadoError from None

    usuario = usuario_service.buscar_por_id(db, id_usuario)
    if usuario is None:
        raise NaoAutenticadoError

    # Senha trocada depois da emissão do token => token antigo deixa de valer.
    if not hmac.compare_digest(str(payload.get("sv", "")), versao_da_senha(usuario.senha)):
        raise NaoAutenticadoError("Sessão expirada. Faça login novamente.")

    if not usuario.is_ativo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo.")
    return usuario


UsuarioAtual = Annotated[Usuario, Depends(get_usuario_atual)]


def exige_cargo(*cargos: str) -> Callable[[Usuario], Usuario]:
    """Fábrica de dependência: só deixa passar usuários com um dos cargos (RN01).

    O cargo vem do banco a cada request, não do token — então rebaixar ou
    inativar uma usuária vale imediatamente, sem esperar o token expirar.
    """

    def _verifica(usuario: UsuarioAtual) -> Usuario:
        if usuario.cargo not in cargos:
            raise AcessoNegadoError("Você não tem permissão para esta operação.")
        return usuario

    return _verifica


AdminAtual = Annotated[Usuario, Depends(exige_cargo(CARGO_ADMINISTRADORA))]
# Qualquer cargo reconhecido (administradora ou vendedora): módulos operacionais.
OperadorAtual = Annotated[Usuario, Depends(exige_cargo(*CARGOS))]
