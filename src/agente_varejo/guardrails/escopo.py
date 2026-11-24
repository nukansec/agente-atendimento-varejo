"""Checagem de escopo: o agente só trata de status de pedido."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from agente_varejo.dominio import PADRAO_ID_PEDIDO
from agente_varejo.guardrails.texto import normalizar


class Escopo(StrEnum):
    """Classificação da mensagem em relação ao escopo."""

    DENTRO = "dentro"  # fala de pedido/entrega ou traz um número de pedido
    FORA = "fora"  # tema que exige uma pessoa (jurídico, reembolso, troca...)
    INDEFINIDO = "indefinido"  # nenhum sinal: pedir o número do pedido


class VerificadorEscopo:
    """Classifica por termos. Tema proibido tem precedência sobre termo do escopo."""

    def __init__(self, temas_fora: str, termos_do_escopo: str) -> None:
        self._fora = re.compile(temas_fora)
        self._dentro = re.compile(termos_do_escopo)

    @classmethod
    def da_politica(cls, politica: dict[str, Any]) -> VerificadorEscopo:
        """Constrói o verificador a partir da seção `escopo` do YAML."""
        return cls(politica["temas_fora"], politica["termos_do_escopo"])

    def classificar(self, texto: str) -> Escopo:
        """Devolve a classificação da mensagem (já mascarada)."""
        normal = normalizar(texto)
        if self._fora.search(normal):
            return Escopo.FORA
        if PADRAO_ID_PEDIDO.search(normal) or self._dentro.search(normal):
            return Escopo.DENTRO
        return Escopo.INDEFINIDO
