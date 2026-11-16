"""Loop do agente: LLM ↔ tool, feito à mão (sem framework)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import httpx

from agente_varejo.agente.ferramentas import (
    NOME_TOOL,
    ClientePedidos,
    ResultadoConsulta,
    carregar_definicoes_tools,
    validar_argumentos,
)
from agente_varejo.agente.modelos import (
    Desfecho,
    ResultadoTurno,
    SaidaInvalida,
    Sessao,
    validar_saida,
)
from agente_varejo.config import (
    ConfigAgente,
    ConfigLoop,
    carregar_mensagens,
    ler_texto,
)
from agente_varejo.llm import LLMClient, construir_llm
from agente_varejo.llm.base import ChamadaTool, DefinicaoTool, Mensagem


@dataclass
class _Turno:
    """Rascunho do que aconteceu no turno; vira `ResultadoTurno` no fim."""

    tools_chamadas: list[str] = field(default_factory=list)
    status_da_tool: str | None = None


class Agente:
    """Atende um turno por vez: recebe o texto do cliente e devolve a resposta."""

    def __init__(
        self,
        llm: LLMClient,
        pedidos: ClientePedidos,
        config: ConfigLoop,
        mensagens: dict[str, str],
        sistema: str,
        tools: Sequence[DefinicaoTool],
    ) -> None:
        self._llm = llm
        self._pedidos = pedidos
        self._config = config
        self._msg = mensagens
        self._sistema = sistema
        self._tools = list(tools)

    def responder(self, sessao: Sessao, texto: str) -> ResultadoTurno:
        """Processa uma mensagem do cliente e devolve resposta + desfecho."""
        sessao.turnos += 1
        turno = _Turno()
        resultado = self._conversar(sessao, texto, turno)
        sessao.historico.append(Mensagem("usuario", texto))
        sessao.historico.append(Mensagem("assistente", resultado.resposta))
        return resultado

    def _conversar(self, sessao: Sessao, texto: str, turno: _Turno) -> ResultadoTurno:
        """Loop de tool calling com teto de passos e uma chance de corrigir a saída."""
        mensagens = [*sessao.historico, Mensagem("usuario", texto)]
        ja_corrigiu = False
        for _ in range(self._config.max_passos):
            resposta = self._llm.gerar(self._sistema, mensagens, self._tools)

            if resposta.chamadas:
                # O modelo PEDE a execução; quem executa (e decide se pode) é o código.
                mensagens.append(
                    Mensagem("assistente", chamadas=resposta.chamadas, bruto=resposta.bruto)
                )
                for chamada in resposta.chamadas:
                    consulta = self._executar_tool(chamada, turno)
                    if consulta.tipo == "falha":
                        return self._fim(turno, Desfecho.HANDOFF, "api_indisponivel")
                    mensagens.append(Mensagem("tool", consulta.para_llm(), nome_tool=chamada.nome))
                continue

            try:
                saida = validar_saida(resposta.texto, turno.status_da_tool)
            except SaidaInvalida as erro:
                if ja_corrigiu:
                    return self._fim(turno, Desfecho.HANDOFF, "saida_invalida")
                ja_corrigiu = True
                mensagens.append(Mensagem("assistente", resposta.texto or "", bruto=resposta.bruto))
                correcao = self._msg["correcao_formato"].format(erro=erro)
                mensagens.append(Mensagem("usuario", correcao))
                continue

            if saida.precisa_humano:
                return self._fim(turno, Desfecho.HANDOFF, "llm_pediu_humano")
            if saida.confianca < self._config.limiar_confianca:
                return self._fim(turno, Desfecho.HANDOFF, "baixa_confianca")
            if saida.status_pedido is not None:
                return self._fim(turno, Desfecho.STATUS, "status_informado", saida.resposta)
            return self._fim(turno, Desfecho.ESCLARECIMENTO, "sem_consulta", saida.resposta)

        return self._fim(turno, Desfecho.HANDOFF, "limite_de_passos")

    def _executar_tool(self, chamada: ChamadaTool, turno: _Turno) -> ResultadoConsulta:
        """Valida nome e argumentos gerados pelo LLM e executa a consulta."""
        turno.tools_chamadas.append(chamada.nome)
        if chamada.nome != NOME_TOOL:
            return ResultadoConsulta("argumento_invalido", detalhe="tool desconhecida")
        id_pedido = validar_argumentos(chamada.argumentos)
        if id_pedido is None:
            return ResultadoConsulta("argumento_invalido", detalhe="id_pedido fora do formato")
        consulta = self._pedidos.consultar(id_pedido)
        if consulta.tipo == "ok" and consulta.pedido is not None:
            turno.status_da_tool = consulta.pedido.status
        return consulta

    def _fim(
        self, turno: _Turno, desfecho: Desfecho, motivo: str, resposta: str | None = None
    ) -> ResultadoTurno:
        """Monta o resultado; sem texto do LLM, usa a mensagem fixa de handoff."""
        return ResultadoTurno(
            resposta=resposta if resposta is not None else self._msg["handoff"],
            desfecho=desfecho,
            motivo=motivo,
            tools_chamadas=tuple(turno.tools_chamadas),
            status_pedido=turno.status_da_tool if desfecho is Desfecho.STATUS else None,
        )


def construir_agente(
    config: ConfigAgente, http: httpx.Client, llm: LLMClient | None = None
) -> Agente:
    """Monta o agente a partir dos arquivos de `config/` e `prompts/`."""
    return Agente(
        llm=llm or construir_llm(config.llm),
        pedidos=ClientePedidos(http),
        config=config.agente,
        mensagens=carregar_mensagens(),
        sistema=ler_texto(config.agente.prompt_sistema),
        tools=carregar_definicoes_tools(config.agente.definicao_tools),
    )
