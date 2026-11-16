"""Interface do provedor de LLM e os tipos trocados com ele.

O agente só conhece `LLMClient`. Trocar de provedor (ou usar o falso nos
testes) não muda nenhuma linha do loop.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Papel = Literal["usuario", "assistente", "tool"]

MARCA_CORRECAO = "[formato]"
"""Prefixo da mensagem que pede ao LLM para refazer uma saída inválida."""


@dataclass(frozen=True)
class ChamadaTool:
    """Pedido do modelo para executar uma função: nome + argumentos (JSON)."""

    nome: str
    argumentos: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Mensagem:
    """Uma entrada da conversa enviada ao modelo."""

    papel: Papel
    conteudo: str = ""
    chamadas: tuple[ChamadaTool, ...] = ()
    nome_tool: str | None = None
    bruto: Any = None
    """Turno original do provedor (ex.: assinaturas de raciocínio), reenviado sem alteração."""


@dataclass(frozen=True)
class DefinicaoTool:
    """Descrição de uma tool no formato JSON Schema."""

    nome: str
    descricao: str
    parametros: dict[str, Any]


@dataclass(frozen=True)
class RespostaLLM:
    """Resposta do modelo: texto final OU chamadas de tool."""

    texto: str | None = None
    chamadas: tuple[ChamadaTool, ...] = ()
    bruto: Any = None


class LLMClient(Protocol):
    """Contrato mínimo de um provedor de LLM com tool calling."""

    def gerar(
        self,
        sistema: str,
        mensagens: Sequence[Mensagem],
        tools: Sequence[DefinicaoTool],
    ) -> RespostaLLM:
        """Gera a próxima resposta do modelo para a conversa dada."""
        ...
