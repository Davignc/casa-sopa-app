from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import DbSession, OperadorAtual
from app.schemas.cliente import (
    ClienteCreate,
    ClienteRead,
    ClienteResumo,
    ClienteUpdate,
    EnderecoDoCliente,
    EnderecoVinculoUpdate,
)
from app.schemas.comum import Pagina
from app.services import cliente as cliente_service

router = APIRouter(prefix="/clientes", tags=["clientes"])

IdCliente = Annotated[int, Path(gt=0)]
IdEndereco = Annotated[int, Path(gt=0)]


@router.post("", response_model=ClienteRead, status_code=status.HTTP_201_CREATED)
def criar_cliente(dados: ClienteCreate, db: DbSession, operador: OperadorAtual) -> ClienteRead:
    """Cadastra cliente com zero ou mais endereços (RF07).

    A usuária responsável é a logada. Telefone repetido retorna 409 (RN07).
    Endereços já existentes no sistema são reaproveitados (RM04).
    """
    return cliente_service.montar_detalhe(cliente_service.criar(db, dados, operador))


@router.get("", response_model=Pagina[ClienteResumo])
def listar_clientes(
    db: DbSession,
    _op: OperadorAtual,
    busca: Annotated[str | None, Query(max_length=100, description="Nome ou telefone")] = None,
    incluir_inativos: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[ClienteResumo]:
    """Nome, telefone e endereço principal de cada cliente (RF10)."""
    itens, total = cliente_service.listar(
        db, busca=busca, incluir_inativos=incluir_inativos, limit=limit, offset=offset
    )
    return Pagina[ClienteResumo](
        itens=[cliente_service.montar_resumo(c) for c in itens],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{id_cliente}", response_model=ClienteRead)
def ler_cliente(id_cliente: IdCliente, db: DbSession, _op: OperadorAtual) -> ClienteRead:
    return cliente_service.montar_detalhe(cliente_service.obter_ou_404(db, id_cliente))


@router.patch("/{id_cliente}", response_model=ClienteRead)
def atualizar_cliente(
    id_cliente: IdCliente, dados: ClienteUpdate, db: DbSession, _op: OperadorAtual
) -> ClienteRead:
    """Altera nome e/ou telefone (RF08). Telefone de outro cliente retorna 409 (RN08)."""
    cliente = cliente_service.obter_ou_404(db, id_cliente)
    return cliente_service.montar_detalhe(cliente_service.atualizar(db, cliente, dados))


@router.delete("/{id_cliente}", status_code=status.HTTP_204_NO_CONTENT)
def inativar_cliente(id_cliente: IdCliente, db: DbSession, _op: OperadorAtual) -> Response:
    """Inativa o cliente (exclusão lógica, RF09). A confirmação é feita pelo front."""
    cliente_service.inativar(db, cliente_service.obter_ou_404(db, id_cliente))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{id_cliente}/reativar", response_model=ClienteRead)
def reativar_cliente(id_cliente: IdCliente, db: DbSession, _op: OperadorAtual) -> ClienteRead:
    cliente = cliente_service.obter_ou_404(db, id_cliente)
    return cliente_service.montar_detalhe(cliente_service.reativar(db, cliente))


@router.post(
    "/{id_cliente}/enderecos", response_model=ClienteRead, status_code=status.HTTP_201_CREATED
)
def adicionar_endereco(
    id_cliente: IdCliente, dados: EnderecoDoCliente, db: DbSession, _op: OperadorAtual
) -> ClienteRead:
    """Inclui um endereço de entrega (RF08). O primeiro endereço vira o principal.

    Envie o endereço completo (novo) **ou** `id_endereco` de um endereço já registrado
    (achado em `GET /enderecos`) com número, complemento e referência do vínculo.
    """
    cliente = cliente_service.obter_ou_404(db, id_cliente)
    return cliente_service.montar_detalhe(cliente_service.adicionar_endereco(db, cliente, dados))


@router.patch("/{id_cliente}/enderecos/{id_endereco}", response_model=ClienteRead)
def atualizar_endereco(
    id_cliente: IdCliente,
    id_endereco: IdEndereco,
    dados: EnderecoVinculoUpdate,
    db: DbSession,
    _op: OperadorAtual,
) -> ClienteRead:
    """Altera apelido, número, complemento, referência ou o principal (RF08).

    Para corrigir rua, bairro, cidade ou CEP: cadastre o endereço novo e remova o antigo.
    """
    cliente = cliente_service.obter_ou_404(db, id_cliente)
    return cliente_service.montar_detalhe(
        cliente_service.atualizar_endereco(db, cliente, id_endereco, dados)
    )


@router.delete("/{id_cliente}/enderecos/{id_endereco}", response_model=ClienteRead)
def remover_endereco(
    id_cliente: IdCliente, id_endereco: IdEndereco, db: DbSession, _op: OperadorAtual
) -> ClienteRead:
    """Remove o endereço do cliente (RF08). Se era o principal, outro assume."""
    cliente = cliente_service.obter_ou_404(db, id_cliente)
    return cliente_service.montar_detalhe(
        cliente_service.remover_endereco(db, cliente, id_endereco)
    )
