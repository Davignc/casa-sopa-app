from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):  # noqa: UP046 - Generic explícito, compatível com FastAPI
    """Resposta paginada padrão das listagens."""

    itens: list[T]
    total: int
    limit: int
    offset: int
