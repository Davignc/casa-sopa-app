"""Formatação para exibição (cupom, listagens). Os dados são gravados "crus"."""


def formatar_cep(cep: str) -> str:
    return f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 and cep.isdigit() else cep


def formatar_telefone(telefone: str) -> str:
    if len(telefone) == 11 and telefone.isdigit():
        return f"({telefone[:2]}) {telefone[2:7]}-{telefone[7:]}"
    if len(telefone) == 10 and telefone.isdigit():
        return f"({telefone[:2]}) {telefone[2:6]}-{telefone[6:]}"
    return telefone


def formatar_endereco(
    *,
    tipo_logradouro: str,
    nome_logradouro: str,
    numero: str,
    complemento: str,
    bairro: str,
    cidade: str,
    cep: str,
) -> str:
    """Ex.: 'Avenida Presidente Vargas, 100, apto 2 - Centro, Franca - CEP 14400-000'."""
    rua = f"{tipo_logradouro} {nome_logradouro}, {numero}"
    if complemento:
        rua += f", {complemento}"
    return f"{rua} - {bairro}, {cidade} - CEP {formatar_cep(cep)}"


def formatar_moeda(valor: object) -> str:
    """Ex.: 1234.5 -> 'R$ 1.234,50'."""
    texto = f"{float(str(valor)):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")
