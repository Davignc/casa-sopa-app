from fastapi import APIRouter, status

from app.api.deps import AdminAtual, DbSession, UsuarioAtual
from app.schemas.usuario import UsuarioCreate, UsuarioRead
from app.services import usuario as usuario_service

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.post("", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def criar_usuario(dados: UsuarioCreate, db: DbSession, _admin: AdminAtual) -> UsuarioRead:
    """Cadastra um novo usuário. Somente a administradora (RN03).

    A senha é gravada apenas como hash bcrypt.
    """
    usuario = usuario_service.criar_usuario(db, dados)
    return UsuarioRead.model_validate(usuario)


@router.get("/me", response_model=UsuarioRead)
def ler_usuario_atual(usuario: UsuarioAtual) -> UsuarioRead:
    """Dados do usuário autenticado."""
    return UsuarioRead.model_validate(usuario)
