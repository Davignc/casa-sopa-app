from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.produto import Produto
    from app.models.venda import Venda


class ItemVenda(Base):
    """Linha de uma venda: qual produto, quantos e por quanto."""

    __tablename__ = "item_vendas"

    id_venda: Mapped[int] = mapped_column(
        ForeignKey("vendas.id_venda", ondelete="CASCADE"), primary_key=True
    )
    id_produto: Mapped[int] = mapped_column(ForeignKey("produto.id_produto"), primary_key=True)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    venda: Mapped[Venda] = relationship(back_populates="itens")
    produto: Mapped[Produto] = relationship(back_populates="itens_venda")

    def __repr__(self) -> str:
        return f"<ItemVenda venda={self.id_venda} produto={self.id_produto}>"
