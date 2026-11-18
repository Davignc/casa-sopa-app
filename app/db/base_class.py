from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Nomes determinísticos de constraints: o Alembic consegue alterá-las/removê-las
# depois, e os nomes batem com os do script SQL de referência. Os CHECKs são
# nomeados explicitamente nos modelos (chk_...), por isso o "ck" usa o nome como veio.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base declarativa compartilhada por todos os modelos.

    Convenção: coleções "pai -> filhos" cujo FK é ON DELETE RESTRICT usam
    ``passive_deletes="all"``, para o ORM não tentar zerar a FK dos filhos e deixar o
    banco recusar a exclusão. Na prática, nada aqui é apagado: usa-se ``is_ativo``.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
