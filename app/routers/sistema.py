import logging
from typing import Annotated

from fastapi import APIRouter, File, Request, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.api.deps import AdminAtual
from app.core.errors import ArquivoGrandeError
from app.schemas.sistema import LogoRead, StatusBackup
from app.services import backup as backup_service
from app.services import logo as logo_service

logger = logging.getLogger("casa_sopa.sistema")

router = APIRouter(prefix="/sistema", tags=["sistema"])


@router.get("/backup", response_model=StatusBackup)
def status_do_backup(_admin: AdminAtual) -> StatusBackup:
    """Situação do backup semanal (RNF03). Somente a administradora.

    Se `alerta` for verdadeiro, mostre `motivo_alerta` em destaque: a última tentativa falhou,
    não há backup recente ou o backup automático está desligado.
    """
    return backup_service.consultar_status()


@router.post("/backup", response_model=StatusBackup, status_code=status.HTTP_201_CREATED)
def fazer_backup_agora(_admin: AdminAtual) -> StatusBackup:
    """Gera um backup imediatamente. Retorna 502 com o motivo se falhar."""
    backup_service.executar_backup()
    return backup_service.consultar_status()


@router.get(
    "/logo",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}, "description": "Logo da ONG"}},
)
def ler_logo(request: Request) -> Response:
    """Logo atual da ONG. **Pública**: a tela de login precisa dela antes de entrar."""
    conteudo = logo_service.obter_logo()
    etiqueta = logo_service.etag(conteudo)
    cabecalhos = {"ETag": etiqueta, "Cache-Control": "no-cache"}  # revalida; 304 se não mudou
    if request.headers.get("if-none-match") == etiqueta:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=cabecalhos)
    return Response(content=conteudo, media_type="image/png", headers=cabecalhos)


@router.post("/logo", response_model=LogoRead)
async def trocar_logo(
    admin: AdminAtual,
    arquivo: Annotated[UploadFile, File(description="PNG, JPG ou WebP, até 2 MB")],
) -> LogoRead:
    """Troca a logo da ONG (somente a administradora). Vale em todo o sistema e no cupom.

    Aceita PNG, JPG ou WebP de até 2 MB. A imagem é conferida pelo conteúdo e regravada como PNG.
    """
    # Lê só um pouco além do limite: nunca carrega um arquivo gigante inteiro na memória.
    dados = await arquivo.read(logo_service.TAMANHO_MAXIMO_BYTES + 1)
    if len(dados) > logo_service.TAMANHO_MAXIMO_BYTES:
        raise ArquivoGrandeError("A imagem passa de 2 MB. Envie uma menor.")
    await run_in_threadpool(logo_service.salvar_logo, dados)  # Pillow é trabalho de CPU
    logger.info("Logo trocada por usuario=%s", admin.id_usuario)
    return LogoRead(personalizada=True)


@router.delete("/logo", response_model=LogoRead)
def restaurar_logo(admin: AdminAtual) -> LogoRead:
    """Volta para a logo padrão do sistema."""
    logo_service.remover_logo()
    logger.info("Logo restaurada por usuario=%s", admin.id_usuario)
    return LogoRead(personalizada=False)


@router.get("/logo/situacao", response_model=LogoRead)
def situacao_da_logo(_admin: AdminAtual) -> LogoRead:
    """Informa se há uma logo personalizada (a tela de configurações usa para o botão Restaurar)."""
    return LogoRead(personalizada=logo_service.eh_personalizada())
