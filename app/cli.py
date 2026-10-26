"""Comandos de linha de comando.

Cria a primeira administradora — necessário porque só uma administradora pode
cadastrar usuários (RN03) e, no início, não existe nenhuma.

    uv run python -m app.cli criar-admin --nome "Maria" --email maria@x.org --telefone 16999990000

A senha é pedida no terminal (não vai para o histórico do shell). Para uso não
interativo, defina a variável de ambiente CASA_SOPA_ADMIN_SENHA.
"""

import argparse
import getpass
import os
import sys

from pydantic import ValidationError

from app.core.errors import ErroDeNegocio
from app.db.session import SessionLocal
from app.schemas.usuario import UsuarioCreate
from app.services import usuario as usuario_service


def _ler_senha() -> str:
    senha = os.environ.get("CASA_SOPA_ADMIN_SENHA")
    if senha:
        return senha
    senha = getpass.getpass("Senha: ")
    if senha != getpass.getpass("Confirme a senha: "):
        raise SystemExit("As senhas não conferem.")
    return senha


def criar_admin(nome: str, email: str, telefone: str, senha: str) -> int:
    """Cadastra uma administradora. Devolve o id criado."""
    try:
        dados = UsuarioCreate(
            nome=nome,
            email=email,
            telefone=telefone,
            cargo="administradora",
            senha=senha,
        )
    except ValidationError as exc:
        mensagens = "; ".join(e["msg"] for e in exc.errors())
        raise SystemExit(f"Dados inválidos: {mensagens}") from None

    with SessionLocal() as db:
        try:
            usuario = usuario_service.criar_usuario(db, dados)
        except ErroDeNegocio as exc:
            raise SystemExit(exc.detail) from None
        return usuario.id_usuario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("criar-admin", help="Cria uma administradora.")
    p.add_argument("--nome", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--telefone", required=True)

    args = parser.parse_args(argv)
    if args.comando == "criar-admin":
        id_usuario = criar_admin(args.nome, args.email, args.telefone, _ler_senha())
        print(f"Administradora criada (id={id_usuario}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
