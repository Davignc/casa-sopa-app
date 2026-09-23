from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.cliente import Cliente
    from app.models.endereco import Endereco


class ClienteEndereco(Base):
    """Associação N:N entre cliente e endereço, com apelido e marcação de principal."""

    __tablename__ = "cliente_endereco"

    id_cliente: Mapped[int] = mapped_column(
        ForeignKey("cliente.id_cliente", ondelete="CASCADE"), primary_key=True
    )
    id_endereco: Mapped[int] = mapped_column(
        ForeignKey("endereco.id_endereco", ondelete="CASCADE"), primary_key=True
    )
    apelido: Mapped[str] = mapped_column(String(50), nullable=False)
    principal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    cliente: Mapped[Cliente] = relationship(back_populates="enderecos")
    endereco: Mapped[Endereco] = relationship(back_populates="clientes")

    def __repr__(self) -> str:
        return f"<ClienteEndereco cliente={self.id_cliente} endereco={self.id_endereco}>"
