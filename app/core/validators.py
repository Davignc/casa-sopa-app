"""Normalizações compartilhadas pelos schemas.

Normalizar antes de gravar é o que faz as restrições UNIQUE (e-mail, telefone)
funcionarem de verdade: "(16) 99999-0000" e "16999990000" são o mesmo telefone.
"""

import re


def normalizar_telefone(valor: str) -> str:
    """Mantém só os dígitos e exige DDD + número (10 ou 11 dígitos)."""
    digitos = re.sub(r"\D", "", valor)
    if len(digitos) not in (10, 11):
        raise ValueError("Telefone inválido: informe DDD + número (10 ou 11 dígitos).")
    return digitos


def normalizar_email(valor: str) -> str:
    return valor.strip().lower()
