"""Hash de senha (bcrypt) e emissão/validação de JWT (PyJWT)."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unicodedata import category

import bcrypt
import jwt

from app.core.config import settings

# bcrypt só olha os 72 primeiros bytes. Recusamos acima disso para que duas senhas
# diferentes nunca gerem o mesmo hash.
SENHA_MAX_BYTES = 72
SENHA_MIN_CARACTERES = 8


def validar_senha_forte(senha: str) -> str:
    """Valida senhas novas sem modificar os caracteres informados."""
    if len(senha.encode("utf-8")) > SENHA_MAX_BYTES:
        raise ValueError(f"A senha não pode passar de {SENHA_MAX_BYTES} bytes.")
    categorias = {category(caractere) for caractere in senha}
    if (
        len(senha) < SENHA_MIN_CARACTERES
        or not {"Lu", "Ll", "Nd"}.issubset(categorias)
        or not any(categoria[0] in {"P", "S"} for categoria in categorias)
    ):
        raise ValueError(
            "A senha deve ter no mínimo 8 caracteres, letra maiúscula, "
            "letra minúscula, número e símbolo."
        )
    return senha


# Tolerância (segundos) para pequenas diferenças de relógio ao validar "iat".
_TOLERANCIA_RELOGIO = 10


def hash_senha(senha: str) -> str:
    """Gera o hash bcrypt de uma senha em texto puro."""
    dados = senha.encode("utf-8")
    if len(dados) > SENHA_MAX_BYTES:
        raise ValueError(f"A senha não pode passar de {SENHA_MAX_BYTES} bytes.")
    return bcrypt.hashpw(dados, bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)).decode("ascii")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Compara uma senha em texto puro com o hash armazenado."""
    dados = senha.encode("utf-8")
    if len(dados) > SENHA_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(dados, senha_hash.encode("utf-8"))
    except ValueError:
        # Hash malformado: trata como credencial inválida.
        return False


# Hash válido de uma senha descartável, usado no login de e-mail inexistente só
# para gastar o mesmo tempo de um bcrypt real. O resultado nunca é aproveitado.
HASH_FALSO = hash_senha("senha-descartavel-so-para-igualar-o-tempo")


def versao_da_senha(senha_hash: str) -> str:
    """Impressão digital curta do hash da senha atual.

    Vai dentro do token: quando a senha muda, o hash muda, e todos os tokens
    emitidos antes deixam de valer — sem precisar guardar nada no banco.
    """
    return hashlib.sha256(senha_hash.encode("utf-8")).hexdigest()[:16]


def criar_access_token(
    subject: str | int,
    *,
    versao_senha: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Emite um JWT assinado, com id único (``jti``) para permitir revogação."""
    agora = datetime.now(UTC)
    expira = agora + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expira,
        "iat": agora,
        "jti": uuid.uuid4().hex,
        "type": "access",
        "sv": versao_senha,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decodificar_access_token(token: str) -> dict[str, Any] | None:
    """Valida assinatura, expiração e campos obrigatórios. None se algo falhar."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],  # lista fixa: o token não escolhe o algoritmo
            options={"require": ["exp", "iat", "sub", "jti"]},
            leeway=_TOLERANCIA_RELOGIO,
        )
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != "access":
        return None
    return payload
