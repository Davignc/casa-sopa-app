from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, UsuarioAtual
from app.schemas.usuario import UsuarioCreate, UsuarioRead
from app.services import usuario as usuario_service

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.post("", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def criar_usuario(dados: UsuarioCreate, db: DbSession) -> UsuarioRead:
    """Cadastra um novo usuário. A senha é gravada apenas como hash bcrypt."""
    try:
        usuario = usuario_service.criar_usuario(db, dados)
    except usuario_service.EmailJaCadastradoError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um usuário com este e-mail.",
        ) from None
    return UsuarioRead.model_validate(usuario)


@router.get("/me", response_model=UsuarioRead)
def ler_usuario_atual(usuario: UsuarioAtual) -> UsuarioRead:
    """Dados do usuário autenticado."""
    return UsuarioRead.model_validate(usuario)
