"""Avaliação do agente por casos de teste com resultado esperado."""

from agente_varejo.avaliacao.casos import Caso, ConjuntoDeCasos, Esperado, carregar_casos
from agente_varejo.avaliacao.runner import (
    Relatorio,
    ResultadoCaso,
    avaliar,
    executar_caso,
    formatar,
)

__all__ = [
    "Caso",
    "ConjuntoDeCasos",
    "Esperado",
    "Relatorio",
    "ResultadoCaso",
    "avaliar",
    "carregar_casos",
    "executar_caso",
    "formatar",
]
