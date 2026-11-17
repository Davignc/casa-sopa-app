"""Servidor isolado para as capturas; usa somente registros fictícios."""

import os
import secrets
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
destino = Path(sys.argv[1]).resolve()
destino.mkdir(parents=True, exist_ok=True)
os.environ.update(
    DATABASE_URL=f"sqlite:///{(destino / 'demonstracao.db').as_posix()}",
    SECRET_KEY=secrets.token_urlsafe(40),
    BCRYPT_ROUNDS="4",
    ENVIRONMENT="development",
    BACKUP_ENABLED="false",
    SMTP_USER="",
    SMTP_PASSWORD="",
    UPLOADS_DIR=str(destino / "uploads"),
)

import uvicorn  # noqa: E402

from app.core.tempo import agora_utc  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import ItemVenda, Venda  # noqa: E402
from app.schemas.cliente import ClienteCreate, EnderecoEntrada  # noqa: E402
from app.schemas.produto import ProdutoCreate  # noqa: E402
from app.schemas.usuario import UsuarioCreate  # noqa: E402
from app.services import cliente, produto, usuario  # noqa: E402

Base.metadata.create_all(engine)
with SessionLocal() as db:
    admin = usuario.criar_usuario(
        db,
        UsuarioCreate(
            nome="Ana • Demonstração",
            email="admin@example.org",
            telefone="16990000001",
            cargo="administradora",
            senha="Demonstracao123",
        ),
    )
    vendedora = usuario.criar_usuario(
        db,
        UsuarioCreate(
            nome="Maria • Demonstração",
            email="maria@example.org",
            telefone="16990000002",
            cargo="vendedora",
            comissao=Decimal(10),
            senha="Demonstracao123",
        ),
    )
    produtos = [
        produto.criar(
            db,
            ProdutoCreate(
                nome=nome,
                descricao="Pacote com 10 unidades",
                preco_unitario=Decimal(preco),
                estoque_inicial=saldo,
                estoque_minimo=10,
            ),
            admin,
        )
        for nome, preco, saldo in [
            ("Saco de lixo 100 L", "25", 80),
            ("Saco de lixo 50 L", "18", 45),
            ("Saco de lixo 30 L", "12", 6),
        ]
    ]
    pessoas = [
        cliente.criar(
            db,
            ClienteCreate(
                nome=nome,
                telefone=f"1699000001{i}",
                enderecos=[
                    EnderecoEntrada(
                        cep="14430000",
                        cidade="Restinga",
                        bairro="Centro",
                        tipo_logradouro="Rua",
                        nome_logradouro="Exemplo",
                        numero=str(10 + i),
                    ),
                ],
            ),
            admin,
        )
        for i, nome in enumerate(["Cliente Exemplo A", "Cliente Exemplo B", "Cliente Exemplo C"])
    ]
    for i in range(15):
        pessoa, item = pessoas[i % 3], produtos[i % 3]
        pedido = Venda(
            id_cliente=pessoa.id_cliente,
            id_usuario=vendedora.id_usuario if i % 2 else admin.id_usuario,
            id_endereco=pessoa.enderecos[0].id_endereco,
            data_venda=agora_utc() - timedelta(days=i),
            forma_pagamento=["pix", "dinheiro", "cartão"][i % 3],
            status=["em_aberto", "confirmado", "entregue", "entregue", "cancelado"][i % 5],
            valor_total=item.preco_unitario * (i % 4 + 1),
            observacao="Dados fictícios de demonstração",
        )
        pedido.itens.append(
            ItemVenda(
                id_produto=item.id_produto,
                quantidade=i % 4 + 1,
                preco_unitario_v=item.preco_unitario,
                subtotal=pedido.valor_total,
            )
        )
        db.add(pedido)
    db.commit()

uvicorn.run("app.main:app", host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
