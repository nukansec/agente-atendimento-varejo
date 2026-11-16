"""Provedores de LLM atrás da interface `LLMClient`."""

from agente_varejo.config import ConfigLLM
from agente_varejo.llm.base import (
    MARCA_CORRECAO,
    ChamadaTool,
    DefinicaoTool,
    LLMClient,
    Mensagem,
    RespostaLLM,
)
from agente_varejo.llm.fake import FakeLLM, resposta_json


def construir_llm(config: ConfigLLM) -> LLMClient:
    """Escolhe a implementação pelo `provedor` configurado."""
    if config.provedor == "gemini":
        # Import tardio: o SDK é dependência opcional (`pip install -e ".[gemini]"`).
        from agente_varejo.llm.gemini import GeminiLLM

        return GeminiLLM(modelo=config.modelo, temperatura=config.temperatura)
    return FakeLLM()


__all__ = [
    "MARCA_CORRECAO",
    "ChamadaTool",
    "DefinicaoTool",
    "FakeLLM",
    "LLMClient",
    "Mensagem",
    "RespostaLLM",
    "construir_llm",
    "resposta_json",
]
