"""Regras de negócio de usuário: cadastro e autenticação."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflitoError
from app.core.security import hash_senha, verificar_senha
from app.core.validators import normalizar_email
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate


class EmailJaCadastradoError(ConflitoError):
    """RN02: já existe um usuário com este e-mail."""

    detail = "Já existe um usuário com este e-mail."


class TelefoneJaCadastradoError(ConflitoError):
    """Já existe um usuário com este telefone."""

    detail = "Já existe um usuário com este telefone."


# Hash descartável usado no login de e-mail inexistente, só para gastar o mesmo
# tempo de um bcrypt real. O resultado da comparação é sempre ignorado.
_HASH_DUMMY = "$2b$12$WhwDghRKD8OZW464JKKlP.cumrAT4U9z2ZVvFF8qEJr/F.n5v.bva"


def buscar_por_email(db: Session, email: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.email == normalizar_email(email)))


def buscar_por_telefone(db: Session, telefone: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.telefone == telefone))


def buscar_por_id(db: Session, id_usuario: int) -> Usuario | None:
    return db.get(Usuario, id_usuario)


def _validar_unicidade(db: Session, email: str, telefone: str) -> None:
    if buscar_por_email(db, email) is not None:
        raise EmailJaCadastradoError
    if buscar_por_telefone(db, telefone) is not None:
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
        verificar_senha(senha, _HASH_DUMMY)
        return None
    if not verificar_senha(senha, usuario.senha):
        return None
    if not usuario.is_ativo:
        return None
    return usuario
