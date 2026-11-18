"""Logo da ONG: a administradora troca pela tela; vale no sistema todo e no cupom.

Segurança do envio:
* o tipo é decidido pelo CONTEÚDO (Pillow abre o arquivo), nunca pelo nome ou pelo
  Content-Type que o navegador informa;
* só PNG, JPEG e WebP. SVG é recusado (pode carregar script);
* limite de tamanho do arquivo e de dimensões (protege contra "bomba de descompressão");
* a imagem é redesenhada e salva como PNG novo: metadados, EXIF e qualquer coisa
  escondida dentro do arquivo original são descartados.
"""

import contextlib
import hashlib
import io
import os
import warnings
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.errors import ArquivoGrandeError, RegraInvalidaError

TAMANHO_MAXIMO_BYTES = 2 * 1024 * 1024
LADO_MAXIMO_ENVIADO = 4000  # pixels
LADO_FINAL = 512
FORMATOS_ACEITOS = {"PNG", "JPEG", "WEBP"}
LOGO_PADRAO = Path(__file__).resolve().parent.parent / "assets" / "logo-padrao.png"


def _caminho_personalizado() -> Path:
    return Path(settings.UPLOADS_DIR) / "logo.png"


def obter_logo() -> bytes:
    """A logo enviada pela administradora, ou a padrão do sistema."""
    personalizada = _caminho_personalizado()
    try:
        return personalizada.read_bytes()
    except OSError:
        return LOGO_PADRAO.read_bytes()


def eh_personalizada() -> bool:
    return _caminho_personalizado().is_file()


def etag(conteudo: bytes) -> str:
    return '"' + hashlib.sha256(conteudo).hexdigest()[:32] + '"'


def processar(dados: bytes) -> bytes:
    """Valida a imagem enviada e devolve um PNG limpo (máx. 512 px de lado)."""
    if not dados:
        raise RegraInvalidaError("Nenhum arquivo foi enviado.")
    if len(dados) > TAMANHO_MAXIMO_BYTES:
        raise ArquivoGrandeError("A imagem passa de 2 MB. Envie uma menor.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            imagem = Image.open(io.BytesIO(dados))
            if imagem.format not in FORMATOS_ACEITOS:
                raise RegraInvalidaError("Formato não aceito. Envie uma imagem PNG, JPG ou WebP.")
            largura, altura = imagem.size
            if max(largura, altura) > LADO_MAXIMO_ENVIADO:
                raise RegraInvalidaError(
                    f"A imagem é grande demais (máximo {LADO_MAXIMO_ENVIADO} px de lado)."
                )
            if min(largura, altura) < 16:
                raise RegraInvalidaError("A imagem é pequena demais.")
            imagem.load()
    except RegraInvalidaError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        # O Pillow recusa ao ABRIR, antes de decodificar um único pixel.
        raise RegraInvalidaError(
            f"A imagem é grande demais (máximo {LADO_MAXIMO_ENVIADO} px de lado)."
        ) from None
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ):
        raise RegraInvalidaError("O arquivo não é uma imagem válida.") from None

    limpa = imagem.convert("RGBA")
    limpa.thumbnail((LADO_FINAL, LADO_FINAL), Image.Resampling.LANCZOS)
    saida = io.BytesIO()
    limpa.save(saida, format="PNG", optimize=True)
    return saida.getvalue()


def salvar_logo(dados: bytes) -> None:
    png = processar(dados)
    destino = _caminho_personalizado()
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".tmp")
    temporario.write_bytes(png)
    os.replace(temporario, destino)  # troca atômica: nunca fica meio escrita


def remover_logo() -> None:
    """Volta para a logo padrão."""
    with contextlib.suppress(FileNotFoundError):
        _caminho_personalizado().unlink()
