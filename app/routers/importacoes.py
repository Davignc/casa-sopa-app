from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from app.api.deps import AdminAtual, DbSession
from app.schemas.importacao import ResultadoImportacao, TipoImportacao
from app.services import importacao

router = APIRouter(prefix="/importacoes", tags=["importações"])


@router.get("/modelo")
def modelo(tipo: TipoImportacao, _: AdminAtual) -> Response:
    return Response(
        importacao.modelo(tipo),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="modelo_{tipo}.xlsx"'},
    )


@router.post("/analisar", response_model=ResultadoImportacao)
def analisar(
    db: DbSession,
    ator: AdminAtual,
    tipo: Annotated[TipoImportacao, Form()],
    arquivo: Annotated[UploadFile, File()],
) -> ResultadoImportacao:
    conteudo = arquivo.file.read(importacao.LIMITE_BYTES + 1)
    return importacao.processar(db, conteudo, arquivo.filename or "", tipo, ator)


@router.post("/confirmar", response_model=ResultadoImportacao)
def confirmar(
    db: DbSession,
    ator: AdminAtual,
    tipo: Annotated[TipoImportacao, Form()],
    token: Annotated[str, Form(max_length=2048)],
    arquivo: Annotated[UploadFile, File()],
) -> ResultadoImportacao:
    conteudo = arquivo.file.read(importacao.LIMITE_BYTES + 1)
    return importacao.processar(db, conteudo, arquivo.filename or "", tipo, ator, token)
