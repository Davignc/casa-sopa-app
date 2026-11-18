"""RNF03: backup semanal, retenção, falha visível e segurança da senha."""

import json
import sqlite3
import subprocess
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.core.config import settings
from app.core.errors import ConflitoError
from app.services import backup as backup_service


@pytest.fixture
def pasta(tmp_path, monkeypatch) -> Path:
    destino = tmp_path / "backups"
    monkeypatch.setattr(settings, "BACKUP_DIR", str(destino))
    monkeypatch.setattr(settings, "BACKUP_RETENCAO", 3)
    monkeypatch.setattr(settings, "BACKUP_ENABLED", True)
    return destino


@pytest.fixture
def banco_sqlite(tmp_path, monkeypatch) -> Path:
    arquivo = tmp_path / "origem.db"
    con = sqlite3.connect(arquivo)
    con.execute("CREATE TABLE cliente (id INTEGER PRIMARY KEY, nome TEXT)")
    con.execute("INSERT INTO cliente (nome) VALUES ('Dona Maria')")
    con.commit()
    con.close()
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{arquivo}")
    return arquivo


def _estado(pasta: Path) -> dict:
    return json.loads((pasta / "status.json").read_text(encoding="utf-8"))


# --- SQLite (desenvolvimento) -------------------------------------------------------------


def test_backup_sqlite_gera_copia_restauravel(pasta, banco_sqlite):
    estado = backup_service.executar_backup()

    copia = pasta / estado["arquivo"]
    assert copia.suffix == ".sqlite"
    assert sqlite3.connect(copia).execute("SELECT nome FROM cliente").fetchall() == [
        ("Dona Maria",)
    ]


def test_backup_registra_o_sucesso(pasta, banco_sqlite):
    backup_service.executar_backup()

    estado = _estado(pasta)
    assert estado["ultimo_status"] == "ok"
    assert estado["ultimo_sucesso"] == estado["ultima_tentativa"]
    assert not list(pasta.glob("*.part"))  # nada de arquivo pela metade


def test_mantem_so_os_backups_mais_recentes(pasta, banco_sqlite):
    pasta.mkdir()
    for i in range(5):
        antigo = pasta / f"casa_sopa_2020010{i}_000000.sqlite"
        antigo.write_bytes(b"x")
        agora = datetime.now(UTC).timestamp() - (10 - i) * 3600
        import os

        os.utime(antigo, (agora, agora))

    backup_service.executar_backup()

    nomes = sorted(a.name for a in pasta.glob("casa_sopa_*.sqlite"))
    assert len(nomes) == 3
    assert "casa_sopa_20200100_000000.sqlite" not in nomes  # o mais antigo saiu
    assert (pasta / "status.json").exists()  # o status não é apagado pela limpeza


def test_sqlite_em_memoria_nao_tem_backup(pasta, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite://")

    with pytest.raises(backup_service.BackupFalhouError):
        backup_service.executar_backup()

    assert _estado(pasta)["ultimo_status"] == "erro"


def test_banco_nao_suportado_falha_com_mensagem(pasta, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "mysql+pymysql://u:p@h/db")

    with pytest.raises(backup_service.BackupFalhouError) as erro:
        backup_service.executar_backup()

    assert "não suportado" in erro.value.detail


# --- PostgreSQL (pg_dump simulado) --------------------------------------------------------------


@pytest.fixture
def postgres(monkeypatch):
    monkeypatch.setattr(
        settings, "DATABASE_URL", "postgresql+psycopg://dono:S3gredo!@db.interno:5433/casa_sopa"
    )


def _fake_pg_dump(chamadas, *, codigo=0, stderr=""):
    def executar(comando, **kwargs):
        chamadas.append((comando, kwargs))
        if codigo == 0:
            Path(comando[comando.index("--file") + 1]).write_bytes(b"PGDMP-conteudo")
        return subprocess.CompletedProcess(comando, codigo, stdout="", stderr=stderr)

    return executar


def test_pg_dump_recebe_os_parametros_certos(pasta, postgres, monkeypatch):
    chamadas = []
    monkeypatch.setattr(subprocess, "run", _fake_pg_dump(chamadas))

    estado = backup_service.executar_backup()

    comando, kwargs = chamadas[0]
    assert comando[0] == "pg_dump"
    assert "--format=custom" in comando
    assert comando[comando.index("--host") + 1] == "db.interno"
    assert comando[comando.index("--port") + 1] == "5433"
    assert comando[comando.index("--username") + 1] == "dono"
    assert comando[comando.index("--dbname") + 1] == "casa_sopa"
    assert estado["arquivo"].endswith(".dump")
    assert (pasta / estado["arquivo"]).read_bytes() == b"PGDMP-conteudo"


def test_a_senha_nunca_vai_na_linha_de_comando(pasta, postgres, monkeypatch):
    chamadas = []
    monkeypatch.setattr(subprocess, "run", _fake_pg_dump(chamadas))

    backup_service.executar_backup()

    comando, kwargs = chamadas[0]
    assert not any("S3gredo!" in parte for parte in comando)
    assert kwargs["env"]["PGPASSWORD"] == "S3gredo!"
    assert "--no-password" in comando
    assert kwargs["timeout"] > 0


def test_falha_do_pg_dump_e_registrada_sem_vazar_a_senha(pasta, postgres, monkeypatch):
    erro = "pg_dump: erro: falha na conexão: senha S3gredo! incorreta"
    monkeypatch.setattr(subprocess, "run", _fake_pg_dump([], codigo=1, stderr=erro))

    with pytest.raises(backup_service.BackupFalhouError) as excecao:
        backup_service.executar_backup()

    assert "S3gredo!" not in excecao.value.detail
    assert "***" in excecao.value.detail
    estado = _estado(pasta)
    assert estado["ultimo_status"] == "erro"
    assert "S3gredo!" not in estado["mensagem"]
    assert not list(pasta.glob("casa_sopa_*"))  # não sobra arquivo de backup falho


def test_pg_dump_ausente_da_uma_mensagem_clara(pasta, postgres, monkeypatch):
    def nao_existe(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", nao_existe)

    with pytest.raises(backup_service.BackupFalhouError) as erro:
        backup_service.executar_backup()

    assert "PG_DUMP_PATH" in erro.value.detail


def test_timeout_do_pg_dump_e_tratado(pasta, postgres, monkeypatch):
    def demora(*a, **k):
        raise subprocess.TimeoutExpired("pg_dump", 1)

    monkeypatch.setattr(subprocess, "run", demora)

    with pytest.raises(backup_service.BackupFalhouError) as erro:
        backup_service.executar_backup()

    assert "demorou" in erro.value.detail


def test_arquivo_vazio_nao_conta_como_backup(pasta, postgres, monkeypatch):
    def vazio(comando, **kwargs):
        Path(comando[comando.index("--file") + 1]).write_bytes(b"")
        return subprocess.CompletedProcess(comando, 0, "", "")

    monkeypatch.setattr(subprocess, "run", vazio)

    with pytest.raises(backup_service.BackupFalhouError):
        backup_service.executar_backup()

    assert not list(pasta.glob("casa_sopa_*"))


def test_falha_nao_apaga_o_ultimo_sucesso(pasta, postgres, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_pg_dump([]))
    backup_service.executar_backup()
    sucesso = _estado(pasta)["ultimo_sucesso"]
    monkeypatch.setattr(subprocess, "run", _fake_pg_dump([], codigo=1, stderr="caiu"))

    with pytest.raises(backup_service.BackupFalhouError):
        backup_service.executar_backup()

    estado = _estado(pasta)
    assert estado["ultimo_status"] == "erro"
    assert estado["ultimo_sucesso"] == sucesso


def test_nao_roda_dois_backups_ao_mesmo_tempo(pasta, banco_sqlite):
    backup_service._trava.acquire()
    try:
        with pytest.raises(ConflitoError):
            backup_service.executar_backup()
    finally:
        backup_service._trava.release()
    backup_service.executar_backup()  # liberou: roda normal


def test_a_trava_e_liberada_mesmo_quando_falha(pasta, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite://")
    with pytest.raises(backup_service.BackupFalhouError):
        backup_service.executar_backup()

    assert backup_service._trava.acquire(blocking=False)
    backup_service._trava.release()


def test_rotina_agendada_nunca_propaga_excecao(pasta, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite://")

    backup_service.executar_backup_agendado()  # não pode lançar


# --- status e alerta ---------------------------------------------------------------------------


def test_status_antes_do_primeiro_backup_pede_a_primeira_execucao(pasta):
    status = backup_service.consultar_status()

    assert status.ultimo_status == "nunca_executado"
    assert status.alerta is True
    assert "Nenhum backup" in status.motivo_alerta
    assert status.arquivos == []


def test_status_ok_nao_tem_alerta(pasta, banco_sqlite):
    backup_service.executar_backup()

    status = backup_service.consultar_status()

    assert status.ultimo_status == "ok"
    assert status.alerta is False
    assert status.motivo_alerta is None
    assert len(status.arquivos) == 1
    assert status.retencao == 3


def test_status_apos_falha_acende_o_alerta(pasta, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite://")
    with pytest.raises(backup_service.BackupFalhouError):
        backup_service.executar_backup()

    status = backup_service.consultar_status()

    assert status.alerta is True
    assert "falhou" in status.motivo_alerta


def test_backup_antigo_demais_acende_o_alerta(pasta):
    pasta.mkdir()
    velho = (datetime.now(UTC) - timedelta(days=9)).isoformat()
    (pasta / "status.json").write_text(
        json.dumps({"ultimo_status": "ok", "ultimo_sucesso": velho, "ultima_tentativa": velho})
    )

    status = backup_service.consultar_status()

    assert status.alerta is True
    assert "8 dias" in status.motivo_alerta


def test_backup_de_ontem_nao_alerta(pasta):
    pasta.mkdir()
    ontem = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    (pasta / "status.json").write_text(
        json.dumps({"ultimo_status": "ok", "ultimo_sucesso": ontem, "ultima_tentativa": ontem})
    )

    assert backup_service.consultar_status().alerta is False


def test_arquivo_de_status_corrompido_nao_derruba(pasta):
    pasta.mkdir()
    (pasta / "status.json").write_text("{isso nao e json")

    assert backup_service.consultar_status().ultimo_status == "nunca_executado"


def test_desligado_em_producao_avisa_e_em_desenvolvimento_nao(pasta, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_ENABLED", False)

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert backup_service.consultar_status().alerta is False

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    status = backup_service.consultar_status()
    assert status.alerta is True
    assert "desligado" in status.motivo_alerta


# --- agendador ---------------------------------------------------------------------------------


def test_agendador_roda_uma_vez_por_semana_no_horario_configurado(pasta, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_DIA_SEMANA", "sat")
    monkeypatch.setattr(settings, "BACKUP_HORA", 2)

    agendador = backup_service.criar_agendador()
    job = agendador.get_job("backup-semanal")

    campos = {c.name: str(c) for c in job.trigger.fields}
    assert campos["day_of_week"] == "sat"
    assert campos["hour"] == "2"
    assert campos["minute"] == "0"
    assert str(job.trigger.timezone) == settings.TIMEZONE
    assert job.max_instances == 1
    assert job.coalesce is True


def test_agendador_nao_inicia_com_backup_desligado(pasta, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_ENABLED", False)
    monkeypatch.setattr(backup_service, "_agendador", None)

    backup_service.iniciar_agendador()

    assert backup_service._agendador is None


def test_agendador_inicia_e_para(pasta, monkeypatch):
    monkeypatch.setattr(backup_service, "_agendador", None)

    backup_service.iniciar_agendador()
    try:
        assert backup_service._agendador is not None
        assert backup_service._agendador.running
        assert backup_service.consultar_status().proxima_execucao is not None
        backup_service.iniciar_agendador()  # chamar de novo não duplica
    finally:
        backup_service.parar_agendador()

    assert backup_service._agendador is None


def test_thread_do_agendador_nao_vaza_entre_testes():
    assert not [t for t in threading.enumerate() if "APScheduler" in t.name]


# --- rotas -------------------------------------------------------------------------------------


def test_rotas_exigem_login(client):
    assert client.get("/sistema/backup").status_code == 401
    assert client.post("/sistema/backup").status_code == 401


def test_rotas_sao_so_da_administradora(client, headers_vendedora):
    assert client.get("/sistema/backup", headers=headers_vendedora).status_code == 403
    assert client.post("/sistema/backup", headers=headers_vendedora).status_code == 403


def test_admin_ve_o_status(client, headers_admin, pasta):
    corpo = client.get("/sistema/backup", headers=headers_admin).json()

    assert corpo["ultimo_status"] == "nunca_executado"
    assert corpo["alerta"] is True
    assert {
        "habilitado",
        "arquivos",
        "retencao",
        "motivo_alerta",
        "proxima_execucao",
    } <= corpo.keys()


def test_admin_faz_backup_agora(client, headers_admin, pasta, banco_sqlite):
    resposta = client.post("/sistema/backup", headers=headers_admin)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["ultimo_status"] == "ok"
    assert corpo["alerta"] is False
    assert len(corpo["arquivos"]) == 1


def test_falha_no_backup_manual_retorna_502_com_o_motivo(client, headers_admin, pasta, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite://")

    resposta = client.post("/sistema/backup", headers=headers_admin)

    assert resposta.status_code == 502
    assert "memória" in resposta.json()["detail"]
    assert client.get("/sistema/backup", headers=headers_admin).json()["alerta"] is True


def test_rota_nao_expoe_o_conteudo_dos_backups(client, headers_admin, pasta, banco_sqlite):
    client.post("/sistema/backup", headers=headers_admin)

    corpo = client.get("/sistema/backup", headers=headers_admin).json()

    assert set(corpo["arquivos"][0]) == {"nome", "tamanho_bytes", "criado_em"}
