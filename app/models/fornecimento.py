from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.fornecedor import Fornecedor
    from app.models.produto import Produto


class Fornecimento(Base):
    """Entrega de um produto por um fornecedor (entrada de estoque)."""

    __tablename__ = "fornecimento"

    id_produto: Mapped[int] = mapped_column(ForeignKey("produto.id_produto"), primary_key=True)
    id_fornecedor: Mapped[int] = mapped_column(
        ForeignKey("fornecedor.id_fornecedor"), primary_key=True
    )
    preco_custo_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    numero_nota_fiscal: Mapped[int] = mapped_column(Integer, nullable=False)
    data_entrega: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    produto: Mapped[Produto] = relationship(back_populates="fornecimentos")
    fornecedor: Mapped[Fornecedor] = relationship(back_populates="fornecimentos")

    def __repr__(self) -> str:
        return f"<Fornecimento produto={self.id_produto} fornecedor={self.id_fornecedor}>"
