"""Regras de negócio de clientes e seus endereços (RF07-RF10, RN07-RN08)."""

import logging
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflitoError, NaoEncontradoError, RegraInvalidaError
from app.core.formatacao import formatar_endereco
from app.models.cliente import Cliente
from app.models.cliente_endereco import ClienteEndereco
from app.models.endereco import Endereco
from app.models.usuario import Usuario
from app.models.venda import Venda
from app.schemas.cliente import (
    ClienteCreate,
    ClienteRead,
    ClienteResumo,
    ClienteUpdate,
    EnderecoEntrada,
    EnderecoRead,
    EnderecoVinculoUpdate,
    ResponsavelRead,
)

logger = logging.getLogger("casa_sopa.clientes")


class TelefoneDeClienteJaCadastradoError(ConflitoError):
    """RN07/RN08: telefone já pertence a outro cliente."""

    detail = "Já existe um cliente com este telefone."


# --- leitura -----------------------------------------------------------------


def _com_enderecos() -> Any:
    return selectinload(Cliente.enderecos).selectinload(ClienteEndereco.endereco)


def obter_ou_404(db: Session, id_cliente: int) -> Cliente:
    cliente = db.scalar(
        select(Cliente)
        .where(Cliente.id_cliente == id_cliente)
        .options(_com_enderecos(), selectinload(Cliente.usuario))
    )
    if cliente is None:
        raise NaoEncontradoError("Cliente não encontrado.")
    return cliente


def _vinculos_ativos(cliente: Cliente) -> list[ClienteEndereco]:
    ativos = [v for v in cliente.enderecos if v.endereco.is_ativo]
    return sorted(ativos, key=lambda v: v.id_endereco)


def montar_endereco(vinculo: ClienteEndereco) -> EnderecoRead:
    e = vinculo.endereco
    return EnderecoRead(
        id_endereco=e.id_endereco,
        cep=e.cep,
        cidade=e.cidade,
        bairro=e.bairro,
        tipo_logradouro=e.tipo_logradouro,
        nome_logradouro=e.nome_logradouro,
        numero=vinculo.numero,
        complemento=vinculo.complemento,
        referencia=vinculo.referencia,
        apelido=vinculo.apelido,
        principal=vinculo.principal,
        endereco_formatado=formatar_endereco(
            tipo_logradouro=e.tipo_logradouro,
            nome_logradouro=e.nome_logradouro,
            numero=vinculo.numero,
            complemento=vinculo.complemento,
            bairro=e.bairro,
            cidade=e.cidade,
            cep=e.cep,
        ),
    )


def _principal(cliente: Cliente) -> EnderecoRead | None:
    ativos = _vinculos_ativos(cliente)
    escolhido = next((v for v in ativos if v.principal), ativos[0] if ativos else None)
    return montar_endereco(escolhido) if escolhido else None


def montar_resumo(cliente: Cliente) -> ClienteResumo:
    return ClienteResumo(
        id_cliente=cliente.id_cliente,
        nome=cliente.nome,
        telefone=cliente.telefone,
        is_ativo=cliente.is_ativo,
        endereco_principal=_principal(cliente),
    )


def montar_detalhe(cliente: Cliente) -> ClienteRead:
    return ClienteRead(
        **montar_resumo(cliente).model_dump(),
        cadastrado_por=ResponsavelRead.model_validate(cliente.usuario),
        enderecos=[montar_endereco(v) for v in _vinculos_ativos(cliente)],
    )


def listar(
    db: Session, *, busca: str | None, incluir_inativos: bool, limit: int, offset: int
) -> tuple[list[Cliente], int]:
    """Lista paginada (RF10). Por padrão só os ativos: inativado "não aparece mais" (RF09)."""
    filtros: list[Any] = []
    if not incluir_inativos:
        filtros.append(Cliente.is_ativo.is_(True))
    if busca and busca.strip():
        termo = busca.strip()
        escapado = termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        condicoes = [Cliente.nome.ilike(f"%{escapado}%", escape="\\")]
        digitos = "".join(c for c in termo if c.isdigit())
        if digitos:
            condicoes.append(Cliente.telefone.like(f"%{digitos}%"))
        filtros.append(or_(*condicoes))

    total = db.scalar(select(func.count()).select_from(Cliente).where(*filtros)) or 0
    itens = db.scalars(
        select(Cliente)
        .where(*filtros)
        .order_by(Cliente.nome, Cliente.id_cliente)
        .limit(limit)
        .offset(offset)
        .options(_com_enderecos())
    ).all()
    return list(itens), total


# --- cadastro ----------------------------------------------------------------


def _validar_telefone_livre(db: Session, telefone: str, ignorar_id: int | None = None) -> None:
    existente = db.scalar(select(Cliente).where(Cliente.telefone == telefone))
    if existente is not None and existente.id_cliente != ignorar_id:
        if not existente.is_ativo:
            raise TelefoneDeClienteJaCadastradoError(
                "Este telefone pertence a um cliente inativo. Reative o cadastro dele."
            )
        raise TelefoneDeClienteJaCadastradoError


def _buscar_endereco(db: Session, dados: EnderecoEntrada) -> Endereco | None:
    """Procura o endereço físico (mesmo CEP, cidade, bairro e logradouro), sem diferenciar caixa."""
    return db.scalar(
        select(Endereco).where(
            Endereco.cep == dados.cep,
            func.lower(Endereco.cidade) == dados.cidade.lower(),
            func.lower(Endereco.bairro) == dados.bairro.lower(),
            func.lower(Endereco.tipo_logradouro) == dados.tipo_logradouro.lower(),
            func.lower(Endereco.nome_logradouro) == dados.nome_logradouro.lower(),
        )
    )


def _resolver_endereco(db: Session, dados: EnderecoEntrada) -> Endereco:
    """Reaproveita o endereço físico se já existir (RM04); senão cria."""
    existente = _buscar_endereco(db, dados)
    if existente is not None:
        existente.is_ativo = True
        return existente
    novo = Endereco(
        cep=dados.cep,
        cidade=dados.cidade,
        bairro=dados.bairro,
        tipo_logradouro=dados.tipo_logradouro,
        nome_logradouro=dados.nome_logradouro,
    )
    db.add(novo)
    db.flush()
    return novo


def _definir_principal(cliente: Cliente, id_endereco: int) -> None:
    for v in _vinculos_ativos(cliente):
        v.principal = v.id_endereco == id_endereco


def _vincular(db: Session, cliente: Cliente, dados: EnderecoEntrada) -> ClienteEndereco:
    endereco = _resolver_endereco(db, dados)
    vinculo = db.get(ClienteEndereco, (cliente.id_cliente, endereco.id_endereco))
    if vinculo is None:
        vinculo = ClienteEndereco(
            id_cliente=cliente.id_cliente,
            id_endereco=endereco.id_endereco,
            apelido=dados.apelido,
            principal=False,
            numero=dados.numero,
            complemento=dados.complemento,
            referencia=dados.referencia,
        )
        vinculo.endereco = endereco
        db.add(vinculo)
        cliente.enderecos.append(vinculo)
    else:
        # Vínculo antigo (endereço removido antes): reativa com os dados novos.
        vinculo.apelido = dados.apelido
        vinculo.numero = dados.numero
        vinculo.complemento = dados.complemento
        vinculo.referencia = dados.referencia
    return vinculo


def criar(db: Session, dados: ClienteCreate, ator: Usuario) -> Cliente:
    """Cadastra o cliente registrando a usuária responsável (RF07)."""
    _validar_telefone_livre(db, dados.telefone)

    cliente = Cliente(nome=dados.nome, telefone=dados.telefone, id_usuario=ator.id_usuario)
    db.add(cliente)
    db.flush()

    vistos: set[int] = set()
    principal_id: int | None = None
    for entrada in dados.enderecos:
        vinculo = _vincular(db, cliente, entrada)
        if vinculo.id_endereco in vistos:
            db.rollback()
            raise RegraInvalidaError("O mesmo endereço foi informado mais de uma vez.")
        vistos.add(vinculo.id_endereco)
        if entrada.principal:
            principal_id = vinculo.id_endereco
    if principal_id is not None:
        _definir_principal(cliente, principal_id)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _validar_telefone_livre(db, dados.telefone)
        raise
    logger.info("Cliente criado: id=%s por usuario=%s", cliente.id_cliente, ator.id_usuario)
    return obter_ou_404(db, cliente.id_cliente)


def atualizar(db: Session, cliente: Cliente, dados: ClienteUpdate) -> Cliente:
    """Altera nome e/ou telefone (RF08, RN08). Endereços têm rotas próprias."""
    campos = dados.model_dump(exclude_unset=True)
    if "telefone" in campos:
        _validar_telefone_livre(db, campos["telefone"], ignorar_id=cliente.id_cliente)
    for campo, valor in campos.items():
        setattr(cliente, campo, valor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if "telefone" in campos:
            _validar_telefone_livre(db, campos["telefone"], ignorar_id=cliente.id_cliente)
        raise
    return obter_ou_404(db, cliente.id_cliente)


def inativar(db: Session, cliente: Cliente) -> None:
    """Exclusão lógica (RF09): preserva pedidos e histórico."""
    cliente.is_ativo = False
    db.commit()


def reativar(db: Session, cliente: Cliente) -> Cliente:
    cliente.is_ativo = True
    db.commit()
    return obter_ou_404(db, cliente.id_cliente)


# --- endereços do cliente (RF08) ---------------------------------------------


def _vinculo_ativo_ou_404(cliente: Cliente, id_endereco: int) -> ClienteEndereco:
    for v in _vinculos_ativos(cliente):
        if v.id_endereco == id_endereco:
            return v
    raise NaoEncontradoError("Endereço não encontrado para este cliente.")


def adicionar_endereco(db: Session, cliente: Cliente, dados: EnderecoEntrada) -> Cliente:
    endereco_existente = _buscar_endereco(db, dados)
    if endereco_existente is not None and endereco_existente.is_ativo:
        ja_tem = db.get(ClienteEndereco, (cliente.id_cliente, endereco_existente.id_endereco))
        if ja_tem is not None:
            raise ConflitoError("Este endereço já está cadastrado para o cliente.")

    sem_enderecos = not _vinculos_ativos(cliente)
    vinculo = _vincular(db, cliente, dados)
    if dados.principal or sem_enderecos:
        _definir_principal(cliente, vinculo.id_endereco)
    db.commit()
    return obter_ou_404(db, cliente.id_cliente)


def atualizar_endereco(
    db: Session, cliente: Cliente, id_endereco: int, dados: EnderecoVinculoUpdate
) -> Cliente:
    """Altera apelido, número, complemento, referência ou o principal.

    Rua, bairro, cidade e CEP são do endereço físico, que pode ser compartilhado com outros
    clientes: para mudá-los, cadastre o endereço novo e remova o antigo.
    """
    vinculo = _vinculo_ativo_ou_404(cliente, id_endereco)
    campos = dados.model_dump(exclude_unset=True)

    principal = campos.pop("principal", None)
    if principal is False and vinculo.principal:
        raise ConflitoError("Defina outro endereço como principal em vez de remover este.")
    for campo, valor in campos.items():
        setattr(vinculo, campo, valor)
    if principal is True:
        _definir_principal(cliente, id_endereco)
    db.commit()
    return obter_ou_404(db, cliente.id_cliente)


def remover_endereco(db: Session, cliente: Cliente, id_endereco: int) -> Cliente:
    """Remove o endereço do cliente (RF08: "inativar endereços").

    * Nunca usado em pedido: o vínculo é apagado.
    * Usado em pedidos e só deste cliente: o endereço é inativado (histórico preservado).
    * Usado em pedidos e compartilhado com outro cliente: recusa, para não afetar o outro.
    Se era o principal, outro endereço do cliente assume o posto.
    """
    vinculo = _vinculo_ativo_ou_404(cliente, id_endereco)
    era_principal = vinculo.principal

    usado_em_pedidos = (
        db.scalar(
            select(func.count())
            .select_from(Venda)
            .where(Venda.id_cliente == cliente.id_cliente, Venda.id_endereco == id_endereco)
        )
        or 0
    ) > 0
    compartilhado = (
        db.scalar(
            select(func.count())
            .select_from(ClienteEndereco)
            .where(
                ClienteEndereco.id_endereco == id_endereco,
                ClienteEndereco.id_cliente != cliente.id_cliente,
            )
        )
        or 0
    ) > 0

    if not usado_em_pedidos:
        db.delete(vinculo)
        cliente.enderecos.remove(vinculo)
        db.flush()
        if not compartilhado:
            db.delete(vinculo.endereco)  # ninguém mais usa: não deixa lixo no banco
    elif compartilhado:
        raise ConflitoError(
            "Este endereço já foi usado em pedidos e é compartilhado com outro cliente, "
            "por isso não pode ser removido."
        )
    else:
        vinculo.endereco.is_ativo = False
        vinculo.principal = False

    db.flush()
    db.expire(cliente, ["enderecos"])
    restantes = _vinculos_ativos(cliente)
    if era_principal and restantes:
        _definir_principal(cliente, restantes[0].id_endereco)
    db.commit()
    return obter_ou_404(db, cliente.id_cliente)
