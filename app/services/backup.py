"""Backup do banco de dados (RNF03): semanal, com retenção e aviso de falha.

* PostgreSQL: ``pg_dump`` em formato custom (restaura com ``pg_restore``). A senha vai
  pela variável de ambiente ``PGPASSWORD`` — nunca na linha de comando, onde apareceria
  na lista de processos.
* SQLite (só desenvolvimento): cópia consistente pela API de backup do próprio SQLite.
* O resultado de cada tentativa fica em ``status.json`` na pasta de backups, então
  sobrevive a reinícios. ``GET /sistema/backup`` mostra o status e acende o alerta se a
  última tentativa falhou ou se passou de 8 dias sem backup.

Os arquivos têm TODOS os dados (inclusive os hashes de senha): proteja a pasta.
"""

import contextlib
import json
import logging
import os
import sqlite3
import subprocess
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.errors import ConflitoError, ErroDeNegocio
from app.schemas.sistema import ArquivoBackup, StatusBackup

logger = logging.getLogger("casa_sopa.backup")

PREFIXO = "casa_sopa_"
EXTENSOES = (".dump", ".sqlite")
ARQUIVO_DE_STATUS = "status.json"
DIAS_SEM_BACKUP_PARA_ALERTAR = 8
TIMEOUT_SEGUNDOS = 900

_trava = threading.Lock()
_agendador: BackgroundScheduler | None = None


class BackupFalhouError(ErroDeNegocio):
    status_code = 502
    detail = "Não foi possível gerar o backup."


# --- estado em disco ----------------------------------------------------------------


def _pasta() -> Path:
    pasta = Path(settings.BACKUP_DIR)
    pasta.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        pasta.chmod(0o700)  # só o dono (no Windows o chmod é ignorado)
    return pasta


def _ler_estado() -> dict[str, Any]:
    arquivo = Path(settings.BACKUP_DIR) / ARQUIVO_DE_STATUS
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (OSError, ValueError):
        return {}


def _gravar_estado(estado: dict[str, Any]) -> None:
    arquivo = _pasta() / ARQUIVO_DE_STATUS
    temporario = arquivo.with_suffix(".tmp")
    temporario.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
    os.replace(temporario, arquivo)  # troca atômica: nunca fica meio escrito


def _agora() -> datetime:
    return datetime.now(UTC)


# --- execução -----------------------------------------------------------------------------


def _limpar_senha(texto: str, senha: str | None) -> str:
    if senha:
        texto = texto.replace(senha, "***")
    return texto.strip()[:500]


def _dump_postgres(destino: Path) -> None:
    url = make_url(settings.DATABASE_URL)
    comando = [
        settings.PG_DUMP_PATH,
        "--format=custom",
        "--no-owner",
        "--no-password",
        "--file",
        str(destino),
        "--username",
        url.username or "postgres",
        "--dbname",
        url.database or "",
    ]
    if url.host:
        comando += ["--host", url.host]
    if url.port:
        comando += ["--port", str(url.port)]
    ambiente = {**os.environ, **({"PGPASSWORD": url.password} if url.password else {})}
    try:
        resultado = subprocess.run(  # noqa: S603 - comando montado só com valores da configuração
            comando,
            env=ambiente,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEGUNDOS,
            check=False,
        )
    except FileNotFoundError:
        raise BackupFalhouError(
            "pg_dump não encontrado. Instale o cliente do PostgreSQL ou configure PG_DUMP_PATH."
        ) from None
    except subprocess.TimeoutExpired:
        raise BackupFalhouError("O backup demorou demais e foi interrompido.") from None
    if resultado.returncode != 0:
        detalhe = _limpar_senha(resultado.stderr or "erro desconhecido", url.password)
        raise BackupFalhouError(f"pg_dump falhou: {detalhe}")


def _dump_sqlite(destino: Path) -> None:
    banco = make_url(settings.DATABASE_URL).database
    if not banco or banco == ":memory:":
        raise BackupFalhouError("Backup indisponível para banco SQLite em memória.")
    origem = sqlite3.connect(banco)
    copia = sqlite3.connect(destino)
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()


def _aplicar_retencao(pasta: Path) -> None:
    arquivos = sorted(
        (a for a in pasta.iterdir() if a.name.startswith(PREFIXO) and a.suffix in EXTENSOES),
        key=lambda a: a.stat().st_mtime,
        reverse=True,
    )
    for antigo in arquivos[settings.BACKUP_RETENCAO :]:
        antigo.unlink(missing_ok=True)
        logger.info("Backup antigo removido: %s", antigo.name)


def executar_backup() -> dict[str, Any]:
    """Gera um backup agora e registra o resultado. Lança ``BackupFalhouError`` se falhar."""
    if not _trava.acquire(blocking=False):
        raise ConflitoError("Já há um backup em andamento.")
    inicio = _agora()
    try:
        pasta = _pasta()
        driver = make_url(settings.DATABASE_URL).get_backend_name()
        extensao = ".sqlite" if driver == "sqlite" else ".dump"
        nome = f"{PREFIXO}{inicio:%Y%m%d_%H%M%S}{extensao}"
        parcial = pasta / (nome + ".part")
        try:
            if driver == "postgresql":
                _dump_postgres(parcial)
            elif driver == "sqlite":
                _dump_sqlite(parcial)
            else:
                raise BackupFalhouError(f"Backup não suportado para o banco «{driver}».")
            if not parcial.exists() or parcial.stat().st_size == 0:
                raise BackupFalhouError("O arquivo de backup saiu vazio.")
            final = pasta / nome
            os.replace(parcial, final)  # só vira "backup" quando está completo
        except Exception as exc:
            parcial.unlink(missing_ok=True)
            mensagem = exc.detail if isinstance(exc, BackupFalhouError) else "Erro inesperado."
            if not isinstance(exc, BackupFalhouError):
                logger.exception("Falha inesperada no backup")
            estado = _ler_estado()
            estado.update(
                ultima_tentativa=inicio.isoformat(), ultimo_status="erro", mensagem=mensagem
            )
            _gravar_estado(estado)
            logger.error("Backup falhou: %s", mensagem)
            if isinstance(exc, BackupFalhouError):
                raise
            raise BackupFalhouError(mensagem) from exc

        _aplicar_retencao(pasta)
        estado = {
            "ultima_tentativa": inicio.isoformat(),
            "ultimo_sucesso": inicio.isoformat(),
            "ultimo_status": "ok",
            "mensagem": f"Backup {nome} gerado ({final.stat().st_size} bytes).",
            "arquivo": nome,
        }
        _gravar_estado(estado)
        logger.info("Backup concluído: %s", nome)
        return estado
    finally:
        _trava.release()


def executar_backup_agendado() -> None:
    """Chamado pelo agendador: nunca deixa uma exceção derrubar a rotina."""
    try:
        executar_backup()
    except Exception:  # noqa: BLE001
        logger.exception("Backup agendado falhou")


# --- status -------------------------------------------------------------------------------------


def _parse(valor: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(valor) if valor else None
    except (TypeError, ValueError):
        return None


def _arquivos() -> list[ArquivoBackup]:
    pasta = Path(settings.BACKUP_DIR)
    if not pasta.is_dir():
        return []
    achados = sorted(
        (a for a in pasta.iterdir() if a.name.startswith(PREFIXO) and a.suffix in EXTENSOES),
        key=lambda a: a.stat().st_mtime,
        reverse=True,
    )
    return [
        ArquivoBackup(
            nome=a.name,
            tamanho_bytes=a.stat().st_size,
            criado_em=datetime.fromtimestamp(a.stat().st_mtime, UTC),
        )
        for a in achados
    ]


def _alerta(
    habilitado: bool, status: str, sucesso: datetime | None, mensagem: str | None, agora: datetime
) -> str | None:
    if not habilitado:
        if settings.ENVIRONMENT == "production":
            return "O backup automático está desligado (BACKUP_ENABLED)."
        return None
    if status == "erro":
        return f"O último backup falhou: {mensagem}"
    if sucesso is None:
        return "Nenhum backup foi realizado ainda. Use «Fazer backup agora»."
    if agora - sucesso > timedelta(days=DIAS_SEM_BACKUP_PARA_ALERTAR):
        return f"Faz mais de {DIAS_SEM_BACKUP_PARA_ALERTAR} dias que não há um backup com sucesso."
    return None


def consultar_status() -> StatusBackup:
    estado = _ler_estado()
    status = estado.get("ultimo_status", "nunca_executado")
    if status not in ("ok", "erro", "nunca_executado"):
        status = "nunca_executado"
    sucesso = _parse(estado.get("ultimo_sucesso"))
    proxima = None
    if _agendador is not None:
        job = _agendador.get_job("backup-semanal")
        proxima = getattr(job, "next_run_time", None)
    motivo = _alerta(settings.BACKUP_ENABLED, status, sucesso, estado.get("mensagem"), _agora())
    return StatusBackup(
        habilitado=settings.BACKUP_ENABLED,
        ultimo_status=status,
        ultima_tentativa=_parse(estado.get("ultima_tentativa")),
        ultimo_sucesso=sucesso,
        mensagem=estado.get("mensagem"),
        proxima_execucao=proxima,
        alerta=motivo is not None,
        motivo_alerta=motivo,
        retencao=settings.BACKUP_RETENCAO,
        arquivos=_arquivos(),
    )


# --- agendador --------------------------------------------------------------------------------


def criar_agendador() -> BackgroundScheduler:
    """Agendador com o job semanal (ainda não iniciado)."""
    agendador = BackgroundScheduler(timezone=settings.TIMEZONE)
    agendador.add_job(
        executar_backup_agendado,
        CronTrigger(
            day_of_week=settings.BACKUP_DIA_SEMANA,
            hour=settings.BACKUP_HORA,
            minute=0,
            timezone=settings.TIMEZONE,
        ),  # fmt: skip
        id="backup-semanal",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=6 * 3600,  # se o servidor estava desligado na hora, roda ao voltar
        replace_existing=True,
    )
    return agendador


def iniciar_agendador() -> None:
    global _agendador
    if not settings.BACKUP_ENABLED or _agendador is not None:
        return
    _agendador = criar_agendador()
    _agendador.start()
    logger.info(
        "Backup semanal agendado: %s às %02d:00 (%s)",
        settings.BACKUP_DIA_SEMANA,
        settings.BACKUP_HORA,
        settings.TIMEZONE,
    )


def parar_agendador() -> None:
    global _agendador
    if _agendador is not None:
        _agendador.shutdown(wait=False)
        _agendador = None
