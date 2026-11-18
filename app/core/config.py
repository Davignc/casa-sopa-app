from functools import lru_cache
from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRET_KEY_TAMANHO_MINIMO = 32


class Settings(BaseSettings):
    """Configurações da aplicação, carregadas do .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str

    SECRET_KEY: str
    # Só algoritmos HMAC: impede configurar "none" ou trocar por chave pública por engano.
    ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1)

    # Bloqueio de login (RF01, critério 4): após N falhas, o cliente espera M minutos.
    LOGIN_MAX_TENTATIVAS: int = Field(default=5, ge=1)
    LOGIN_BLOQUEIO_MINUTOS: int = Field(default=15, ge=1)

    # Custo do bcrypt. 12 é o padrão seguro; só baixe (mín. 4) em testes.
    BCRYPT_ROUNDS: int = Field(default=12, ge=4, le=16)

    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Fuso usado para "hoje", "último mês" e limites de período nos relatórios.
    TIMEZONE: str = "America/Sao_Paulo"

    # Origens do front-end autorizadas a chamar a API (CORS), separadas por vírgula.
    # Vazio = nenhuma (a API só aceita chamadas do mesmo domínio).
    CORS_ORIGINS: str = ""

    # Arquivos enviados pela administradora (logo da ONG).
    UPLOADS_DIR: str = "uploads"

    # Backup semanal do banco (RNF03).
    BACKUP_ENABLED: bool = False
    BACKUP_DIR: str = "backups"
    BACKUP_RETENCAO: int = Field(default=8, ge=1)  # quantos backups manter
    BACKUP_DIA_SEMANA: Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"] = "sun"
    BACKUP_HORA: int = Field(default=3, ge=0, le=23)
    PG_DUMP_PATH: str = "pg_dump"

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_forte(cls, v: str) -> str:
        if len(v) < SECRET_KEY_TAMANHO_MINIMO:
            raise ValueError(
                f"SECRET_KEY precisa ter ao menos {SECRET_KEY_TAMANHO_MINIMO} caracteres. "
                'Gere com: uv run python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return v

    @field_validator("TIMEZONE")
    @classmethod
    def _fuso_valido(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValueError(f"TIMEZONE inválido: {v!r}") from exc
        return v

    @property
    def cors_origins_lista(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _custo_bcrypt_minimo_em_producao(self) -> Self:
        if self.ENVIRONMENT == "production" and self.BCRYPT_ROUNDS < 10:
            raise ValueError("BCRYPT_ROUNDS precisa ser ao menos 10 em produção.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Instância única de Settings (evita reler o .env a cada chamada)."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
