"""Normalização de texto usada pelos guardrails baseados em padrão."""

from __future__ import annotations

import re
import unicodedata

_ESPACOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    """Deixa o texto em forma canônica: minúsculo, sem acento e sem truques visuais.

    - NFKD desfaz variações de compatibilidade (ex.: letras "largas" ｉｇｎｏｒｅ);
    - marcas de acento (categoria Mn) e caracteres de formato invisíveis
      (categoria Cf, como o zero-width space) são removidos;
    - qualquer sequência de espaços e quebras de linha vira um espaço.
    """
    decomposto = unicodedata.normalize("NFKD", texto)
    visivel = "".join(c for c in decomposto if unicodedata.category(c) not in {"Mn", "Cf"})
    return _ESPACOS.sub(" ", visivel).casefold().strip()
