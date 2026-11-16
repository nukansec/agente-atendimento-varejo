"""LLM falso, determinístico, usado em todos os testes, no CI e no `make eval`.

Dois modos, que se combinam:

- **roteiro**: respostas pré-definidas, consumidas em ordem. Serve para forçar
  o comportamento de um modelo que erra (JSON inválido, status inventado,
  chamada de tool indevida).
- **regras**: quando o roteiro acaba, imita um modelo bem-comportado — pede a
  tool se o cliente citou um número de pedido e responde a partir do resultado.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from agente_varejo.dominio import PADRAO_ID_PEDIDO
from agente_varejo.llm.base import (
    MARCA_CORRECAO,
    ChamadaTool,
    DefinicaoTool,
    Mensagem,
    RespostaLLM,
)

NOME_TOOL = "consultar_pedido"


@dataclass(frozen=True)
class ChamadaRecebida:
    """O que o agente enviou ao LLM em uma chamada (para inspeção nos testes)."""

    sistema: str
    mensagens: tuple[Mensagem, ...]


def resposta_json(
    resposta: str,
    status: str | None = None,
    confianca: float = 0.95,
    precisa_humano: bool = False,
) -> RespostaLLM:
    """Monta uma resposta final no formato JSON exigido pelo system prompt."""
    corpo = {
        "resposta": resposta,
        "status_pedido": status,
        "confianca": confianca,
        "precisa_humano": precisa_humano,
    }
    return RespostaLLM(texto=json.dumps(corpo, ensure_ascii=False))


class FakeLLM:
    """Implementação de `LLMClient` sem rede e sem aleatoriedade."""

    def __init__(self, roteiro: Iterable[RespostaLLM] | None = None) -> None:
        self._roteiro = list(roteiro or [])
        self.recebidas: list[ChamadaRecebida] = []

    def gerar(
        self,
        sistema: str,
        mensagens: Sequence[Mensagem],
        tools: Sequence[DefinicaoTool],
    ) -> RespostaLLM:
        """Devolve o próximo item do roteiro ou aplica as regras."""
        self.recebidas.append(ChamadaRecebida(sistema, tuple(mensagens)))
        if self._roteiro:
            return self._roteiro.pop(0)
        return self._por_regras(mensagens)

    def _por_regras(self, mensagens: Sequence[Mensagem]) -> RespostaLLM:
        # Anda de trás para frente até o fato mais recente: resultado de tool
        # ou fala do cliente. Pedidos de correção de formato são pulados.
        for mensagem in reversed(mensagens):
            if mensagem.papel == "tool":
                return self._responder_resultado(mensagem.conteudo)
            if mensagem.papel == "usuario" and not mensagem.conteudo.startswith(MARCA_CORRECAO):
                achado = PADRAO_ID_PEDIDO.search(mensagem.conteudo)
                if achado:
                    argumentos = {"id_pedido": achado.group(0).upper()}
                    return RespostaLLM(chamadas=(ChamadaTool(NOME_TOOL, argumentos),))
                break
        return resposta_json("Claro! Qual é o número do pedido (ex.: PED-1001)?")

    @staticmethod
    def _responder_resultado(conteudo: str) -> RespostaLLM:
        resultado = json.loads(conteudo)
        if not resultado.get("encontrado"):
            return resposta_json("Não encontrei esse pedido. Pode confirmar o número?")
        texto = f"O pedido {resultado['id_pedido']} está com status: {resultado['status']}."
        if resultado.get("previsao_entrega"):
            texto += f" Previsão de entrega: {resultado['previsao_entrega']}."
        return resposta_json(texto, resultado["status"])
