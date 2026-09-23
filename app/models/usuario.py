from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.venda import Venda


class Usuario(Base):
    """Operador do sistema — quem registra as vendas."""

    __tablename__ = "usuario"

    id_usuario: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    endereco: Mapped[str] = mapped_column(String(255), nullable=False)
    telefone: Mapped[str] = mapped_column(String(20), nullable=False)
    # Nunca armazena a senha em texto puro: só o hash bcrypt.
    senha: Mapped[str] = mapped_column(String(150), nullable=False)
    is_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    vendas: Mapped[list[Venda]] = relationship(back_populates="usuario")

    def __repr__(self) -> str:
        return f"<Usuario id={self.id_usuario} email={self.email!r}>"
