"""Regras de negócio de usuário: cadastro e autenticação."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_senha, verificar_senha
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate


class EmailJaCadastradoError(Exception):
    """Já existe um usuário com este e-mail."""


# Hash descartável usado no login de e-mail inexistente, só para gastar o mesmo
# tempo de um bcrypt real. O resultado da comparação é sempre ignorado.
_HASH_DUMMY = "$2b$12$WhwDghRKD8OZW464JKKlP.cumrAT4U9z2ZVvFF8qEJr/F.n5v.bva"


def buscar_por_email(db: Session, email: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.email == email))


def buscar_por_id(db: Session, id_usuario: int) -> Usuario | None:
    return db.get(Usuario, id_usuario)


def criar_usuario(db: Session, dados: UsuarioCreate) -> Usuario:
    """Cadastra um usuário guardando apenas o hash da senha."""
    if buscar_por_email(db, dados.email) is not None:
        raise EmailJaCadastradoError(dados.email)

    usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        endereco=dados.endereco,
        telefone=dados.telefone,
        senha=hash_senha(dados.senha),
    )
    db.add(usuario)
    db.commit()
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
