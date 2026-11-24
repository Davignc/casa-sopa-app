"""Dados de exemplo para desenvolvimento.

Popula vendedoras, produtos, clientes, endereços, pedidos e movimentações coerentes entre si
(o estoque de cada produto é a soma das suas movimentações), com datas relativas ao dia em que
a migration roda, para o painel e os relatórios terem o que mostrar.

Não faz nada em produção (ENVIRONMENT=production) nem em banco que já tenha produto cadastrado.
O downgrade remove apenas o que esta migration criou.

Login das vendedoras de exemplo: e-mails em @exemplo.casadasopa.dev, senha Exemplo@123.

Revision ID: 0003
Revises: 0002
"""

import logging
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import bcrypt
import sqlalchemy as sa

from alembic import op
from app.core.config import settings

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

DOMINIO = "@exemplo.casadasopa.dev"
SENHA = "Exemplo@123"

VENDEDORAS = [
    ("Ana Paula Souza", "ana", "16991000001", Decimal("10.00"), True),
    ("Beatriz Oliveira", "beatriz", "16991000002", Decimal("8.00"), True),
    ("Carla Mendes", "carla", "16991000003", Decimal("12.00"), True),
    ("Denise Rocha", "denise", "16991000004", Decimal("10.00"), False),
]

PRODUTOS = [
    ("Saco de lixo 15 L", "Pacote com 50 unidades, cor preta", "8.50", 30),
    ("Saco de lixo 30 L", "Pacote com 50 unidades, cor preta", "12.00", 30),
    ("Saco de lixo 50 L", "Pacote com 25 unidades, cor preta", "14.00", 30),
    ("Saco de lixo 100 L", "Pacote com 25 unidades, reforçado", "22.00", 25),
    ("Saco de lixo 200 L", "Pacote com 10 unidades, extra reforçado", "28.00", 20),
    ("Saco de lixo azul 100 L", "Pacote com 25 unidades, para recicláveis", "23.50", 15),
    ("Saco para pia", "Rolo com 100 unidades", "6.00", 40),
    ("Kit cozinha", "1 pacote 30 L + 1 rolo para pia", "16.00", 20),
]
COM_ESTOQUE_BAIXO = {"Saco de lixo 200 L", "Saco de lixo azul 100 L"}

ENDERECOS = [
    ("Restinga", "Centro", "Rua", "Coronel Joaquim Garcia", "14430000"),
    ("Restinga", "Centro", "Avenida", "Brasil", "14430000"),
    ("Restinga", "Jardim Primavera", "Rua", "das Flores", "14430000"),
    ("Restinga", "Vila Nova", "Rua", "São Sebastião", "14430000"),
    ("Restinga", "Jardim Bela Vista", "Rua", "Ipê Amarelo", "14430000"),
    ("Franca", "Centro", "Rua", "Voluntários da Franca", "14400490"),
    ("Franca", "Jardim Paulista", "Avenida", "Major Nicácio", "14401135"),
    ("Franca", "Cidade Nova", "Rua", "Ouvidor Freire", "14401000"),
    ("Franca", "Vila Santos Dumont", "Rua", "Campos Salles", "14405000"),
    ("Franca", "Parque Universitário", "Avenida", "Dr. Armando Salles Oliveira", "14404600"),
]

CLIENTES = [
    "Maria Aparecida Silva",
    "José Carlos Pereira",
    "Antônia Ferreira",
    "João Batista Lima",
    "Francisca Gomes",
    "Luiz Henrique Costa",
    "Sebastiana Alves",
    "Paulo Roberto Dias",
    "Lúcia Helena Martins",
    "Pedro Henrique Ribeiro",
    "Rosângela Barbosa",
    "Marcos Vinícius Teixeira",
    "Cláudia Regina Cardoso",
    "Restaurante Sabor da Terra",
    "Padaria Pão Quente",
    "Escola Municipal Dom Pedro",
    "Mercadinho São José",
    "Igreja Nossa Senhora Aparecida",
]

FORMAS_PAGAMENTO = ["pix", "pix", "pix", "dinheiro", "dinheiro", "cartão de débito"]

usuario = sa.table(
    "usuario",
    sa.column("id_usuario", sa.Integer),
    sa.column("nome", sa.String),
    sa.column("email", sa.String),
    sa.column("telefone", sa.String),
    sa.column("senha", sa.String),
    sa.column("cargo", sa.String),
    sa.column("comissao", sa.Numeric),
    sa.column("is_ativo", sa.Boolean),
)
produto = sa.table(
    "produto",
    sa.column("id_produto", sa.Integer),
    sa.column("nome", sa.String),
    sa.column("descricao", sa.String),
    sa.column("preco_unitario", sa.Numeric),
    sa.column("estoque_atual", sa.Integer),
    sa.column("estoque_minimo", sa.Integer),
    sa.column("is_ativo", sa.Boolean),
)
endereco = sa.table(
    "endereco",
    sa.column("id_endereco", sa.Integer),
    sa.column("cidade", sa.String),
    sa.column("bairro", sa.String),
    sa.column("tipo_logradouro", sa.String),
    sa.column("nome_logradouro", sa.String),
    sa.column("cep", sa.String),
    sa.column("is_ativo", sa.Boolean),
)
cliente = sa.table(
    "cliente",
    sa.column("id_cliente", sa.Integer),
    sa.column("nome", sa.String),
    sa.column("telefone", sa.String),
    sa.column("id_usuario", sa.Integer),
    sa.column("is_ativo", sa.Boolean),
)
cliente_endereco = sa.table(
    "cliente_endereco",
    sa.column("id_cliente", sa.Integer),
    sa.column("id_endereco", sa.Integer),
    sa.column("apelido", sa.String),
    sa.column("principal", sa.Boolean),
    sa.column("numero", sa.String),
    sa.column("complemento", sa.String),
    sa.column("referencia", sa.String),
)
vendas = sa.table(
    "vendas",
    sa.column("id_venda", sa.Integer),
    sa.column("data_venda", sa.DateTime(timezone=True)),
    sa.column("valor_total", sa.Numeric),
    sa.column("forma_pagamento", sa.String),
    sa.column("status", sa.String),
    sa.column("observacao", sa.String),
    sa.column("id_cliente", sa.Integer),
    sa.column("id_usuario", sa.Integer),
    sa.column("data_pagamento", sa.DateTime(timezone=True)),
    sa.column("id_endereco", sa.Integer),
)
item_vendas = sa.table(
    "item_vendas",
    sa.column("id_venda", sa.Integer),
    sa.column("id_produto", sa.Integer),
    sa.column("preco_unitario_v", sa.Numeric),
    sa.column("quantidade", sa.Integer),
    sa.column("subtotal", sa.Numeric),
)
movimentacoes = sa.table(
    "movimentacoes",
    sa.column("id_movimentacao", sa.Integer),
    sa.column("tipo_movimentacao", sa.String),
    sa.column("quantidade", sa.Integer),
    sa.column("tipo_referencia", sa.String),
    sa.column("data_movimentacao", sa.DateTime(timezone=True)),
    sa.column("observacao", sa.String),
    sa.column("id_venda", sa.Integer),
    sa.column("id_produto", sa.Integer),
)


def _inserir(conn: sa.Connection, tabela: sa.TableClause, pk: str, valores: dict) -> int:
    return conn.execute(tabela.insert().values(**valores).returning(tabela.c[pk])).scalar_one()


def upgrade() -> None:
    conn = op.get_bind()
    if settings.ENVIRONMENT == "production":
        log.warning("0003: ENVIRONMENT=production, dados de exemplo NÃO foram inseridos.")
        return
    if conn.execute(sa.select(sa.func.count()).select_from(produto)).scalar_one():
        log.warning("0003: já existem produtos cadastrados, dados de exemplo NÃO foram inseridos.")
        return

    rng = random.Random(2026)
    agora = datetime.now(UTC).replace(microsecond=0)
    inicio = agora - timedelta(days=150)
    senha_hash = bcrypt.hashpw(SENHA.encode(), bcrypt.gensalt(rounds=10)).decode("ascii")

    ids_vendedoras: list[int] = []
    nomes_vendedoras: dict[int, str] = {}
    for nome, login, telefone, comissao, ativa in VENDEDORAS:
        id_usuario = _inserir(
            conn,
            usuario,
            "id_usuario",
            {
                "nome": nome,
                "email": f"{login}{DOMINIO}",
                "telefone": telefone,
                "senha": senha_hash,
                "cargo": "vendedora",
                "comissao": comissao,
                "is_ativo": ativa,
            },
        )
        nomes_vendedoras[id_usuario] = nome
        if ativa:
            ids_vendedoras.append(id_usuario)
    responsavel = f"[por {nomes_vendedoras[ids_vendedoras[0]]}]"

    ids_enderecos = [
        _inserir(
            conn,
            endereco,
            "id_endereco",
            {
                "cidade": cidade,
                "bairro": bairro,
                "tipo_logradouro": tipo,
                "nome_logradouro": logradouro,
                "cep": cep,
                "is_ativo": True,
            },
        )
        for cidade, bairro, tipo, logradouro, cep in ENDERECOS
    ]

    enderecos_do_cliente: dict[int, list[int]] = {}
    dono_do_cliente: dict[int, int] = {}
    for i, nome in enumerate(CLIENTES):
        id_vendedora = ids_vendedoras[i % len(ids_vendedoras)]
        id_cliente = _inserir(
            conn,
            cliente,
            "id_cliente",
            {
                "nome": nome,
                "telefone": f"169920000{i + 1:02d}",
                "id_usuario": id_vendedora,
                "is_ativo": i != len(CLIENTES) - 1,
            },
        )
        dono_do_cliente[id_cliente] = id_vendedora
        escolhidos = [ids_enderecos[i % len(ids_enderecos)]]
        if i % 4 == 0:
            escolhidos.append(ids_enderecos[(i + 3) % len(ids_enderecos)])
        for ordem, id_endereco in enumerate(escolhidos):
            conn.execute(
                cliente_endereco.insert().values(
                    id_cliente=id_cliente,
                    id_endereco=id_endereco,
                    apelido="Casa" if ordem == 0 else "Trabalho",
                    principal=ordem == 0,
                    numero=str(rng.randint(10, 1999)),
                    complemento="" if rng.random() < 0.7 else "Fundos",
                    referencia="" if rng.random() < 0.6 else "Perto da praça",
                )
            )
        enderecos_do_cliente[id_cliente] = escolhidos

    precos = {nome: Decimal(preco) for nome, _, preco, _ in PRODUTOS}
    estoque_inicial = {nome: rng.randint(180, 260) for nome, *_ in PRODUTOS}
    compras = {nome: rng.choice([0, 0, 50, 100]) for nome, *_ in PRODUTOS}
    saldo = {nome: estoque_inicial[nome] + compras[nome] for nome in estoque_inicial}

    pedidos = []
    for n in range(70):
        dias = rng.randint(0, 12) if n < 18 else rng.randint(0, 120)
        data_venda = agora - timedelta(
            days=dias, hours=rng.randint(0, 9), minutes=rng.randint(0, 59)
        )
        sorteio = rng.random()
        if dias <= 3:
            status = "em_aberto" if sorteio < 0.75 else "cancelado"
        elif dias <= 12:
            status = (
                "confirmado" if sorteio < 0.7 else ("entregue" if sorteio < 0.9 else "cancelado")
            )
        else:
            status = "entregue" if sorteio < 0.85 else "cancelado"
        id_cliente = rng.choice(list(enderecos_do_cliente))
        itens = {nome: rng.randint(1, 6) for nome in rng.sample(list(precos), rng.randint(1, 3))}
        baixou_estoque = status in ("confirmado", "entregue") or (
            status == "cancelado" and rng.random() < 0.5
        )
        if status in ("confirmado", "entregue"):
            for nome, qtd in itens.items():
                saldo[nome] -= qtd
        pedidos.append((data_venda, status, id_cliente, itens, baixou_estoque))
    pedidos.sort(key=lambda p: p[0])

    ids_produtos: dict[str, int] = {}
    for nome, descricao, _, minimo in PRODUTOS:
        if nome in COM_ESTOQUE_BAIXO:
            minimo = max(saldo[nome] + 15, minimo)
        ids_produtos[nome] = _inserir(
            conn,
            produto,
            "id_produto",
            {
                "nome": nome,
                "descricao": descricao,
                "preco_unitario": precos[nome],
                "estoque_atual": saldo[nome],
                "estoque_minimo": minimo,
                "is_ativo": True,
            },
        )
        conn.execute(
            movimentacoes.insert().values(
                tipo_movimentacao="entrada",
                quantidade=estoque_inicial[nome],
                tipo_referencia="ajuste_manual",
                data_movimentacao=inicio,
                observacao=f"Estoque inicial {responsavel}",
                id_venda=None,
                id_produto=ids_produtos[nome],
            )
        )
        if compras[nome]:
            conn.execute(
                movimentacoes.insert().values(
                    tipo_movimentacao="entrada",
                    quantidade=compras[nome],
                    tipo_referencia="compra",
                    data_movimentacao=agora - timedelta(days=60),
                    observacao=f"Compra do fornecedor {responsavel}",
                    id_venda=None,
                    id_produto=ids_produtos[nome],
                )
            )

    for data_venda, status, id_cliente, itens, baixou_estoque in pedidos:
        total = sum((precos[n] * q for n, q in itens.items()), Decimal("0.00"))
        pago = status == "entregue" or (status == "confirmado" and rng.random() < 0.5)
        id_venda = _inserir(
            conn,
            vendas,
            "id_venda",
            {
                "data_venda": data_venda,
                "valor_total": total,
                "forma_pagamento": rng.choice(FORMAS_PAGAMENTO),
                "status": status,
                "observacao": rng.choice([None, None, None, "Entregar à tarde", "Ligar antes"]),
                "id_cliente": id_cliente,
                "id_usuario": dono_do_cliente[id_cliente],
                "data_pagamento": data_venda + timedelta(days=rng.randint(0, 2)) if pago else None,
                "id_endereco": rng.choice(enderecos_do_cliente[id_cliente]),
            },
        )
        for nome, qtd in itens.items():
            conn.execute(
                item_vendas.insert().values(
                    id_venda=id_venda,
                    id_produto=ids_produtos[nome],
                    preco_unitario_v=precos[nome],
                    quantidade=qtd,
                    subtotal=precos[nome] * qtd,
                )
            )
            if baixou_estoque:
                conn.execute(
                    movimentacoes.insert().values(
                        tipo_movimentacao="saida",
                        quantidade=qtd,
                        tipo_referencia="venda",
                        data_movimentacao=data_venda + timedelta(hours=1),
                        observacao=f"Pedido #{id_venda}",
                        id_venda=id_venda,
                        id_produto=ids_produtos[nome],
                    )
                )
                if status == "cancelado":
                    conn.execute(
                        movimentacoes.insert().values(
                            tipo_movimentacao="entrada",
                            quantidade=qtd,
                            tipo_referencia="venda",
                            data_movimentacao=data_venda + timedelta(hours=5),
                            observacao=f"Cancelamento do pedido #{id_venda}",
                            id_venda=id_venda,
                            id_produto=ids_produtos[nome],
                        )
                    )


def downgrade() -> None:
    conn = op.get_bind()
    ids_usuarios = sa.select(usuario.c.id_usuario).where(usuario.c.email.like(f"%{DOMINIO}"))
    ids_clientes = sa.select(cliente.c.id_cliente).where(cliente.c.id_usuario.in_(ids_usuarios))
    ids_vendas = sa.select(vendas.c.id_venda).where(vendas.c.id_usuario.in_(ids_usuarios))
    ids_produtos = sa.select(produto.c.id_produto).where(
        produto.c.nome.in_([nome for nome, *_ in PRODUTOS])
    )
    ids_enderecos = [
        conn.execute(
            sa.select(endereco.c.id_endereco).where(
                endereco.c.cep == cep,
                endereco.c.nome_logradouro == logradouro,
                endereco.c.bairro == bairro,
                endereco.c.cidade == cidade,
            )
        )
        .scalars()
        .all()
        for cidade, bairro, _, logradouro, cep in ENDERECOS
    ]

    conn.execute(movimentacoes.delete().where(movimentacoes.c.id_venda.in_(ids_vendas)))
    conn.execute(item_vendas.delete().where(item_vendas.c.id_venda.in_(ids_vendas)))
    conn.execute(vendas.delete().where(vendas.c.id_venda.in_(ids_vendas)))
    conn.execute(cliente_endereco.delete().where(cliente_endereco.c.id_cliente.in_(ids_clientes)))
    conn.execute(cliente.delete().where(cliente.c.id_cliente.in_(ids_clientes)))
    usados = sa.select(cliente_endereco.c.id_endereco)
    for ids in ids_enderecos:
        conn.execute(
            endereco.delete().where(
                endereco.c.id_endereco.in_(ids), endereco.c.id_endereco.not_in(usados)
            )
        )
    if not conn.execute(
        sa.select(sa.func.count())
        .select_from(item_vendas)
        .where(item_vendas.c.id_produto.in_(ids_produtos))
    ).scalar_one():
        conn.execute(movimentacoes.delete().where(movimentacoes.c.id_produto.in_(ids_produtos)))
        conn.execute(produto.delete().where(produto.c.id_produto.in_(ids_produtos)))
    conn.execute(usuario.delete().where(usuario.c.email.like(f"%{DOMINIO}")))
