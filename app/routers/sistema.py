from fastapi import APIRouter, status

from app.api.deps import AdminAtual
from app.schemas.sistema import StatusBackup
from app.services import backup as backup_service

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
