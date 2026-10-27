"""Cupom não fiscal em PDF (RF15, RF16, RN12, RN13)."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.formatacao import formatar_moeda, formatar_telefone
from app.core.tempo import para_local
from app.schemas.pedido import PedidoRead

NOME_DA_ONG = "Casa da Sopa de Restinga"

VIAS = {
    "interna": "VIA DA ONG — USO INTERNO",
    "entregador": "VIA DO ENTREGADOR",
    "cliente": "VIA DO CLIENTE",
}
ORDEM_DAS_VIAS = ("interna", "entregador", "cliente")

_ESTILOS = getSampleStyleSheet()
_NORMAL = ParagraphStyle("normal", parent=_ESTILOS["Normal"], fontSize=9, leading=12)
_PEQUENO = ParagraphStyle(
    "pequeno", parent=_NORMAL, fontSize=7.5, leading=10, textColor=colors.grey
)
_TITULO = ParagraphStyle(
    "titulo",
    parent=_NORMAL,
    fontName="Helvetica-Bold",
    fontSize=15,
    leading=19,
    alignment=TA_CENTER,
)
_SUBTITULO = ParagraphStyle("sub", parent=_NORMAL, alignment=TA_CENTER, fontSize=9)
_VIA = ParagraphStyle(
    "via", parent=_NORMAL, fontName="Helvetica-Bold", fontSize=11, leading=14, alignment=TA_CENTER
)
_DIREITA = ParagraphStyle("dir", parent=_NORMAL, alignment=2)


def _t(texto: object) -> str:
    """Texto seguro para o PDF: escapa marcação e troca o que a fonte não desenha por '?'."""
    limpo = str(texto).encode("cp1252", "replace").decode("cp1252")
    return escape(limpo)


def _data(momento: object) -> str:
    return para_local(momento).strftime("%d/%m/%Y %H:%M")  # type: ignore[arg-type]


def _bloco_da_via(pedido: PedidoRead, via: str) -> list[object]:
    p = pedido
    elementos: list[object] = [
        Paragraph(_t(NOME_DA_ONG), _TITULO),
        Paragraph("CUPOM NÃO FISCAL", _SUBTITULO),
        Spacer(1, 3 * mm),
        Paragraph(_t(VIAS[via]), _VIA),
        HRFlowable(width="100%", thickness=0.8, color=colors.black, spaceBefore=2, spaceAfter=4),
        Paragraph(
            f"<b>Pedido nº {p.id_pedido}</b> &nbsp;·&nbsp; {_t(_data(p.data_venda))}", _NORMAL
        ),
        Paragraph(f"Situação: {_t(p.status.replace('_', ' '))}", _NORMAL),
        Paragraph(f"Vendedora: {_t(p.vendedora.nome)}", _NORMAL),
        Spacer(1, 3 * mm),
        Paragraph(f"<b>Cliente:</b> {_t(p.cliente.nome)}", _NORMAL),
        Paragraph(f"<b>Telefone:</b> {_t(formatar_telefone(p.cliente.telefone))}", _NORMAL),
        Paragraph(f"<b>Entrega:</b> {_t(p.endereco_entrega.endereco_formatado)}", _NORMAL),
    ]
    if p.endereco_entrega.referencia:
        elementos.append(
            Paragraph(f"<b>Referência:</b> {_t(p.endereco_entrega.referencia)}", _NORMAL)
        )
    elementos.append(Spacer(1, 3 * mm))

    linhas: list[list[object]] = [["Produto", "Qtd", "Preço un.", "Subtotal"]]
    for i in p.itens:
        linhas.append(
            [
                Paragraph(_t(i.nome_produto), _NORMAL),
                str(i.quantidade),
                formatar_moeda(i.preco_unitario),
                formatar_moeda(i.subtotal),
            ]
        )
    tabela = Table(linhas, colWidths=[58 * mm, 12 * mm, 24 * mm, 24 * mm], repeatRows=1)
    tabela.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )
    elementos.append(tabela)
    elementos += [
        Spacer(1, 3 * mm),
        Paragraph(
            f"<b>TOTAL: {_t(formatar_moeda(p.valor_total))}</b>",
            ParagraphStyle("total", parent=_DIREITA, fontSize=12, leading=16),
        ),
        Paragraph(f"Forma de pagamento: {_t(p.forma_pagamento)}", _DIREITA),
    ]
    if p.observacao:
        elementos += [
            Spacer(1, 2 * mm),
            Paragraph(f"<b>Observação:</b> {_t(p.observacao)}", _NORMAL),
        ]
    elementos += [
        Spacer(1, 6 * mm),
        HRFlowable(width="100%", thickness=0.4, color=colors.grey),
        Paragraph("Documento sem valor fiscal.", _PEQUENO),
    ]
    return [KeepTogether(elementos)]


def gerar_cupom_pdf(pedido: PedidoRead, via: str) -> bytes:
    """Gera o PDF com uma página por via. ``via='todas'`` junta as três."""
    vias = ORDEM_DAS_VIAS if via == "todas" else (via,)
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A5,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Pedido {pedido.id_pedido} — {NOME_DA_ONG}",
        author=NOME_DA_ONG,
    )
    paginas: list[object] = []
    for indice, nome_da_via in enumerate(vias):
        if indice:
            paginas.append(PageBreak())
        paginas += _bloco_da_via(pedido, nome_da_via)
    documento.build(paginas)
    return buffer.getvalue()
