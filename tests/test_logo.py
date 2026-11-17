"""Troca de logo pela administradora: segurança do envio e uso no cupom."""

import io
import struct
import zlib
from io import BytesIO

import pytest
from PIL import Image
from pypdf import PdfReader

from app.core.config import settings
from app.services import logo as logo_service


@pytest.fixture(autouse=True)
def pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path / "uploads"))


def imagem(formato="PNG", tamanho=(300, 200), cor=(200, 30, 30, 255), modo="RGBA") -> bytes:
    saida = io.BytesIO()
    Image.new(modo, tamanho, cor if modo == "RGBA" else cor[:3]).save(saida, format=formato)
    return saida.getvalue()


def enviar(client, headers, conteudo, nome="logo.png", tipo="image/png"):
    return client.post("/sistema/logo", files={"arquivo": (nome, conteudo, tipo)}, headers=headers)


# --- leitura pública -------------------------------------------------------------------------


def test_logo_e_publica_e_vem_a_padrao(client):
    resposta = client.get("/sistema/logo")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "image/png"
    assert resposta.content == logo_service.LOGO_PADRAO.read_bytes()
    assert Image.open(BytesIO(resposta.content)).format == "PNG"


def test_logo_usa_etag_e_responde_304_quando_nao_mudou(client):
    primeira = client.get("/sistema/logo")

    igual = client.get("/sistema/logo", headers={"If-None-Match": primeira.headers["etag"]})
    outra = client.get("/sistema/logo", headers={"If-None-Match": '"outro"'})

    assert igual.status_code == 304
    assert igual.content == b""
    assert outra.status_code == 200
    assert primeira.headers["cache-control"] == "no-cache"


# --- troca ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("rota", ["post", "delete"])
def test_trocar_e_restaurar_exigem_login(client, rota):
    resposta = (
        client.post("/sistema/logo", files={"arquivo": ("l.png", imagem(), "image/png")})
        if rota == "post"
        else client.delete("/sistema/logo")
    )

    assert resposta.status_code == 401


def test_vendedora_nao_troca_a_logo(client, headers_vendedora):
    assert enviar(client, headers_vendedora, imagem()).status_code == 403
    assert client.delete("/sistema/logo", headers=headers_vendedora).status_code == 403
    assert client.get("/sistema/logo/situacao", headers=headers_vendedora).status_code == 403


def test_admin_troca_a_logo_e_ela_passa_a_valer_para_todos(client, headers_admin):
    resposta = enviar(client, headers_admin, imagem(cor=(0, 128, 0, 255)))

    assert resposta.status_code == 200
    assert resposta.json() == {"personalizada": True}
    publica = Image.open(BytesIO(client.get("/sistema/logo").content)).convert("RGBA")
    assert publica.getpixel((5, 5)) == (0, 128, 0, 255)
    assert client.get("/sistema/logo/situacao", headers=headers_admin).json() == {
        "personalizada": True
    }


def test_trocar_muda_o_etag(client, headers_admin):
    antes = client.get("/sistema/logo").headers["etag"]

    enviar(client, headers_admin, imagem())

    assert client.get("/sistema/logo").headers["etag"] != antes


def test_restaurar_volta_para_a_padrao(client, headers_admin):
    enviar(client, headers_admin, imagem())

    resposta = client.delete("/sistema/logo", headers=headers_admin)

    assert resposta.json() == {"personalizada": False}
    assert client.get("/sistema/logo").content == logo_service.LOGO_PADRAO.read_bytes()
    assert client.delete("/sistema/logo", headers=headers_admin).status_code == 200  # idempotente


@pytest.mark.parametrize("formato", ["PNG", "JPEG", "WEBP"])
def test_aceita_png_jpg_e_webp(client, headers_admin, formato):
    modo = "RGB" if formato == "JPEG" else "RGBA"

    assert enviar(client, headers_admin, imagem(formato, modo=modo)).status_code == 200


def test_o_arquivo_salvo_e_sempre_um_png_pequeno(client, headers_admin):
    enviar(client, headers_admin, imagem("JPEG", tamanho=(3000, 1500), modo="RGB"))

    salvo = Image.open(BytesIO(client.get("/sistema/logo").content))

    assert salvo.format == "PNG"
    assert max(salvo.size) == 512
    assert salvo.size == (512, 256)  # mantém a proporção


def test_metadados_do_arquivo_original_sao_descartados(client, headers_admin):
    original = Image.new("RGB", (100, 100), "red")
    exif = Image.Exif()
    exif[0x010E] = "SEGREDO-NO-EXIF"
    saida = io.BytesIO()
    original.save(saida, format="JPEG", exif=exif)

    enviar(client, headers_admin, saida.getvalue(), nome="foto.jpg", tipo="image/jpeg")

    assert b"SEGREDO-NO-EXIF" not in client.get("/sistema/logo").content


# --- recusas --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("conteudo", "nome", "tipo"),
    [
        (
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            "logo.svg",
            "image/svg+xml",
        ),
        (b"%PDF-1.4 conteudo", "logo.pdf", "application/pdf"),
        (b"<?php echo 1; ?>", "logo.png", "image/png"),  # extensão e tipo mentem
        (b"GIF89a" + b"\x00" * 50, "logo.gif", "image/gif"),
        (b"nao e imagem", "logo.png", "image/png"),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 20, "logo.png", "image/png"),  # cabeçalho PNG truncado
    ],
)
def test_arquivo_que_nao_e_imagem_aceita_e_recusado(client, headers_admin, conteudo, nome, tipo):
    resposta = enviar(client, headers_admin, conteudo, nome, tipo)

    assert resposta.status_code == 422
    assert (
        client.get("/sistema/logo").content == logo_service.LOGO_PADRAO.read_bytes()
    )  # nada mudou


def test_gif_valido_tambem_e_recusado(client, headers_admin):
    assert (
        enviar(client, headers_admin, imagem("GIF", modo="RGB"), "l.gif", "image/gif").status_code
        == 422
    )


def test_o_conteudo_manda_nao_o_content_type(client, headers_admin):
    """Um GIF anunciado como PNG continua sendo recusado, e um PNG anunciado como texto passa."""
    assert (
        enviar(client, headers_admin, imagem("GIF", modo="RGB"), "l.png", "image/png").status_code
        == 422
    )
    assert enviar(client, headers_admin, imagem(), "l.txt", "text/plain").status_code == 200


def test_arquivo_vazio_e_recusado(client, headers_admin):
    assert enviar(client, headers_admin, b"").status_code == 422


def test_arquivo_acima_de_2mb_retorna_413(client, headers_admin):
    resposta = enviar(client, headers_admin, b"\x89PNG" + b"0" * (2 * 1024 * 1024 + 10))

    assert resposta.status_code == 413
    assert "2 MB" in resposta.json()["detail"]


def test_imagem_com_dimensao_gigante_e_recusada_sem_ser_carregada(client, headers_admin):
    """PNG minúsculo que DECLARA 30000x30000 px: a 'bomba de descompressão'."""

    def bloco(tipo, dados):
        corpo = tipo + dados
        return struct.pack(">I", len(dados)) + corpo + struct.pack(">I", zlib.crc32(corpo))

    cabecalho = struct.pack(">IIBBBBB", 30000, 30000, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + bloco(b"IHDR", cabecalho)
        + bloco(b"IDAT", zlib.compress(b"\x00"))
        + bloco(b"IEND", b"")
    )

    resposta = enviar(client, headers_admin, png)

    assert resposta.status_code == 422
    assert "grande demais" in resposta.json()["detail"]


def test_imagem_minuscula_e_recusada(client, headers_admin):
    assert enviar(client, headers_admin, imagem(tamanho=(8, 8))).status_code == 422


def test_sem_arquivo_no_pedido_retorna_422(client, headers_admin):
    assert client.post("/sistema/logo", headers=headers_admin).status_code == 422


def test_o_nome_enviado_nao_define_onde_salvar(client, headers_admin, tmp_path):
    enviar(client, headers_admin, imagem(), nome="../../../etc/passwd.png")

    arquivos = sorted(p.name for p in (tmp_path / "uploads").iterdir())
    assert arquivos == ["logo.png"]
    assert not (tmp_path / "etc").exists()


# --- cupom ------------------------------------------------------------------------------------------


@pytest.fixture
def pedido(client, headers_admin):
    cliente = client.post(
        "/clientes",
        json={"nome": "Ana", "telefone": "16999990001", "enderecos": [
            {"cep": "14400-000", "cidade": "Franca", "bairro": "Centro", "tipo_logradouro": "Rua",
             "nome_logradouro": "X", "numero": "1"}]},
        headers=headers_admin,
    ).json()  # fmt: skip
    produto = client.post(
        "/produtos",
        json={
            "nome": "Saco",
            "descricao": "d",
            "preco_unitario": "10",
            "estoque_inicial": 5,
            "estoque_minimo": 1,
        },
        headers=headers_admin,
    ).json()
    return client.post(
        "/pedidos",
        json={"id_cliente": cliente["id_cliente"], "id_endereco": cliente["enderecos"][0]["id_endereco"],
              "forma_pagamento": "pix", "itens": [{"id_produto": produto["id_produto"], "quantidade": 1}]},
        headers=headers_admin,
    ).json()["id_pedido"]  # fmt: skip


def _imagens_do_pdf(resposta):
    leitor = PdfReader(BytesIO(resposta.content))
    return [len(pagina.images) for pagina in leitor.pages]


def test_cupom_traz_a_logo_em_cada_via(client, headers_admin, pedido):
    resposta = client.get(f"/pedidos/{pedido}/cupom", headers=headers_admin)

    assert resposta.status_code == 200
    assert _imagens_do_pdf(resposta) == [1, 1, 1]
    assert (
        "Casa da Sopa de Restinga" in PdfReader(BytesIO(resposta.content)).pages[0].extract_text()
    )


def test_cupom_usa_a_logo_que_a_administradora_enviou(client, headers_admin, pedido):
    enviar(client, headers_admin, imagem(cor=(0, 0, 255, 255), tamanho=(400, 400)))

    resposta = client.get(f"/pedidos/{pedido}/cupom?via=cliente", headers=headers_admin)

    leitor = PdfReader(BytesIO(resposta.content))
    imagem_do_pdf = leitor.pages[0].images[0].image.convert("RGB")
    assert imagem_do_pdf.getpixel((10, 10)) == (0, 0, 255)


def test_cupom_a_logo_nao_infla_o_pdf_com_tres_vias(client, headers_admin, pedido):
    uma = client.get(f"/pedidos/{pedido}/cupom?via=cliente", headers=headers_admin).content
    tres = client.get(f"/pedidos/{pedido}/cupom", headers=headers_admin).content

    assert len(tres) < len(uma) * 2  # a mesma imagem é reaproveitada, não repetida


def test_cupom_sem_logo_continua_funcionando():
    from app.schemas.pedido import PedidoRead
    from app.services import cupom

    pedido = PedidoRead.model_validate(
        {"id_pedido": 1, "status": "em_aberto", "data_venda": "2026-10-01T12:00:00Z", "forma_pagamento": "pix",
         "observacao": None, "data_pagamento": None, "valor_total": "10.00", "total_produtos": 1,
         "cliente": {"id_cliente": 1, "nome": "Ana", "telefone": "16999990001"},
         "vendedora": {"id_usuario": 1, "nome": "Maria"},
         "endereco_entrega": {"id_endereco": 1, "endereco_formatado": "Rua X, 1", "apelido": None, "referencia": ""},
         "itens": [{"id_produto": 1, "nome_produto": "Saco", "quantidade": 1, "preco_unitario": "10.00", "subtotal": "10.00"}]}
    )  # fmt: skip

    assert cupom.gerar_cupom_pdf(pedido, "cliente").startswith(b"%PDF")
