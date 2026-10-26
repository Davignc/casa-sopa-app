from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.cliente import Cliente
    from app.models.cliente_endereco import ClienteEndereco
    from app.models.item_venda import ItemVenda
    from app.models.movimentacao import Movimentacao
    from app.models.usuario import Usuario


class Venda(Base):
    """Pedido de um cliente, registrado por uma vendedora (RN09).

    * ``id_usuario`` é a vendedora responsável e não pode ser trocada (RN10 —
      garantido na camada de serviço).
    * ``(id_cliente, id_endereco)`` referencia ``cliente_endereco``, o que obriga
      o endereço de entrega a pertencer ao cliente da venda (RM05).
    * ``data_pagamento`` fica NULL enquanto a venda não for paga.
    """

    __tablename__ = "vendas"
    __table_args__ = (
        ForeignKeyConstraint(
            ["id_cliente", "id_endereco"],
            ["cliente_endereco.id_cliente", "cliente_endereco.id_endereco"],
            name="fk_vendas_cliente_endereco",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status <> 'pago' OR data_pagamento IS NOT NULL",
            name="chk_vendas_pagamento",
        ),
        CheckConstraint("valor_total >= 0", name="chk_vendas_valor"),
        Index("idx_vendas_status_data", "status", "data_venda"),
    )

    id_venda: Mapped[int] = mapped_column(primary_key=True)
    data_venda: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    forma_pagamento: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    observacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_cliente: Mapped[int] = mapped_column(
        ForeignKey("cliente.id_cliente", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    data_pagamento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    id_endereco: Mapped[int] = mapped_column(nullable=False)

    cliente: Mapped[Cliente] = relationship(back_populates="vendas", foreign_keys=[id_cliente])
    usuario: Mapped[Usuario] = relationship(back_populates="vendas")
    # Somente leitura: para trocar o endereço, altere ``id_endereco``.
    endereco_entrega: Mapped[ClienteEndereco] = relationship(
        back_populates="vendas",
        foreign_keys=[id_cliente, id_endereco],
        viewonly=True,
    )
    itens: Mapped[list[ItemVenda]] = relationship(
        back_populates="venda", cascade="all, delete-orphan", passive_deletes=True
    )
    movimentacoes: Mapped[list[Movimentacao]] = relationship(
        back_populates="venda", passive_deletes="all"
    )

    def __repr__(self) -> str:
        return f"<Venda id={self.id_venda} status={self.status!r} total={self.valor_total}>"
