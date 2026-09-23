from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.fornecimento import Fornecimento
    from app.models.item_venda import ItemVenda
    from app.models.movimentacao import Movimentacao


class Produto(Base):
    """Item vendido pela ONG (os sacos de lixo, em suas variações)."""

    __tablename__ = "produto"

    id_produto: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    codigo: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    estoque_atual: Mapped[int] = mapped_column(Integer, nullable=False)
    estoque_minimo: Mapped[int] = mapped_column(Integer, nullable=False)
    is_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    fornecimentos: Mapped[list[Fornecimento]] = relationship(back_populates="produto")
    itens_venda: Mapped[list[ItemVenda]] = relationship(back_populates="produto")
    movimentacoes: Mapped[list[Movimentacao]] = relationship(back_populates="produto")

    def __repr__(self) -> str:
        return f"<Produto id={self.id_produto} codigo={self.codigo!r}>"
