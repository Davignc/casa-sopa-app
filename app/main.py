from fastapi import FastAPI

from app.core.config import settings
from app.routers import auth, usuarios

app = FastAPI(
    title="Casa de Sopa — API",
    description="Gestão de vendas de sacos de lixo da Casa de Sopa.",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(usuarios.router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.ENVIRONMENT}
