from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import registrar_handlers
from app.routers import (
    auth,
    clientes,
    estoque,
    pedidos,
    produtos,
    relatorios,
    sistema,
    usuarios,
)
from app.services import backup as backup_service

em_producao = settings.ENVIRONMENT == "production"


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
    backup_service.iniciar_agendador()  # só liga se BACKUP_ENABLED=true
    try:
        yield
    finally:
        backup_service.parar_agendador()


app = FastAPI(
    title="Casa da Sopa de Restinga — API",
    description="Gestão de clientes, produtos, estoque e pedidos da Casa da Sopa de Restinga.",
    version="1.0.0",
    lifespan=ciclo_de_vida,
    # Em produção a documentação interativa fica desligada.
    docs_url=None if em_producao else "/docs",
    redoc_url=None if em_producao else "/redoc",
    openapi_url=None if em_producao else "/openapi.json",
)

registrar_handlers(app)

if settings.cors_origins_lista:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_lista,  # só as origens listadas, nunca "*"
        allow_credentials=False,  # o token vai no cabeçalho Authorization, não em cookie
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition", "Retry-After"],
    )


@app.middleware("http")
async def cabecalhos_de_seguranca(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    resposta = await call_next(request)
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("X-Frame-Options", "DENY")
    resposta.headers.setdefault("Referrer-Policy", "no-referrer")
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
        resposta.headers.setdefault("Cache-Control", "no-store")  # dados internos: não cachear
    return resposta


app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(clientes.router)
app.include_router(produtos.router)
app.include_router(estoque.router)
app.include_router(pedidos.router)
app.include_router(relatorios.router)
app.include_router(sistema.router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.ENVIRONMENT}
