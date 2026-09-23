"""Hash de senha (passlib/bcrypt) e emissão/validação de JWT (python-jose)."""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt trunca silenciosamente acima de 72 bytes; recusamos antes disso para
# que duas senhas diferentes nunca gerem o mesmo hash.
SENHA_MAX_BYTES = 72


def hash_senha(senha: str) -> str:
    """Gera o hash bcrypt de uma senha em texto puro."""
    return pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Compara uma senha em texto puro com o hash armazenado."""
    try:
        return pwd_context.verify(senha, senha_hash)
    except ValueError:
        # Hash malformado ou de outro esquema: trata como credencial inválida.
        return False


def criar_access_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    """Emite um JWT assinado tendo `subject` como `sub`."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decodificar_access_token(token: str) -> dict[str, Any] | None:
    """Valida assinatura e expiração. Devolve o payload, ou None se inválido."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
