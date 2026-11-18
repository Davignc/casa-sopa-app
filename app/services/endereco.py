"""Busca de endereços já registrados, para reaproveitá-los em outros clientes (RM04)."""

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.formatacao import formatar_cep
from app.models.cliente_endereco import ClienteEndereco
from app.models.endereco import Endereco
from app.schemas.cliente import EnderecoBusca


def _escapar(termo: str) -> str:
    return termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def buscar(db: Session, busca: str, limit: int) -> list[EnderecoBusca]:
    """Cada palavra precisa aparecer na rua, no bairro, na cidade ou no início do CEP."""
    filtros: list[Any] = [Endereco.is_ativo.is_(True)]
    for palavra in busca.split():
        padrao = f"%{_escapar(palavra)}%"
        opcoes = [
            Endereco.nome_logradouro.ilike(padrao, escape="\\"),
            Endereco.tipo_logradouro.ilike(padrao, escape="\\"),
            Endereco.bairro.ilike(padrao, escape="\\"),
            Endereco.cidade.ilike(padrao, escape="\\"),
        ]
        digitos = "".join(c for c in palavra if c.isdigit())
        if len(digitos) >= 3:
            opcoes.append(Endereco.cep.like(f"{digitos}%"))
        filtros.append(or_(*opcoes))

    clientes = (
        select(ClienteEndereco.id_endereco, func.count().label("qtd"))
        .group_by(ClienteEndereco.id_endereco)
        .subquery()
    )
    linhas = db.execute(
        select(Endereco, func.coalesce(clientes.c.qtd, 0))
        .outerjoin(clientes, clientes.c.id_endereco == Endereco.id_endereco)
        .where(*filtros)
        .order_by(Endereco.cidade, Endereco.bairro, Endereco.nome_logradouro, Endereco.id_endereco)
        .limit(limit)
    ).all()
    return [
        EnderecoBusca(
            id_endereco=e.id_endereco,
            cep=e.cep,
            cidade=e.cidade,
            bairro=e.bairro,
            tipo_logradouro=e.tipo_logradouro,
            nome_logradouro=e.nome_logradouro,
            descricao=(
                f"{e.tipo_logradouro} {e.nome_logradouro} - {e.bairro}, {e.cidade} "
                f"- CEP {formatar_cep(e.cep)}"
            ),
            quantidade_clientes=int(qtd),
        )
        for e, qtd in linhas
    ]
