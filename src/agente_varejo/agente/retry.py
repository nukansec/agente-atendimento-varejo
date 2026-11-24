"""Retry com backoff exponencial e jitter, sem dependência externa."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PoliticaRetry:
    """Quantas vezes repetir e quanto esperar entre as tentativas."""

    retries: int = 2
    base_s: float = 0.5
    fator: float = 2.0
    jitter_s: float = 0.25

    def espera(self, repeticao: int, rng: random.Random) -> float:
        """Espera antes da repetição `repeticao` (0 = primeira): base * fator^n + jitter.

        O jitter (parcela aleatória) evita que vários clientes que falharam
        juntos voltem todos no mesmo instante e derrubem a API de novo.
        """
        return self.base_s * (self.fator**repeticao) + rng.uniform(0.0, self.jitter_s)


def executar_com_retry(
    operacao: Callable[[], T],
    deve_repetir: Callable[[T], bool],
    politica: PoliticaRetry,
    dormir: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
) -> tuple[T, int]:
    """Executa `operacao` até dar certo ou acabar o orçamento de tentativas.

    Devolve o último resultado e o número de tentativas feitas. O total máximo é
    `1 + politica.retries`: o teto existe para não transformar uma falha da API
    em uma tempestade de repetições.
    """
    rng = rng or random.Random()  # noqa: S311 - jitter não é uso criptográfico
    tentativas = 0
    while True:
        resultado = operacao()
        tentativas += 1
        if not deve_repetir(resultado) or tentativas > politica.retries:
            return resultado, tentativas
        dormir(politica.espera(tentativas - 1, rng))
