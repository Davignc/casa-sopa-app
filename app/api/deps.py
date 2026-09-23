"""Dependências compartilhadas pelos endpoints."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decodificar_access_token
from app.db.session import get_db
from app.models.usuario import Usuario
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
