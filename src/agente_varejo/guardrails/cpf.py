"""Mascaramento de CPF: roda antes do LLM, do histórico e de qualquer log."""

from __future__ import annotations

import re
from typing import Any

MASCARA_CPF = "***.***.***-**"

# 11 dígitos no formato de CPF, com ou sem pontuação (ponto, hífen ou espaço).
# Os lookarounds impedem casar um pedaço de um número maior (ex.: CNPJ, 14 dígitos).
PADRAO_CPF = re.compile(r"(?<!\d)\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{2}(?!\d)")


def mascarar_cpf(texto: str) -> tuple[str, int]:
    """Troca todo CPF do texto pela máscara. Devolve o texto e quantos foram trocados.

    Mascara pelo FORMATO, sem conferir os dígitos verificadores: um CPF digitado
    errado continua sendo, quase sempre, o dado pessoal de alguém.
    """
    return PADRAO_CPF.subn(MASCARA_CPF, texto)


def contem_cpf(texto: str) -> bool:
    """Diz se há algo com formato de CPF no texto."""
    return PADRAO_CPF.search(texto) is not None


def mascarar_profundo(valor: Any) -> Any:
    """Aplica a máscara em strings e inteiros de uma estrutura (dict, lista, tupla)."""
    if isinstance(valor, str):
        return mascarar_cpf(valor)[0]
    if isinstance(valor, int) and not isinstance(valor, bool):
        return MASCARA_CPF if contem_cpf(str(valor)) else valor
    if isinstance(valor, dict):
        return {mascarar_profundo(k): mascarar_profundo(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set, frozenset)):
        return [mascarar_profundo(item) for item in valor]
    return valor
