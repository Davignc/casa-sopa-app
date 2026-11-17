from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class VendaImportada(Base):
    """Chave legada única: reenvios e importações simultâneas não duplicam vendas."""

    __tablename__ = "venda_importada"
    referencia: Mapped[str] = mapped_column(String(100), primary_key=True)
    id_venda: Mapped[int] = mapped_column(ForeignKey("vendas.id_venda"), unique=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario"))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
