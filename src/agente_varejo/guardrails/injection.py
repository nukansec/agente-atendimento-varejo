"""Detector simples de prompt injection: padrões com peso + limiar."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from agente_varejo.guardrails.texto import normalizar


@dataclass(frozen=True)
class PadraoInjection:
    """Um padrão da política: regex sobre o texto normalizado e seu peso."""

    id: str
    peso: float
    regex: re.Pattern[str]


@dataclass(frozen=True)
class ResultadoInjection:
    """Veredito do detector, com o que casou (vai para o log)."""

    bloqueado: bool
    pontuacao: float
    padroes: tuple[str, ...]


class DetectorInjection:
    """Soma os pesos dos padrões que casam; bloqueia a partir do limiar.

    A heurística é a soma: um sinal forte basta, sinais fracos só bloqueiam
    combinados. Isso reduz falso positivo de frases como "sou o gerente".
    """

    def __init__(self, padroes: list[PadraoInjection], limiar: float) -> None:
        self._padroes = padroes
        self._limiar = limiar

    @classmethod
    def da_politica(cls, politica: dict[str, Any]) -> DetectorInjection:
        """Constrói o detector a partir da seção `injection` do YAML."""
        padroes = [
            PadraoInjection(item["id"], float(item["peso"]), re.compile(item["regex"]))
            for item in politica["padroes"]
        ]
        return cls(padroes, float(politica["limiar"]))

    def analisar(self, texto: str) -> ResultadoInjection:
        """Avalia o texto do usuário (já mascarado) e devolve o veredito."""
        normal = normalizar(texto)
        casados = [p for p in self._padroes if p.regex.search(normal)]
        pontuacao = sum(p.peso for p in casados)
        return ResultadoInjection(
            bloqueado=pontuacao >= self._limiar,
            pontuacao=pontuacao,
            padroes=tuple(p.id for p in casados),
        )
