from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DbSession
from app.core.security import criar_access_token
from app.schemas.token import Token
from app.schemas.usuario import LoginRequest
from app.services import usuario as usuario_service

router = APIRouter(prefix="/auth", tags=["auth"])

CREDENCIAIS_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="E-mail ou senha incorretos.",
    headers={"WWW-Authenticate": "Bearer"},
)


@router.post("/login", response_model=Token)
def login(
    db: DbSession,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """Login no formato OAuth2 (form-urlencoded) — é o que o Swagger usa.

    O campo `username` recebe o e-mail do usuário.
    """
    usuario = usuario_service.autenticar(db, form.username, form.password)
    if usuario is None:
        raise CREDENCIAIS_INVALIDAS
    return Token(access_token=criar_access_token(usuario.id_usuario))


@router.post("/login/json", response_model=Token)
def login_json(dados: LoginRequest, db: DbSession) -> Token:
    """Mesmo login, recebendo JSON — mais conveniente para o front."""
    usuario = usuario_service.autenticar(db, dados.email, dados.senha)
    if usuario is None:
        raise CREDENCIAIS_INVALIDAS
    return Token(access_token=criar_access_token(usuario.id_usuario))
