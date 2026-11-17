from typing import Literal

from pydantic import BaseModel, Field

TipoImportacao = Literal["clientes", "produtos", "vendas"]


class ProblemaImportacao(BaseModel):
    linha: int
    mensagem: str


class ResultadoImportacao(BaseModel):
    tipo: TipoImportacao
    total_linhas: int
    novos: int = 0
    ignorados: int = 0
    erros: list[ProblemaImportacao] = Field(default_factory=list)
    amostra: list[dict[str, str]] = Field(default_factory=list)
    token: str | None = None
    concluida: bool = False
