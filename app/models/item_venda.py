from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.produto import Produto
    from app.models.venda import Venda


class ItemVenda(Base):
    """Linha do pedido (RM01). Um produto aparece no máximo uma vez por venda.

    ``preco_unitario_v`` guarda o preço praticado na venda, que não muda quando o
    preço de cadastro do produto é reajustado.
    """

    __tablename__ = "item_vendas"
    __table_args__ = (
        CheckConstraint(
            "quantidade > 0 AND preco_unitario_v >= 0 AND subtotal >= 0",
            name="chk_iv_valores",
        ),
        CheckConstraint(
            "subtotal = ROUND(preco_unitario_v * quantidade, 2)",
            name="chk_iv_subtotal",
        ),
    )

    id_venda: Mapped[int] = mapped_column(
        ForeignKey("vendas.id_venda", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
    )
    id_produto: Mapped[int] = mapped_column(
        ForeignKey("produto.id_produto", onupdate="CASCADE", ondelete="RESTRICT"),
        primary_key=True,
    )
    preco_unitario_v: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    venda: Mapped[Venda] = relationship(back_populates="itens")
    produto: Mapped[Produto] = relationship(back_populates="itens_venda")

    def __repr__(self) -> str:
        return f"<ItemVenda venda={self.id_venda} produto={self.id_produto}>"
