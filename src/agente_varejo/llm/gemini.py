"""Adaptador do Gemini (SDK `google-genai`) para a interface `LLMClient`.

Não é usado em testes, CI nem `make eval`. A chave vem só de variável de
ambiente (`GEMINI_API_KEY`), lida pelo próprio SDK. Este adaptador ainda não
foi executado contra a API real: ver "Itens a verificar" no PROGRESSO.md.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from agente_varejo.llm.base import ChamadaTool, DefinicaoTool, Mensagem, RespostaLLM

VAR_CHAVE = "GEMINI_API_KEY"


class GeminiLLM:
    """Implementação de `LLMClient` sobre `client.models.generate_content`."""

    def __init__(self, modelo: str, temperatura: float) -> None:
        if not os.environ.get(VAR_CHAVE):
            raise RuntimeError(f"Defina a variável de ambiente {VAR_CHAVE} para usar o Gemini.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as erro:
            raise RuntimeError('Instale o extra: pip install -e ".[gemini]"') from erro
        self._types = types
        self._cliente = genai.Client()  # lê a chave do ambiente
        self._modelo = modelo
        self._temperatura = temperatura

    def gerar(
        self,
        sistema: str,
        mensagens: Sequence[Mensagem],
        tools: Sequence[DefinicaoTool],
    ) -> RespostaLLM:
        """Envia a conversa e traduz a resposta para `RespostaLLM`."""
        types = self._types
        declaracoes = [
            types.FunctionDeclaration(
                name=tool.nome,
                description=tool.descricao,
                parameters_json_schema=tool.parametros,
            )
            for tool in tools
        ]
        config = types.GenerateContentConfig(
            system_instruction=sistema,
            temperature=self._temperatura,
            tools=[types.Tool(function_declarations=declaracoes)],
        )
        resposta = self._cliente.models.generate_content(
            model=self._modelo,
            contents=[self._converter(mensagem) for mensagem in mensagens],
            config=config,
        )
        chamadas = tuple(
            ChamadaTool(nome=chamada.name, argumentos=dict(chamada.args or {}))
            for chamada in (resposta.function_calls or [])
        )
        bruto = resposta.candidates[0].content if resposta.candidates else None
        if chamadas:
            return RespostaLLM(chamadas=chamadas, bruto=bruto)
        return RespostaLLM(texto=resposta.text, bruto=bruto)

    def _converter(self, mensagem: Mensagem) -> Any:
        """Converte uma `Mensagem` no `Content` do SDK."""
        types = self._types
        if mensagem.papel == "tool":
            parte = types.Part.from_function_response(
                name=mensagem.nome_tool or "", response={"result": mensagem.conteudo}
            )
            return types.Content(role="tool", parts=[parte])
        if mensagem.papel == "assistente":
            if mensagem.bruto is not None:
                # Reenvia o turno do modelo sem alterar: preserva as assinaturas
                # de raciocínio que acompanham as chamadas de função.
                return mensagem.bruto
            return types.Content(role="model", parts=[types.Part.from_text(text=mensagem.conteudo)])
        return types.Content(role="user", parts=[types.Part.from_text(text=mensagem.conteudo)])
