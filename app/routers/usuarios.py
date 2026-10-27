from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import AdminAtual, DbSession, UsuarioAtual
from app.schemas.comum import Pagina
from app.schemas.usuario import Cargo, UsuarioCreate, UsuarioRead, UsuarioUpdate
from app.services import usuario as usuario_service

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

IdUsuario = Annotated[int, Path(gt=0, description="Id do usuário")]


@router.post("", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def criar_usuario(dados: UsuarioCreate, db: DbSession, _admin: AdminAtual) -> UsuarioRead:
    """Cadastra um novo usuário. Somente a administradora (RF03, RN03).

    A senha é gravada apenas como hash bcrypt.
    """
    usuario = usuario_service.criar_usuario(db, dados)
    return UsuarioRead.model_validate(usuario)


@router.get("", response_model=Pagina[UsuarioRead])
def listar_usuarios(
    db: DbSession,
    _admin: AdminAtual,
    busca: Annotated[str | None, Query(max_length=100, description="Nome ou e-mail")] = None,
    cargo: Cargo | None = None,
    is_ativo: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[UsuarioRead]:
    """Lista os usuários, ativos e inativos. Somente a administradora (RF06, RN06)."""
    itens, total = usuario_service.listar(
        db, busca=busca, cargo=cargo, is_ativo=is_ativo, limit=limit, offset=offset
    )
    return Pagina[UsuarioRead](
        itens=[UsuarioRead.model_validate(u) for u in itens],
        total=total,
        limit=limit,
        offset=offset,
    )


# Atenção: "/me" precisa vir antes de "/{id_usuario}", senão "me" seria lido como id.
@router.get("/me", response_model=UsuarioRead)
def ler_usuario_atual(usuario: UsuarioAtual) -> UsuarioRead:
    """Dados do usuário autenticado."""
    return UsuarioRead.model_validate(usuario)


@router.get("/{id_usuario}", response_model=UsuarioRead)
def ler_usuario(id_usuario: IdUsuario, db: DbSession, _admin: AdminAtual) -> UsuarioRead:
    """Detalhe de um usuário. Somente a administradora."""
    return UsuarioRead.model_validate(usuario_service.obter_ou_404(db, id_usuario))


@router.patch("/{id_usuario}", response_model=UsuarioRead)
def atualizar_usuario(
    id_usuario: IdUsuario, dados: UsuarioUpdate, db: DbSession, admin: AdminAtual
) -> UsuarioRead:
    """Altera dados do usuário; só os campos enviados mudam (RF04, RN04).

    Trocar a senha encerra as sessões abertas daquele usuário.
    """
    alvo = usuario_service.obter_ou_404(db, id_usuario)
    return UsuarioRead.model_validate(usuario_service.atualizar(db, alvo, dados, admin))


@router.delete("/{id_usuario}", status_code=status.HTTP_204_NO_CONTENT)
def inativar_usuario(id_usuario: IdUsuario, db: DbSession, admin: AdminAtual) -> Response:
    """Inativa o usuário (exclusão lógica, RF05/RN05): ele não consegue mais entrar.

    A confirmação ("tem certeza?") é feita pelo front antes de chamar este endpoint.
    """
    alvo = usuario_service.obter_ou_404(db, id_usuario)
    usuario_service.inativar(db, alvo, admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{id_usuario}/reativar", response_model=UsuarioRead)
def reativar_usuario(id_usuario: IdUsuario, db: DbSession, _admin: AdminAtual) -> UsuarioRead:
    """Reativa um usuário inativado."""
    alvo = usuario_service.obter_ou_404(db, id_usuario)
    return UsuarioRead.model_validate(usuario_service.reativar(db, alvo))
