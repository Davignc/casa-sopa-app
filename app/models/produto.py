from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.item_venda import ItemVenda
    from app.models.movimentacao import Movimentacao


class Produto(Base):
    """Item comercializado e controlado em estoque."""

    __tablename__ = "produto"
    __table_args__ = (
        CheckConstraint(
            "preco_unitario >= 0 AND estoque_atual >= 0 AND estoque_minimo >= 0",
            name="chk_produto_valores",
        ),
    )

    id_produto: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    estoque_atual: Mapped[int] = mapped_column(Integer, nullable=False)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # Base do alerta de estoque baixo (RN14).
    estoque_minimo: Mapped[int] = mapped_column(Integer, nullable=False)

    itens_venda: Mapped[list[ItemVenda]] = relationship(
        back_populates="produto", passive_deletes="all"
    )
    movimentacoes: Mapped[list[Movimentacao]] = relationship(
        back_populates="produto", passive_deletes="all"
    )

    @property
    def estoque_baixo(self) -> bool:
        """RN14: a quantidade disponível atingiu (ou ficou abaixo de) o mínimo."""
        return self.estoque_atual <= self.estoque_minimo

    def __repr__(self) -> str:
        return f"<Produto id={self.id_produto} nome={self.nome!r}>"
