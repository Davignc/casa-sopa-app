from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CHAR, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.cliente_endereco import ClienteEndereco


class Endereco(Base):
    """Endereço de entrega, compartilhável entre clientes."""

    __tablename__ = "endereco"

    id_endereco: Mapped[int] = mapped_column(primary_key=True)
    cidade: Mapped[str] = mapped_column(String(50), nullable=False)
    bairro: Mapped[str] = mapped_column(String(50), nullable=False)
    rua: Mapped[str] = mapped_column(String(50), nullable=False)
    logradouro: Mapped[str] = mapped_column(String(50), nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    cep: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    is_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    clientes: Mapped[list[ClienteEndereco]] = relationship(back_populates="endereco")

    def __repr__(self) -> str:
        return f"<Endereco id={self.id_endereco} cep={self.cep!r}>"
