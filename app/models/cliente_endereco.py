from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.cliente import Cliente
    from app.models.endereco import Endereco
    from app.models.venda import Venda


class ClienteEndereco(Base):
    """Entidade associativa N:N entre cliente e endereço (RM04).

    Guarda o que é específico do vínculo: apelido, se é o principal, número,
    complemento e referência. ``complemento`` e ``referencia`` são obrigatórios;
    use string vazia quando não houver.
    """

    __tablename__ = "cliente_endereco"

    id_cliente: Mapped[int] = mapped_column(
        ForeignKey("cliente.id_cliente", onupdate="CASCADE", ondelete="RESTRICT"),
        primary_key=True,
    )
    id_endereco: Mapped[int] = mapped_column(
        ForeignKey("endereco.id_endereco", onupdate="CASCADE", ondelete="RESTRICT"),
        primary_key=True,
    )
    apelido: Mapped[str | None] = mapped_column(String(50), nullable=True)
    principal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    numero: Mapped[str] = mapped_column(String(10), nullable=False)  # aceita "123A" e "S/N"
    complemento: Mapped[str] = mapped_column(String(50), nullable=False)
    referencia: Mapped[str] = mapped_column(String(50), nullable=False)

    cliente: Mapped[Cliente] = relationship(back_populates="enderecos")
    endereco: Mapped[Endereco] = relationship(back_populates="clientes")
    vendas: Mapped[list[Venda]] = relationship(
        back_populates="endereco_entrega",
        foreign_keys="[Venda.id_cliente, Venda.id_endereco]",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<ClienteEndereco cliente={self.id_cliente} endereco={self.id_endereco}>"
