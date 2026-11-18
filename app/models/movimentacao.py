from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.produto import Produto
    from app.models.venda import Venda

TIPO_ENTRADA = "entrada"
TIPO_SAIDA = "saida"
REF_VENDA = "venda"
REF_COMPRA = "compra"
REF_AJUSTE_MANUAL = "ajuste_manual"


def _agora() -> datetime:
    return datetime.now(UTC)


class Movimentacao(Base):
    """Histórico de entradas e saídas de estoque (RM02 e RM03).

    ``id_venda`` só é preenchido quando a origem é uma venda.
    """

    __tablename__ = "movimentacoes"
    __table_args__ = (
        CheckConstraint("quantidade > 0", name="chk_mov_quantidade"),
        CheckConstraint("tipo_movimentacao IN ('entrada', 'saida')", name="chk_mov_tipo"),
        CheckConstraint(
            "tipo_referencia IN ('venda', 'compra', 'ajuste_manual')",
            name="chk_mov_referencia",
        ),
        CheckConstraint(
            "(tipo_referencia = 'venda' AND id_venda IS NOT NULL)"
            " OR (tipo_referencia <> 'venda' AND id_venda IS NULL)",
            name="chk_mov_venda_origem",
        ),
        Index("idx_mov_produto_data", "id_produto", "data_movimentacao"),
    )

    id_movimentacao: Mapped[int] = mapped_column(primary_key=True)
    tipo_movimentacao: Mapped[str] = mapped_column(String(20), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_referencia: Mapped[str] = mapped_column(String(40), nullable=False)
    data_movimentacao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_agora
    )
    observacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_venda: Mapped[int | None] = mapped_column(
        ForeignKey("vendas.id_venda", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=True,
    )
    id_produto: Mapped[int] = mapped_column(
        ForeignKey("produto.id_produto", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )

    produto: Mapped[Produto] = relationship(back_populates="movimentacoes")
    venda: Mapped[Venda | None] = relationship(back_populates="movimentacoes")

    def __repr__(self) -> str:
        return f"<Movimentacao id={self.id_movimentacao} tipo={self.tipo_movimentacao!r}>"
