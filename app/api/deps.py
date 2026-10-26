"""Dependências compartilhadas pelos endpoints."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.errors import AcessoNegadoError
from app.core.security import decodificar_access_token
from app.db.session import get_db
from app.models.usuario import CARGO_ADMINISTRADORA, Usuario
from app.services import usuario as usuario_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def get_usuario_atual(
    db: DbSession,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> Usuario:
    """Resolve o usuário dono do token, ou devolve 401."""
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decodificar_access_token(token)
    if payload is None:
        raise credenciais_invalidas

    sub = payload.get("sub")
    if sub is None:
        raise credenciais_invalidas

    try:
        id_usuario = int(sub)
    except (TypeError, ValueError):
        raise credenciais_invalidas from None

    usuario = usuario_service.buscar_por_id(db, id_usuario)
    if usuario is None:
        raise credenciais_invalidas
    if not usuario.is_ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo.",
        )
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
