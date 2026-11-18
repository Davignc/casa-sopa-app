from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.cliente_endereco import ClienteEndereco
    from app.models.usuario import Usuario
    from app.models.venda import Venda


class Cliente(Base):
    """Pessoa que realiza pedidos, cadastrada por uma usuária (RM08)."""

    __tablename__ = "cliente"
    __table_args__ = (Index("idx_cliente_nome", "nome"),)

    id_cliente: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    is_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # RN07 e RN08: telefone único.
    telefone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )

    usuario: Mapped[Usuario] = relationship(back_populates="clientes_cadastrados")
    vendas: Mapped[list[Venda]] = relationship(back_populates="cliente", passive_deletes="all")
    enderecos: Mapped[list[ClienteEndereco]] = relationship(
        back_populates="cliente", passive_deletes="all"
    )

    def __repr__(self) -> str:
        return f"<Cliente id={self.id_cliente} nome={self.nome!r}>"
