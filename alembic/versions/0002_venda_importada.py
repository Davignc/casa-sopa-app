"""Rastreia referências de vendas antigas para impedir duplicação."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "venda_importada",
        sa.Column("referencia", sa.String(100), primary_key=True),
        sa.Column(
            "id_venda", sa.Integer(), sa.ForeignKey("vendas.id_venda"), nullable=False, unique=True
        ),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuario.id_usuario"), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("venda_importada")
