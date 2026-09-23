"""Reúne a Base e todos os modelos.

O Alembic importa este módulo no autogenerate — todo modelo novo precisa
aparecer aqui (direta ou indiretamente), senão a tabela não é detectada.
"""

from app.db.base_class import Base
from app.models import (  # noqa: F401
    Cliente,
    ClienteEndereco,
    Endereco,
    Fornecedor,
    Fornecimento,
    ItemVenda,
    Movimentacao,
    Produto,
    Usuario,
    Venda,
)

__all__ = ["Base"]
