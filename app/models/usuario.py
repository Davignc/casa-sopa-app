from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.cliente import Cliente
    from app.models.venda import Venda

# Cargos reconhecidos pelo sistema (RM07). O banco guarda texto livre (VARCHAR(40),
# como no script de referência); quem valida os valores é a camada de aplicação.
CARGO_ADMINISTRADORA = "administradora"
CARGO_VENDEDORA = "vendedora"
CARGOS = (CARGO_ADMINISTRADORA, CARGO_VENDEDORA)


class Usuario(Base):
    """Administradora ou vendedora que opera o sistema."""

    __tablename__ = "usuario"
    __table_args__ = (
        CheckConstraint(
            "comissao IS NULL OR (comissao >= 0 AND comissao <= 100)",
            name="chk_usuario_comissao",
        ),
    )

    id_usuario: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    # RN02: e-mail único. O telefone também é único (script de referência).
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    telefone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    # Nunca armazena a senha em texto puro: só o hash bcrypt.
    senha: Mapped[str] = mapped_column(String(150), nullable=False)
    cargo: Mapped[str] = mapped_column(String(40), nullable=False)
    # Percentual de comissão (0 a 100); aplicável apenas às vendedoras.
    comissao: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    vendas: Mapped[list[Venda]] = relationship(back_populates="usuario", passive_deletes="all")
    clientes_cadastrados: Mapped[list[Cliente]] = relationship(
        back_populates="usuario", passive_deletes="all"
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.id_usuario} email={self.email!r} cargo={self.cargo!r}>"
