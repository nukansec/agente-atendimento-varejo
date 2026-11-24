"""CLI da avaliação: `python -m agente_varejo.avaliacao` (ou `make eval`)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from agente_varejo.avaliacao.casos import CASOS_PADRAO, carregar_casos
from agente_varejo.avaliacao.runner import avaliar, formatar
from agente_varejo.config import carregar_config
from agente_varejo.llm import FakeLLM, construir_llm


def main(argumentos: Sequence[str] | None = None) -> int:
    """Roda os casos, imprime a tabela e devolve 0 (meta atingida) ou 1."""
    parser = argparse.ArgumentParser(description="Avalia o agente nos casos de teste.")
    parser.add_argument("--casos", default=CASOS_PADRAO, help="YAML de casos, relativo à raiz")
    parser.add_argument("--meta", type=float, default=None, help="sobrepõe a meta do arquivo (0-1)")
    parser.add_argument(
        "--llm",
        choices=["fake", "gemini"],
        default="fake",
        help="fake (padrão, offline) ou gemini (precisa de GEMINI_API_KEY e do extra [gemini])",
    )
    opcoes = parser.parse_args(argumentos)

    config = carregar_config()
    if opcoes.llm == "gemini":
        config_llm = config.llm.model_copy(update={"provedor": "gemini"})
        llm_real = construir_llm(config_llm)
        criar_llm = lambda: llm_real  # noqa: E731 - o cliente real não guarda estado por caso
    else:
        criar_llm = FakeLLM

    relatorio = avaliar(carregar_casos(opcoes.casos), config, criar_llm, opcoes.meta)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"Casos: {opcoes.casos} | LLM: {opcoes.llm}")
    print(formatar(relatorio))
    return 0 if relatorio.atingiu_meta else 1


if __name__ == "__main__":
    sys.exit(main())
