from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession, OperadorAtual
from app.schemas.cliente import EnderecoBusca
from app.services import endereco as endereco_service

router = APIRouter(prefix="/enderecos", tags=["endereços"])


@router.get("", response_model=list[EnderecoBusca])
def buscar_enderecos(
    db: DbSession,
    _op: OperadorAtual,
    busca: Annotated[
        str, Query(min_length=2, max_length=100, description="Rua, bairro, cidade ou CEP")
    ],
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> list[EnderecoBusca]:
    """Procura endereços já registrados (de qualquer cliente) para reaproveitar.

    Depois de escolher um, ligue-o ao cliente com `POST /clientes/{id}/enderecos`
    enviando `id_endereco` + número, complemento e referência.
    """
    return endereco_service.buscar(db, busca, limit)
