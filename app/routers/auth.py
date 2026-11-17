import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DbSession, TokenAtual
from app.core import protecao
from app.core.errors import NaoAutenticadoError
from app.core.security import criar_access_token, versao_da_senha
from app.core.validators import normalizar_email
from app.schemas.recuperacao import RecuperarSenha, RedefinirSenha
from app.schemas.token import Token
from app.schemas.usuario import LoginRequest
from app.services import recuperacao
from app.services import usuario as usuario_service

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("casa_sopa.auth")


@router.post("/recuperar-senha", status_code=202)
def recuperar_senha(
    request: Request, dados: RecuperarSenha, db: DbSession, tarefas: BackgroundTasks
) -> dict[str, str]:
    ip = _ip_do_cliente(request)
    chave = normalizar_email(str(dados.email))
    for limitador, valor in (
        (protecao.limitador_recuperacao_ip, ip),
        (protecao.limitador_recuperacao_email, chave),
    ):
        limitador.verificar(valor)
        limitador.registrar_falha(valor)
    recuperacao.verificar_configuracao()
    usuario = usuario_service.buscar_por_email(db, chave)
    if usuario and usuario.is_ativo:
        tarefas.add_task(recuperacao.enviar_email, usuario.email, recuperacao.criar_token(usuario))
    return {"detail": recuperacao.MENSAGEM}


@router.post("/redefinir-senha", status_code=204)
def redefinir_senha(request: Request, dados: RedefinirSenha, db: DbSession) -> Response:
    ip = _ip_do_cliente(request)
    protecao.limitador_redefinicao.verificar(ip)
    protecao.limitador_redefinicao.registrar_falha(ip)
    recuperacao.redefinir(db, dados.token, dados.senha)
    return Response(status_code=204)


def _ip_do_cliente(request: Request) -> str:
    # Não confia em X-Forwarded-For (qualquer cliente pode forjá-lo). Atrás de um
    # proxy reverso, configure o uvicorn com --proxy-headers e a lista de IPs confiáveis.
    return request.client.host if request.client else "desconhecido"


def _tentar_login(request: Request, db: DbSession, email: str, senha: str) -> Token:
    ip = _ip_do_cliente(request)
    email = normalizar_email(email)
    chave_conta = f"{ip}|{email}"

    # Bloqueado = não chega nem a conferir a senha (nem a correta passa).
    protecao.limitador_login_conta.verificar(chave_conta)
    protecao.limitador_login_ip.verificar(ip)

    usuario = usuario_service.autenticar(db, email, senha)
    if usuario is None:
        protecao.limitador_login_conta.registrar_falha(chave_conta)
        protecao.limitador_login_ip.registrar_falha(ip)
        logger.warning("Falha de login: email=%s ip=%s", email, ip)
        raise NaoAutenticadoError("E-mail ou senha incorretos.")

    protecao.limitador_login_conta.registrar_sucesso(chave_conta)
    return Token(
        access_token=criar_access_token(
            usuario.id_usuario, versao_senha=versao_da_senha(usuario.senha)
        )
    )


@router.post("/login", response_model=Token)
def login(
    request: Request,
    db: DbSession,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """Login no formato OAuth2 (form-urlencoded) — é o que o Swagger usa.

    O campo `username` recebe o e-mail do usuário. Após várias tentativas erradas
    seguidas a resposta passa a ser 429 (com `Retry-After`) por alguns minutos.
    """
    return _tentar_login(request, db, form.username, form.password)


@router.post("/login/json", response_model=Token)
def login_json(request: Request, dados: LoginRequest, db: DbSession) -> Token:
    """Mesmo login, recebendo JSON — mais conveniente para o front."""
    return _tentar_login(request, db, dados.email, dados.senha)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: TokenAtual) -> Response:
    """Encerra a sessão (RF02): o token usado deixa de valer imediatamente.

    O front também deve descartar o token e voltar à tela de login.
    """
    protecao.revogador_tokens.revogar(payload["jti"], float(payload["exp"]))
    logger.info("Logout: usuario=%s", payload["sub"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
