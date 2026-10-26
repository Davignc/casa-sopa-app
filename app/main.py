from fastapi import FastAPI

from app.core.config import settings
from app.core.errors import registrar_handlers
from app.routers import auth, usuarios

em_producao = settings.ENVIRONMENT == "production"

app = FastAPI(
    title="Casa da Sopa de Restinga — API",
    description="Gestão de clientes, produtos, estoque e pedidos da Casa da Sopa de Restinga.",
    version="0.1.0",
    # Em produção a documentação interativa fica desligada.
    docs_url=None if em_producao else "/docs",
    redoc_url=None if em_producao else "/redoc",
    openapi_url=None if em_producao else "/openapi.json",
)

registrar_handlers(app)

app.include_router(auth.router)
app.include_router(usuarios.router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.ENVIRONMENT}
