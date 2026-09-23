from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.cliente_endereco import ClienteEndereco
    from app.models.venda import Venda


class Cliente(Base):
    """Comprador dos sacos de lixo."""

    __tablename__ = "cliente"

    id_cliente: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    telefone: Mapped[str] = mapped_column(String(20), nullable=False)
    is_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    vendas: Mapped[list[Venda]] = relationship(back_populates="cliente")
    enderecos: Mapped[list[ClienteEndereco]] = relationship(back_populates="cliente")

    def __repr__(self) -> str:
        return f"<Cliente id={self.id_cliente} nome={self.nome!r}>"
