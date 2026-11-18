from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ArquivoBackup(BaseModel):
    nome: str
    tamanho_bytes: int
    criado_em: datetime


class StatusBackup(BaseModel):
    """Situação do backup. `alerta` deve ser mostrado de forma destacada à administradora."""

    habilitado: bool
    ultimo_status: Literal["nunca_executado", "ok", "erro"]
    ultima_tentativa: datetime | None
    ultimo_sucesso: datetime | None
    mensagem: str | None
    proxima_execucao: datetime | None
    alerta: bool
    motivo_alerta: str | None
    retencao: int
    arquivos: list[ArquivoBackup]


class LogoRead(BaseModel):
    personalizada: bool
