"""Compatibilidade com a tabela histórica; a funcionalidade de importação foi removida.

Mantém o mapeamento de bancos já migrados sem excluir registros existentes.
Não há rotas, serviços ou interface de importação.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class VendaImportada(Base):
    __tablename__ = "venda_importada"
    referencia: Mapped[str] = mapped_column(String(100), primary_key=True)
    id_venda: Mapped[int] = mapped_column(ForeignKey("vendas.id_venda"), unique=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario"))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
