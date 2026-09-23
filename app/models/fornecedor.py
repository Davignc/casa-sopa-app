from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.fornecimento import Fornecimento


class Fornecedor(Base):
    """Quem fornece os sacos de lixo à ONG."""

    __tablename__ = "fornecedor"

    id_fornecedor: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(50), nullable=False)
    telefone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    observacao: Mapped[str] = mapped_column(String(255), nullable=False)
    is_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    fornecimentos: Mapped[list[Fornecimento]] = relationship(back_populates="fornecedor")

    def __repr__(self) -> str:
        return f"<Fornecedor id={self.id_fornecedor} nome={self.nome!r}>"
