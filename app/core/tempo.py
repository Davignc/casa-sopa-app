"""Datas e fusos.

O banco guarda instantes em UTC; "hoje", "último mês" e os limites de período dos
relatórios valem no fuso local da ONG (``settings.TIMEZONE``).
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings

FUSO = ZoneInfo(settings.TIMEZONE)


def agora_utc() -> datetime:
    return datetime.now(UTC)


def hoje_local() -> date:
    return datetime.now(FUSO).date()


def inicio_do_dia_utc(dia: date) -> datetime:
    """00:00 do dia, no fuso local, convertido para UTC."""
    return datetime.combine(dia, time.min, tzinfo=FUSO).astimezone(UTC)


def fim_do_dia_exclusivo_utc(dia: date) -> datetime:
    """00:00 do dia seguinte (limite superior exclusivo do dia informado)."""
    return inicio_do_dia_utc(dia + timedelta(days=1))


def para_local(momento: datetime) -> datetime:
    """Converte para o fuso local; datas sem fuso (SQLite) são tratadas como UTC."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    return momento.astimezone(FUSO)
