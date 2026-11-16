"""Loop do agente: guardrails → LLM ↔ tool → validação → resposta ou handoff."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

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
from agente_varejo.agente.retry import PoliticaRetry
from agente_varejo.config import (
    ConfigAgente,
    ConfigLoop,
    carregar_mensagens,
    ler_texto,
)
from agente_varejo.guardrails import (
    Escopo,
    Guardrails,
    carregar_guardrails,
    mascarar_cpf,
    pode_ver_pedido,
)
from agente_varejo.llm import LLMClient, construir_llm
from agente_varejo.llm.base import ChamadaTool, DefinicaoTool, Mensagem
from agente_varejo.logs import RegistradorJSON

LIMITE_NAO_ENCONTRADOS = 2
"""Na 2ª vez que o pedido não é encontrado (após o cliente conferir): handoff."""


@dataclass
class _Turno:
    """Rascunho do que aconteceu no turno; vira `ResultadoTurno` e registro de log."""

    inicio: float = field(default_factory=time.perf_counter)
    guardrails: list[str] = field(default_factory=list)
    tools_chamadas: list[str] = field(default_factory=list)
    log_tools: list[dict[str, Any]] = field(default_factory=list)
    chamadas_llm: int = 0
    status_da_tool: str | None = None
    passou_pelos_guardrails: bool = False


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
        guardrails: Guardrails,
        registrador: RegistradorJSON | None = None,
    ) -> None:
        self._llm = llm
        self._pedidos = pedidos
        self._config = config
        self._msg = mensagens
        self._sistema = sistema
        self._tools = list(tools)
        self._guardrails = guardrails
        self._log = registrador or RegistradorJSON()

    def responder(self, sessao: Sessao, texto: str) -> ResultadoTurno:
        """Processa uma mensagem do cliente e devolve resposta + desfecho."""
        sessao.turnos += 1
        turno = _Turno()

        # Guardrail 1 — CPF. A partir desta linha o texto original não é mais usado.
        texto, cpfs = mascarar_cpf(texto)
        if cpfs:
            turno.guardrails.append("cpf")

        resultado = self._barrar_na_entrada(texto, turno)
        if resultado is None:
            turno.passou_pelos_guardrails = True
            resultado = self._conversar(sessao, texto, turno)

        if turno.passou_pelos_guardrails:
            # Só entra no histórico (e volta ao LLM nos próximos turnos) o que passou
            # pelos guardrails: texto barrado como injection não fica "armazenado".
            sessao.historico.append(Mensagem("usuario", texto))
            sessao.historico.append(Mensagem("assistente", resultado.resposta))

        self._registrar(sessao, texto, turno, resultado)
        return resultado

    def _barrar_na_entrada(self, texto: str, turno: _Turno) -> ResultadoTurno | None:
        """Guardrails de entrada que encerram o turno sem chamar o LLM."""
        if len(texto) > self._config.max_chars_entrada:
            turno.guardrails.append("tamanho")
            return self._fim(turno, Desfecho.RECUSA, "tamanho", self._msg["recusa_tamanho"])

        # Guardrail 2 — prompt injection.
        injection = self._guardrails.injection.analisar(texto)
        if injection.bloqueado:
            turno.guardrails.append("injection:" + "+".join(injection.padroes))
            return self._fim(turno, Desfecho.RECUSA, "injection", self._msg["recusa_injection"])

        # Guardrail 3 — escopo.
        escopo = self._guardrails.escopo.classificar(texto)
        if escopo is Escopo.FORA:
            turno.guardrails.append("escopo:fora")
            return self._fim(turno, Desfecho.HANDOFF, "fora_do_escopo")
        if escopo is Escopo.INDEFINIDO:
            turno.guardrails.append("escopo:indefinido")
            pedir_numero = self._msg["esclarecimento_escopo"]
            return self._fim(turno, Desfecho.ESCLARECIMENTO, "sem_sinal_de_escopo", pedir_numero)
        return None

    def _conversar(self, sessao: Sessao, texto: str, turno: _Turno) -> ResultadoTurno:
        """Loop de tool calling com teto de passos e uma chance de corrigir a saída."""
        mensagens = [*sessao.historico, Mensagem("usuario", texto)]
        ja_corrigiu = False
        for _ in range(self._config.max_passos):
            turno.chamadas_llm += 1
            resposta = self._llm.gerar(self._sistema, mensagens, self._tools)

            if resposta.chamadas:
                # O modelo PEDE a execução; quem executa (e decide se pode) é o código.
                mensagens.append(
                    Mensagem("assistente", chamadas=resposta.chamadas, bruto=resposta.bruto)
                )
                for chamada in resposta.chamadas:
                    consulta = self._executar_tool(chamada, sessao, turno)
                    encerramento = self._encerrar_pela_tool(consulta, sessao, turno)
                    if encerramento is not None:
                        return encerramento
                    mensagens.append(Mensagem("tool", consulta.para_llm(), nome_tool=chamada.nome))
                continue

            try:
                saida = validar_saida(resposta.texto, turno.status_da_tool)
            except SaidaInvalida as erro:
                if ja_corrigiu:
                    return self._fim(turno, Desfecho.HANDOFF, "saida_invalida")
                ja_corrigiu = True
                turno.guardrails.append(f"saida_invalida:{erro}")
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

    def _executar_tool(
        self, chamada: ChamadaTool, sessao: Sessao, turno: _Turno
    ) -> ResultadoConsulta:
        """Valida o que o LLM pediu, executa a consulta e aplica a autorização."""
        turno.tools_chamadas.append(chamada.nome)
        inicio = time.perf_counter()
        if chamada.nome != NOME_TOOL:
            consulta = ResultadoConsulta("argumento_invalido", detalhe="tool desconhecida")
        elif (id_pedido := validar_argumentos(chamada.argumentos)) is None:
            consulta = ResultadoConsulta("argumento_invalido", detalhe="id_pedido fora do formato")
        else:
            consulta = self._pedidos.consultar(id_pedido)
            # Guardrail 4 — autorização. O dono do pedido é comparado com o cliente
            # DA SESSÃO; em caso negativo o pedido é descartado antes de chegar ao LLM.
            if consulta.pedido is not None and not pode_ver_pedido(
                sessao.cliente_id, consulta.pedido
            ):
                turno.guardrails.append("autorizacao")
                consulta = ResultadoConsulta(
                    "nao_autorizado", id_pedido, tentativas=consulta.tentativas
                )
        if consulta.tipo == "ok" and consulta.pedido is not None:
            turno.status_da_tool = consulta.pedido.status
        turno.log_tools.append(
            {
                "nome": chamada.nome,
                "id_pedido": consulta.id_pedido,
                "resultado": consulta.tipo,
                "detalhe": consulta.detalhe,
                "tentativas": consulta.tentativas,
                "latencia_ms": round((time.perf_counter() - inicio) * 1000, 1),
            }
        )
        return consulta

    def _encerrar_pela_tool(
        self, consulta: ResultadoConsulta, sessao: Sessao, turno: _Turno
    ) -> ResultadoTurno | None:
        """Desfechos que o CÓDIGO decide a partir do resultado da tool, sem voltar ao LLM."""
        if consulta.tipo == "ok":
            sessao.nao_encontrados = 0
            return None
        if consulta.tipo == "nao_autorizado":
            return self._fim(turno, Desfecho.RECUSA, "autorizacao", self._msg["recusa_autorizacao"])
        if consulta.tipo == "falha":
            return self._fim(turno, Desfecho.HANDOFF, "api_indisponivel")
        if consulta.tipo == "nao_encontrado":
            sessao.nao_encontrados += 1
            if sessao.nao_encontrados >= LIMITE_NAO_ENCONTRADOS:
                return self._fim(turno, Desfecho.HANDOFF, "pedido_nao_encontrado")
            pedir = self._msg["confirmacao_pedido"].format(id_pedido=consulta.id_pedido)
            return self._fim(turno, Desfecho.CONFIRMACAO, "pedido_nao_encontrado", pedir)
        return None  # argumento inválido: o erro volta ao LLM, que pode se corrigir

    def _fim(
        self, turno: _Turno, desfecho: Desfecho, motivo: str, resposta: str | None = None
    ) -> ResultadoTurno:
        """Monta o resultado; sem texto próprio, usa a mensagem fixa de handoff."""
        texto = resposta if resposta is not None else self._msg["handoff"]
        # Guardrail de saída: nada sai para o cliente com CPF, venha de onde vier.
        texto, cpfs = mascarar_cpf(texto)
        if cpfs:
            turno.guardrails.append("cpf_na_saida")
        return ResultadoTurno(
            resposta=texto,
            desfecho=desfecho,
            motivo=motivo,
            tools_chamadas=tuple(turno.tools_chamadas),
            status_pedido=turno.status_da_tool if desfecho is Desfecho.STATUS else None,
            guardrails=tuple(turno.guardrails),
        )

    def _registrar(
        self, sessao: Sessao, texto: str, turno: _Turno, resultado: ResultadoTurno
    ) -> None:
        """Um registro JSON por turno. O registrador mascara CPF de novo na saída."""
        self._log.registrar(
            "turno",
            sessao_id=sessao.id,
            cliente_id=sessao.cliente_id,
            turno=sessao.turnos,
            entrada=texto[: self._config.max_chars_entrada],
            guardrails=list(resultado.guardrails),
            chamadas_llm=turno.chamadas_llm,
            tool_calls=turno.log_tools,
            desfecho=resultado.desfecho.value,
            motivo=resultado.motivo,
            latencia_ms=round((time.perf_counter() - turno.inicio) * 1000, 1),
        )


def construir_agente(
    config: ConfigAgente,
    http: httpx.Client,
    llm: LLMClient | None = None,
    registrador: RegistradorJSON | None = None,
    dormir: Callable[[float], None] = time.sleep,
) -> Agente:
    """Monta o agente a partir dos arquivos de `config/` e `prompts/`."""
    politica = PoliticaRetry(
        retries=config.api.retries,
        base_s=config.api.backoff_base_s,
        fator=config.api.backoff_fator,
        jitter_s=config.api.jitter_s,
    )
    return Agente(
        llm=llm or construir_llm(config.llm),
        pedidos=ClientePedidos(http, politica=politica, dormir=dormir),
        config=config.agente,
        mensagens=carregar_mensagens(),
        sistema=ler_texto(config.agente.prompt_sistema),
        tools=carregar_definicoes_tools(config.agente.definicao_tools),
        guardrails=carregar_guardrails(),
        registrador=registrador,
    )
