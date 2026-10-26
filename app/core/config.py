from functools import lru_cache
from typing import Literal

from pydantic import field_validator
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
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_forte(cls, v: str) -> str:
        if len(v) < SECRET_KEY_TAMANHO_MINIMO:
            raise ValueError(
                f"SECRET_KEY precisa ter ao menos {SECRET_KEY_TAMANHO_MINIMO} caracteres. "
                'Gere com: uv run python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return v


@lru_cache
def get_settings() -> Settings:
    """Instância única de Settings (evita reler o .env a cada chamada)."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
