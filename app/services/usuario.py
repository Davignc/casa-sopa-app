"""Regras de negócio de usuário: cadastro e autenticação."""

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflitoError, NaoEncontradoError, RegraInvalidaError
from app.core.security import HASH_FALSO, hash_senha, verificar_senha
from app.core.validators import normalizar_email
from app.models.usuario import CARGO_VENDEDORA, Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate


class EmailJaCadastradoError(ConflitoError):
    """RN02: já existe um usuário com este e-mail."""

    detail = "Já existe um usuário com este e-mail."


class TelefoneJaCadastradoError(ConflitoError):
    """Já existe um usuário com este telefone."""

    detail = "Já existe um usuário com este telefone."


def buscar_por_email(db: Session, email: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.email == normalizar_email(email)))


def buscar_por_telefone(db: Session, telefone: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.telefone == telefone))


def buscar_por_id(db: Session, id_usuario: int) -> Usuario | None:
    return db.get(Usuario, id_usuario)


def obter_ou_404(db: Session, id_usuario: int) -> Usuario:
    usuario = buscar_por_id(db, id_usuario)
    if usuario is None:
        raise NaoEncontradoError("Usuário não encontrado.")
    return usuario


def _validar_unicidade(
    db: Session, email: str | None, telefone: str | None, ignorar_id: int | None = None
) -> None:
    """RN02 e telefone único. ``ignorar_id`` evita conflito do usuário consigo mesmo."""
    if email is not None:
        existente = buscar_por_email(db, email)
        if existente is not None and existente.id_usuario != ignorar_id:
            raise EmailJaCadastradoError
    if telefone is not None:
        existente = buscar_por_telefone(db, telefone)
        if existente is not None and existente.id_usuario != ignorar_id:
            raise TelefoneJaCadastradoError


def criar_usuario(db: Session, dados: UsuarioCreate) -> Usuario:
    """Cadastra um usuário guardando apenas o hash da senha (RN02, RF03)."""
    _validar_unicidade(db, dados.email, dados.telefone)

    usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        telefone=dados.telefone,
        cargo=dados.cargo,
        comissao=dados.comissao,
        senha=hash_senha(dados.senha),
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        # Corrida: outro request gravou o mesmo e-mail/telefone entre a checagem e o commit.
        db.rollback()
        _validar_unicidade(db, dados.email, dados.telefone)
        raise
    db.refresh(usuario)
    return usuario


def autenticar(db: Session, email: str, senha: str) -> Usuario | None:
    """Devolve o usuário se e-mail e senha conferirem e a conta estiver ativa."""
    usuario = buscar_por_email(db, email)
    if usuario is None:
        # Gasta o mesmo tempo de um bcrypt real para não vazar, pelo tempo de
        # resposta, se o e-mail existe ou não.
        verificar_senha(senha, HASH_FALSO)
        return None
    if not verificar_senha(senha, usuario.senha):
        return None
    if not usuario.is_ativo:
        return None
    return usuario


def _escapar_like(termo: str) -> str:
    return termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def listar(
    db: Session,
    *,
    busca: str | None,
    cargo: str | None,
    is_ativo: bool | None,
    limit: int,
    offset: int,
) -> tuple[list[Usuario], int]:
    """Lista paginada (RF06), com filtros opcionais. Devolve (itens, total)."""
    filtros: list[Any] = []
    if busca and busca.strip():
        padrao = f"%{_escapar_like(busca.strip())}%"
        filtros.append(
            or_(Usuario.nome.ilike(padrao, escape="\\"), Usuario.email.ilike(padrao, escape="\\"))
        )
    if cargo is not None:
        filtros.append(Usuario.cargo == cargo)
    if is_ativo is not None:
        filtros.append(Usuario.is_ativo == is_ativo)

    total = db.scalar(select(func.count()).select_from(Usuario).where(*filtros)) or 0
    itens = db.scalars(
        select(Usuario)
        .where(*filtros)
        .order_by(Usuario.nome, Usuario.id_usuario)
        .limit(limit)
        .offset(offset)
    ).all()
    return list(itens), total


def atualizar(db: Session, alvo: Usuario, dados: UsuarioUpdate, ator: Usuario) -> Usuario:
    """Altera os campos enviados (RF04).

    Regras: e-mail/telefone únicos (excluindo o próprio usuário); a administradora não
    altera o próprio cargo; comissão só para vendedora (ao virar administradora a
    comissão é zerada); trocar a senha invalida as sessões abertas do usuário.
    """
    campos = dados.model_dump(exclude_unset=True)

    if "cargo" in campos and campos["cargo"] != alvo.cargo and alvo.id_usuario == ator.id_usuario:
        raise ConflitoError("Você não pode alterar o seu próprio cargo.")

    cargo_final = campos.get("cargo", alvo.cargo)
    if cargo_final != CARGO_VENDEDORA:
        if campos.get("comissao") is not None:
            raise RegraInvalidaError("A comissão só se aplica a usuárias com cargo de vendedora.")
        if "cargo" in campos and "comissao" not in campos:
            campos["comissao"] = None

    novo_email = campos.get("email")
    novo_telefone = campos.get("telefone")
    _validar_unicidade(db, novo_email, novo_telefone, ignorar_id=alvo.id_usuario)

    senha = campos.pop("senha", None)
    if senha is not None:
        alvo.senha = hash_senha(senha)
    for campo, valor in campos.items():
        setattr(alvo, campo, valor)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _validar_unicidade(db, novo_email, novo_telefone, ignorar_id=alvo.id_usuario)
        raise
    db.refresh(alvo)
    return alvo


def inativar(db: Session, alvo: Usuario, ator: Usuario) -> None:
    """Exclusão lógica (RF05): preserva o histórico e impede novos logins."""
    if alvo.id_usuario == ator.id_usuario:
        raise ConflitoError("Você não pode inativar a própria conta.")
    alvo.is_ativo = False
    db.commit()


def reativar(db: Session, alvo: Usuario) -> Usuario:
    alvo.is_ativo = True
    db.commit()
    db.refresh(alvo)
    return alvo
