from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.cliente import Cliente
    from app.models.item_venda import ItemVenda
    from app.models.usuario import Usuario


class Venda(Base):
    """Venda registrada por um usuário para um cliente."""

    __tablename__ = "vendas"

    id_venda: Mapped[int] = mapped_column(primary_key=True)
    data_venda: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    forma_pagamento: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    observacao: Mapped[str] = mapped_column(String(255), nullable=False)
    data_pagamento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canal_envio: Mapped[str] = mapped_column(String(30), nullable=False)

    id_cliente: Mapped[int] = mapped_column(ForeignKey("cliente.id_cliente"), nullable=False)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario"), nullable=False)

    cliente: Mapped[Cliente] = relationship(back_populates="vendas")
    usuario: Mapped[Usuario] = relationship(back_populates="vendas")
    itens: Mapped[list[ItemVenda]] = relationship(back_populates="venda")

    def __repr__(self) -> str:
        return f"<Venda id={self.id_venda} total={self.valor_total}>"
