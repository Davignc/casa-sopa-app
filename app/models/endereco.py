from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CHAR, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.cliente_endereco import ClienteEndereco


class Endereco(Base):
    """Local físico, que pode ser compartilhado entre clientes (RM04).

    Número, complemento e referência ficam em ``ClienteEndereco``.
    """

    __tablename__ = "endereco"

    id_endereco: Mapped[int] = mapped_column(primary_key=True)
    cidade: Mapped[str] = mapped_column(String(50), nullable=False)
    bairro: Mapped[str] = mapped_column(String(50), nullable=False)
    nome_logradouro: Mapped[str] = mapped_column(String(100), nullable=False)  # "Presidente Vargas"
    tipo_logradouro: Mapped[str] = mapped_column(String(20), nullable=False)  # "Avenida"
    cep: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    is_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    clientes: Mapped[list[ClienteEndereco]] = relationship(
        back_populates="endereco", passive_deletes="all"
    )

    def __repr__(self) -> str:
        return f"<Endereco id={self.id_endereco} cep={self.cep!r}>"
