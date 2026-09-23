from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.produto import Produto


class Movimentacao(Base):
    """Entrada ou saída de estoque de um produto."""

    __tablename__ = "movimentacoes"

    id_movimentacao: Mapped[int] = mapped_column(primary_key=True)
    tipo_movimentacao: Mapped[str] = mapped_column(String(20), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    # Origem da movimentação: 'venda', 'compra', 'ajuste manual'.
    tipo_referencia: Mapped[str] = mapped_column(String(20), nullable=False)
    data_movimentacao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    id_produto: Mapped[int] = mapped_column(ForeignKey("produto.id_produto"), nullable=False)

    produto: Mapped[Produto] = relationship(back_populates="movimentacoes")

    def __repr__(self) -> str:
        return f"<Movimentacao id={self.id_movimentacao} tipo={self.tipo_movimentacao!r}>"
