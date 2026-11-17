"""Importação atômica com prévia, limites de arquivo e proteção contra reenvios."""

import csv
import hashlib
import io
import unicodedata
import zipfile
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

import jwt
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ErroDeNegocio, RegraInvalidaError
from app.core.tempo import hoje_local, inicio_do_dia_utc
from app.core.validators import normalizar_email, normalizar_telefone
from app.models import Cliente, ItemVenda, Produto, Usuario, Venda, VendaImportada
from app.models.movimentacao import REF_AJUSTE_MANUAL, TIPO_ENTRADA
from app.schemas.cliente import ClienteCreate, EnderecoEntrada
from app.schemas.importacao import ProblemaImportacao, ResultadoImportacao, TipoImportacao
from app.schemas.pedido import normalizar_forma_pagamento
from app.schemas.produto import ProdutoCreate
from app.services import cliente as clientes
from app.services import estoque

LIMITE_BYTES = 5 * 1024 * 1024
LIMITE_LINHAS = 2000
COLUNAS = {
    "clientes": [
        "nome",
        "telefone",
        "cep",
        "cidade",
        "bairro",
        "tipo_logradouro",
        "nome_logradouro",
        "numero",
        "complemento",
        "referencia",
    ],
    "produtos": ["nome", "descricao", "preco_unitario", "estoque_inicial", "estoque_minimo"],
    "vendas": [
        "pedido_origem",
        "data_venda",
        "cliente_telefone",
        "responsavel_email",
        "produto",
        "quantidade",
        "preco_unitario",
        "forma_pagamento",
        "status",
        "data_pagamento",
        "observacao",
    ],
}
OBRIGATORIAS = {
    "clientes": {"nome", "telefone"},
    "produtos": {"nome", "descricao", "preco_unitario", "estoque_minimo"},
    "vendas": {
        "pedido_origem",
        "data_venda",
        "cliente_telefone",
        "produto",
        "quantidade",
        "preco_unitario",
        "forma_pagamento",
        "status",
    },
}


def _cabecalho(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or "").strip().lower())
    return "".join(c for c in texto if not unicodedata.combining(c)).replace(" ", "_")


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    return str(valor).strip()


def _decimal(valor: str) -> Decimal:
    texto = valor.replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    numero = Decimal(texto)
    if not numero.is_finite():
        raise ValueError("Informe um número finito.")
    return numero


def _data(valor: str) -> date:
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor, formato).date()
        except ValueError:
            pass
    raise ValueError("Data inválida: use DD/MM/AAAA ou AAAA-MM-DD.")


class LinhaVenda(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pedido_origem: str = Field(min_length=1, max_length=100)
    data_venda: date
    cliente_telefone: str
    responsavel_email: str = ""
    produto: str = Field(min_length=1, max_length=150)
    quantidade: int = Field(ge=1, le=100000)
    preco_unitario: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    forma_pagamento: str
    status: Literal["entregue", "cancelado"]
    data_pagamento: date | None = None
    observacao: str = Field(default="", max_length=100)

    @field_validator("cliente_telefone")
    @classmethod
    def telefone_valido(cls, valor: str) -> str:
        return normalizar_telefone(valor)

    @field_validator("forma_pagamento")
    @classmethod
    def pagamento_valido(cls, valor: str) -> str:
        return normalizar_forma_pagamento(valor)


def ler(conteudo: bytes, nome: str, tipo: TipoImportacao) -> list[tuple[int, dict[str, str]]]:
    if not conteudo or len(conteudo) > LIMITE_BYTES:
        raise RegraInvalidaError("Envie uma planilha não vazia de até 5 MB.")
    linhas: list[list[Any]] = []
    if nome.lower().endswith(".xlsx"):
        try:
            with zipfile.ZipFile(io.BytesIO(conteudo)) as arquivo:
                if sum(i.file_size for i in arquivo.infolist()) > 20 * 1024 * 1024:
                    raise RegraInvalidaError("Planilha descompactada grande demais (máximo 20 MB).")
            wb = load_workbook(
                io.BytesIO(conteudo), read_only=True, data_only=False, keep_links=False
            )
            try:
                ws = wb[tipo] if tipo in wb.sheetnames else wb.worksheets[0]
                for numero, linha in enumerate(ws.iter_rows()):
                    if numero > LIMITE_LINHAS:
                        raise RegraInvalidaError("Limite de 2.000 linhas por importação.")
                    if len(linha) > 30:
                        raise RegraInvalidaError("A planilha tem colunas demais. Use o modelo.")
                    if any(c.data_type == "f" for c in linha):
                        raise RegraInvalidaError(
                            f"Linha {numero + 1}: substitua fórmulas por valores."
                        )
                    linhas.append([c.value for c in linha])
            finally:
                wb.close()
        except RegraInvalidaError:
            raise
        except Exception as exc:
            raise RegraInvalidaError("Arquivo Excel inválido. Envie um .xlsx sem senha.") from exc
    elif nome.lower().endswith(".csv"):
        try:
            try:
                texto = conteudo.decode("utf-8-sig")
            except UnicodeDecodeError:
                texto = conteudo.decode("cp1252")
            separador = ";" if ";" in texto.splitlines()[0] else ","
            for linha in csv.reader(io.StringIO(texto), delimiter=separador):
                if len(linhas) > LIMITE_LINHAS:
                    raise RegraInvalidaError("Limite de 2.000 linhas por importação.")
                if len(linha) > 30:
                    raise RegraInvalidaError("Use no máximo 30 colunas.")
                linhas.append(linha)
        except (UnicodeError, csv.Error, IndexError) as exc:
            raise RegraInvalidaError(
                "CSV inválido. Use UTF-8 e separador ponto e vírgula."
            ) from exc
    else:
        raise RegraInvalidaError("Use um arquivo Excel (.xlsx) ou CSV (.csv).")
    if not linhas:
        raise RegraInvalidaError("O arquivo está vazio.")
    cabecalhos = [_cabecalho(v) for v in linhas[0]]
    while cabecalhos and not cabecalhos[-1]:
        cabecalhos.pop()
    if len(set(cabecalhos)) != len(cabecalhos) or "" in cabecalhos:
        raise RegraInvalidaError("Há cabeçalhos vazios ou repetidos.")
    faltantes = OBRIGATORIAS[tipo] - set(cabecalhos)
    extras = set(cabecalhos) - set(COLUNAS[tipo])
    if faltantes or extras:
        raise RegraInvalidaError(
            "Confira as colunas do modelo. "
            f"Faltantes: {', '.join(sorted(faltantes)) or 'nenhuma'}. "
            f"Não reconhecidas: {', '.join(sorted(extras)) or 'nenhuma'}."
        )
    resultado = []
    for numero, valores in enumerate(linhas[1:], 2):
        if not any(_texto(v) for v in valores):
            continue
        if any(_texto(v) for v in valores[len(cabecalhos) :]):
            raise RegraInvalidaError(f"Linha {numero}: há valores sem cabeçalho.")
        dados = {
            c: _texto(valores[i]) if i < len(valores) else "" for i, c in enumerate(cabecalhos)
        }
        if any(len(v) > 1000 for v in dados.values()):
            raise RegraInvalidaError(f"Linha {numero}: campo longo demais.")
        resultado.append((numero, dados))
    if not resultado:
        raise RegraInvalidaError("Preencha ao menos uma linha depois do cabeçalho.")
    return resultado


def modelo(tipo: TipoImportacao) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = tipo
    ws.append(COLUNAS[tipo])
    ws.freeze_panes = "A2"
    for cell in ws[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="581C87")
        ws.column_dimensions[cell.column_letter].width = 24
    # Mantém zeros de CEP/telefone e referências textuais no Excel.
    for linha in ws.iter_rows(min_row=2, max_row=101, max_col=len(COLUNAS[tipo])):
        for cell in linha:
            cell.number_format = "@"
    guia = wb.create_sheet("Instruções")
    instrucoes = [
        "Preencha a primeira aba. Os nomes das colunas devem permanecer iguais.",
        "Importe na ordem: clientes, produtos e vendas. Máximo 2.000 linhas / 5 MB.",
        "Clientes: nome e telefone com DDD são obrigatórios. Endereço é opcional; se informado, "
        "preencha CEP, cidade, bairro, tipo_logradouro, nome_logradouro e numero.",
        "Produtos: estoque_inicial representa a contagem ATUAL, já descontadas as vendas antigas. "
        "estoque_minimo é obrigatório.",
        "Vendas: uma linha por produto. Repita pedido_origem e os dados do pedido para vários "
        "itens da mesma venda. Máximo 100 produtos por pedido.",
        "pedido_origem deve ser único em todo o acervo (ex.: CADERNO-2024-001). "
        "Reenvios com a mesma referência são ignorados.",
        "Vendas: cliente_telefone identifica cliente já cadastrado com endereço principal. "
        "produto é o nome exato do produto já cadastrado, sem nomes ambíguos.",
        "responsavel_email é o e-mail de usuário já cadastrado; "
        "vazio = administradora que importa. "
        "Usuários inativos podem constar no histórico.",
        "Datas: DD/MM/AAAA ou AAAA-MM-DD. Vendas históricas: status entregue ou cancelado. "
        "Não alteram o estoque atual.",
        "Preços: 12,50 ou 12.50. data_pagamento é opcional; só preencha se souber que foi pago. "
        "observacao é opcional, até 100 caracteres.",
        "Clientes com telefone existente e produtos com nome existente são ignorados. "
        "Nenhum cadastro existente é sobrescrito.",
        "Vendas entregues entram nos relatórios e nas comissões com o percentual ATUAL "
        "da responsável, conforme a regra do sistema.",
        "Planilhas antigas precisam ter suas colunas adaptadas ao modelo. "
        "O Excel de relatórios é um resumo, não um backup importável.",
        "Remova fórmulas, células mescladas e totais. Revise a prévia. "
        "Se houver erros, nada será salvo.",
    ]
    for texto in instrucoes:
        guia.append([texto])
    guia.column_dimensions["A"].width = 125
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _cliente(db: Session, dados: dict[str, str], ator: Usuario) -> bool:
    endereco = {c: dados.get(c, "") for c in COLUNAS["clientes"][2:]}
    entrada = ClienteCreate(
        nome=dados["nome"],
        telefone=dados["telefone"],
        enderecos=[EnderecoEntrada(**endereco)] if any(endereco.values()) else [],
    )
    if db.scalar(select(Cliente).where(Cliente.telefone == entrada.telefone)):
        return False
    cliente = Cliente(nome=entrada.nome, telefone=entrada.telefone, id_usuario=ator.id_usuario)
    db.add(cliente)
    db.flush()
    for e in entrada.enderecos:
        vinculo = clientes._vincular(db, cliente, e)
        vinculo.principal = True
    return True


def _produto(db: Session, dados: dict[str, str], ator: Usuario) -> bool:
    entrada = ProdutoCreate(
        **{
            **dados,
            "preco_unitario": _decimal(dados["preco_unitario"]),
            "estoque_inicial": dados.get("estoque_inicial") or 0,
        }
    )
    if db.scalar(select(Produto).where(func.lower(Produto.nome) == entrada.nome.lower())):
        return False
    produto = Produto(
        nome=entrada.nome,
        descricao=entrada.descricao,
        preco_unitario=entrada.preco_unitario,
        estoque_atual=0,
        estoque_minimo=entrada.estoque_minimo,
    )
    db.add(produto)
    db.flush()
    if entrada.estoque_inicial:
        estoque.movimentar(
            db,
            produto,
            tipo=TIPO_ENTRADA,
            quantidade=entrada.estoque_inicial,
            referencia=REF_AJUSTE_MANUAL,
            observacao=estoque.com_responsavel("Estoque inicial importado", ator),
        )
    return True


def _venda(db: Session, linhas: list[dict[str, str]], ator: Usuario) -> bool:
    itens = [
        LinhaVenda(
            **{
                **d,
                "preco_unitario": _decimal(d["preco_unitario"]),
                "data_venda": _data(d["data_venda"]),
                "data_pagamento": _data(d["data_pagamento"]) if d.get("data_pagamento") else None,
            }
        )
        for d in linhas
    ]
    primeiro = itens[0]
    if db.get(VendaImportada, primeiro.pedido_origem):
        return False
    comuns = primeiro.model_dump(exclude={"produto", "quantidade", "preco_unitario"})
    if any(
        i.model_dump(exclude={"produto", "quantidade", "preco_unitario"}) != comuns for i in itens
    ):
        raise ValueError("Os dados do mesmo pedido_origem precisam ser iguais em todas as linhas.")
    if len(itens) > 100 or len({i.produto.lower() for i in itens}) != len(itens):
        raise ValueError("Use até 100 produtos distintos por pedido; some quantidades repetidas.")
    if primeiro.data_venda > hoje_local() or (
        primeiro.data_pagamento
        and (
            primeiro.data_pagamento < primeiro.data_venda or primeiro.data_pagamento > hoje_local()
        )
    ):
        raise ValueError(
            "Confira as datas: venda não pode ser futura e pagamento deve ser entre a venda e hoje."
        )
    cliente = db.scalar(select(Cliente).where(Cliente.telefone == primeiro.cliente_telefone))
    if not cliente:
        raise ValueError("Cliente não encontrado. Importe/cadastre o cliente primeiro.")
    vinculos = sorted(cliente.enderecos, key=lambda v: (not v.principal, v.id_endereco))
    if not vinculos:
        raise ValueError("Cadastre o endereço principal do cliente antes de importar a venda.")
    responsavel = ator
    if primeiro.responsavel_email:
        encontrada = db.scalar(
            select(Usuario).where(Usuario.email == normalizar_email(primeiro.responsavel_email))
        )
        if not encontrada:
            raise ValueError("Responsável não encontrado. Cadastre o usuário ou confira o e-mail.")
        responsavel = encontrada
    venda = Venda(
        id_cliente=cliente.id_cliente,
        id_endereco=vinculos[0].id_endereco,
        id_usuario=responsavel.id_usuario,
        data_venda=inicio_do_dia_utc(primeiro.data_venda),
        data_pagamento=inicio_do_dia_utc(primeiro.data_pagamento)
        if primeiro.data_pagamento
        else None,
        forma_pagamento=primeiro.forma_pagamento,
        status=primeiro.status,
        valor_total=Decimal(0),
        observacao=f"Histórico importado: {primeiro.pedido_origem}. {primeiro.observacao}".strip(),
    )
    for item in itens:
        produtos = list(
            db.scalars(
                select(Produto).where(func.lower(Produto.nome) == item.produto.lower()).limit(2)
            )
        )
        if len(produtos) != 1:
            raise ValueError(
                f"Produto '{item.produto}' inexistente ou com nome repetido. Confira o cadastro."
            )
        subtotal = item.preco_unitario * item.quantidade
        venda.itens.append(
            ItemVenda(
                id_produto=produtos[0].id_produto,
                quantidade=item.quantidade,
                preco_unitario_v=item.preco_unitario,
                subtotal=subtotal,
            )
        )
        venda.valor_total += subtotal
    if venda.valor_total > Decimal("99999999.99"):
        raise ValueError("Valor total do pedido acima do limite.")
    db.add(venda)
    db.flush()
    db.add(
        VendaImportada(
            referencia=primeiro.pedido_origem, id_venda=venda.id_venda, id_usuario=ator.id_usuario
        )
    )
    return True


def processar(
    db: Session,
    conteudo: bytes,
    nome: str,
    tipo: TipoImportacao,
    ator: Usuario,
    token: str | None = None,
) -> ResultadoImportacao:
    resumo = ResultadoImportacao(tipo=tipo, total_linhas=0)
    digest = hashlib.sha256(conteudo).hexdigest()
    if token:
        try:
            dados = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"require": ["type", "sha256", "sub", "tipo", "exp"]},
            )
            if (dados["type"], dados["sha256"], dados["sub"], dados["tipo"]) != (
                "import_preview",
                digest,
                str(ator.id_usuario),
                tipo,
            ):
                raise ValueError
        except (jwt.PyJWTError, ValueError):
            raise RegraInvalidaError(
                "Prévia inválida ou expirada. Analise o arquivo novamente."
            ) from None
    linhas = ler(conteudo, nome, tipo)
    resumo.total_linhas = len(linhas)
    resumo.amostra = [d for _, d in linhas[:5]]
    grupos: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for numero, linha in linhas:
        grupos[linha.get("pedido_origem", "") if tipo == "vendas" else str(numero)].append(
            (numero, linha)
        )
    transacao = db.begin_nested()
    try:
        for grupo in grupos.values():
            try:
                with db.begin_nested():
                    if tipo == "vendas":
                        novo = _venda(db, [d for _, d in grupo], ator)
                    elif tipo == "clientes":
                        novo = _cliente(db, grupo[0][1], ator)
                    else:
                        novo = _produto(db, grupo[0][1], ator)
                    db.flush()
                if novo:
                    resumo.novos += 1
                else:
                    resumo.ignorados += 1
            except (ValueError, ArithmeticError, ErroDeNegocio, IntegrityError) as exc:
                if isinstance(exc, ValidationError):
                    mensagem = "; ".join(
                        f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()
                    )
                elif isinstance(exc, IntegrityError):
                    mensagem = "Conflito com os dados existentes. Confira duplicados e referências."
                else:
                    mensagem = str(exc)
                resumo.erros.append(ProblemaImportacao(linha=grupo[0][0], mensagem=mensagem))
        if token and not resumo.erros:
            transacao.commit()
            db.commit()
            resumo.concluida = True
        else:
            transacao.rollback()
    except Exception:
        if transacao.is_active:
            transacao.rollback()
        raise
    if not token and not resumo.erros:
        resumo.token = jwt.encode(
            {
                "type": "import_preview",
                "sha256": digest,
                "sub": str(ator.id_usuario),
                "tipo": tipo,
                "exp": datetime.now(UTC) + timedelta(minutes=15),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
    return resumo
