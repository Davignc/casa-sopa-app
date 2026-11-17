"""Links temporários, vinculados à senha atual e consumidos atomicamente no banco."""

import hmac
import logging
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from urllib.parse import urlencode

import jwt
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import RegraInvalidaError
from app.core.security import hash_senha, versao_da_senha
from app.models.usuario import Usuario

logger = logging.getLogger("casa_sopa.recuperacao")
MENSAGEM = (
    "Se o e-mail estiver cadastrado e ativo, você receberá um link para redefinir a senha. "
    "Confira também o spam."
)


def verificar_configuracao() -> None:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD.get_secret_value():
        raise HTTPException(503, "Recuperação por e-mail indisponível. Contate a administradora.")


def criar_token(usuario: Usuario) -> str:
    agora = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(usuario.id_usuario),
            "type": "password_reset",
            "sv": versao_da_senha(usuario.senha),
            "email": usuario.email,
            "iat": agora,
            "exp": agora + timedelta(minutes=settings.RESET_PASSWORD_EXPIRE_MINUTES),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def enviar_email(destinatario: str, token: str) -> None:
    link = (
        str(settings.FRONTEND_URL).rstrip("/") + "/#/redefinir-senha?" + urlencode({"token": token})
    )
    mensagem = EmailMessage()
    mensagem["Subject"] = "Casa da Sopa — redefinir sua senha"
    mensagem["From"] = settings.SMTP_USER
    mensagem["To"] = destinatario
    mensagem.set_content(
        "Recebemos um pedido para redefinir sua senha da Casa da Sopa de Restinga.\n\n"
        f"Abra este link: {link}\n\n"
        f"Ele vale por {settings.RESET_PASSWORD_EXPIRE_MINUTES} minutos "
        "e só pode ser usado uma vez.\n"
        "Se você não fez o pedido, ignore esta mensagem. Sua senha permanece a mesma."
    )
    try:
        contexto = ssl.create_default_context()
        smtp: smtplib.SMTP
        if settings.SMTP_PORT == 465:
            smtp = smtplib.SMTP_SSL(settings.SMTP_HOST, 465, timeout=15, context=contexto)
        else:
            smtp = smtplib.SMTP(settings.SMTP_HOST, 587, timeout=15)
        with smtp:
            if settings.SMTP_PORT == 587:
                smtp.starttls(context=contexto)
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD.get_secret_value())
            smtp.send_message(mensagem)
    except (smtplib.SMTPException, OSError):
        # Não registra token, senha, corpo da mensagem nem a resposta do provedor.
        logger.error("Falha no envio da recuperação de senha. Verifique a configuração SMTP.")


def redefinir(db: Session, token: str, senha: str) -> None:
    erro = RegraInvalidaError("Link inválido, expirado ou já utilizado. Solicite outro link.")
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["sub", "type", "sv", "email", "iat", "exp"]},
        )
        if payload["type"] != "password_reset":
            raise erro
        usuario = db.get(Usuario, int(payload["sub"]))
    except (jwt.PyJWTError, TypeError, ValueError):
        raise erro from None
    if (
        usuario is None
        or not usuario.is_ativo
        or usuario.email != payload["email"]
        or not hmac.compare_digest(str(payload["sv"]), versao_da_senha(usuario.senha))
    ):
        raise erro
    resultado = db.execute(
        update(Usuario)
        .where(
            Usuario.id_usuario == usuario.id_usuario,
            Usuario.senha == usuario.senha,
            Usuario.email == payload["email"],
            Usuario.is_ativo.is_(True),
        )
        .values(senha=hash_senha(senha))
        .returning(Usuario.id_usuario)
    )
    if resultado.scalar_one_or_none() is None:
        db.rollback()
        raise erro
    db.commit()
