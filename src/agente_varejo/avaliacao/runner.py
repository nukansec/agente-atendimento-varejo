"""Executa os casos de avaliação contra o agente e calcula a taxa de acerto."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from agente_varejo.agente import ResultadoTurno, Sessao, construir_agente
from agente_varejo.api_simulada import carregar_pedidos, cliente_em_memoria, criar_app
from agente_varejo.avaliacao.casos import Caso, ConjuntoDeCasos
from agente_varejo.config import ConfigAgente
from agente_varejo.guardrails import contem_cpf
from agente_varejo.llm import DefinicaoTool, FakeLLM, LLMClient, Mensagem, RespostaLLM
from agente_varejo.logs import RegistradorMemoria

# Na avaliação a API "lenta" demora 0,3 s e o cliente espera 0,1 s: o timeout é
# real, mas o caso termina rápido. As esperas de backoff são puladas.
ATRASO_API_S = 0.3
TIMEOUT_CLIENTE_S = 0.1


class LLMEspiao:
    """Envolve qualquer `LLMClient` e guarda tudo o que foi enviado a ele."""

    def __init__(self, interno: LLMClient) -> None:
        self._interno = interno
        self.textos_enviados: list[str] = []

    def gerar(
        self,
        sistema: str,
        mensagens: Sequence[Mensagem],
        tools: Sequence[DefinicaoTool],
    ) -> RespostaLLM:
        """Registra o conteúdo das mensagens e repassa a chamada."""
        self.textos_enviados.extend(mensagem.conteudo for mensagem in mensagens)
        return self._interno.gerar(sistema, mensagens, tools)


@dataclass(frozen=True)
class ResultadoCaso:
    """Veredito de um caso, com as divergências encontradas."""

    caso: Caso
    obtido: ResultadoTurno
    cpf_mascarado: bool
    falhas: tuple[str, ...]

    @property
    def passou(self) -> bool:
        """O caso passa quando não há nenhuma divergência."""
        return not self.falhas


@dataclass(frozen=True)
class Relatorio:
    """Resultado do conjunto inteiro."""

    resultados: tuple[ResultadoCaso, ...]
    meta: float
    acertos: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "acertos", sum(r.passou for r in self.resultados))

    @property
    def taxa(self) -> float:
        """Fração de casos que passaram."""
        return self.acertos / len(self.resultados)

    @property
    def atingiu_meta(self) -> bool:
        """Verdadeiro se a taxa de acerto alcança a meta do conjunto."""
        return self.taxa >= self.meta


def executar_caso(
    caso: Caso,
    cliente_id: str,
    config: ConfigAgente,
    criar_llm: Callable[[], LLMClient] = FakeLLM,
) -> ResultadoCaso:
    """Roda um caso do zero (sessão, LLM, API e log novos) e compara com o esperado."""
    dados = carregar_pedidos()
    dados.falhas_simuladas.atraso_timeout_s = ATRASO_API_S
    espiao = LLMEspiao(criar_llm())
    registros = RegistradorMemoria()
    sessao = Sessao(cliente_id=cliente_id)
    respostas: list[ResultadoTurno] = []

    with cliente_em_memoria(criar_app(dados), timeout_s=TIMEOUT_CLIENTE_S) as http:
        agente = construir_agente(
            config, http, llm=espiao, registrador=registros, dormir=lambda _segundos: None
        )
        respostas.extend(agente.responder(sessao, texto) for texto in caso.turnos)

    obtido = respostas[-1]
    esperado = caso.esperado
    falhas: list[str] = []

    if obtido.desfecho is not esperado.desfecho:
        falhas.append(f"desfecho={obtido.desfecho.value} (esperado {esperado.desfecho.value})")
    tool_obtida = obtido.tools_chamadas[0] if obtido.tools_chamadas else "nenhuma"
    if tool_obtida != esperado.tool or len(obtido.tools_chamadas) > 1:
        chamadas = ",".join(obtido.tools_chamadas) or "nenhuma"
        falhas.append(f"tool={chamadas} (esperado {esperado.tool})")
    if esperado.status is not None and obtido.status_pedido != esperado.status:
        falhas.append(f"status={obtido.status_pedido} (esperado {esperado.status})")
    if esperado.motivo is not None and obtido.motivo != esperado.motivo:
        falhas.append(f"motivo={obtido.motivo} (esperado {esperado.motivo})")
    if esperado.tentativas_api is not None:
        tools_logadas = registros.eventos()[-1]["tool_calls"]
        tentativas = tools_logadas[-1]["tentativas"] if tools_logadas else 0
        if tentativas != esperado.tentativas_api:
            falhas.append(f"tentativas_api={tentativas} (esperado {esperado.tentativas_api})")

    # CPF: o guardrail agiu quando devia, e nada vazou em nenhuma superfície.
    cpf_mascarado = any("cpf" in turno.guardrails for turno in respostas)
    if cpf_mascarado != esperado.cpf_mascarado:
        falhas.append(f"cpf_mascarado={cpf_mascarado} (esperado {esperado.cpf_mascarado})")
    superficies = {
        "llm": espiao.textos_enviados,
        "resposta": [turno.resposta for turno in respostas],
        "log": registros.linhas,
    }
    falhas.extend(
        f"CPF vazou em: {nome}"
        for nome, textos in superficies.items()
        if any(contem_cpf(texto) for texto in textos)
    )

    return ResultadoCaso(caso, obtido, cpf_mascarado, tuple(falhas))


def avaliar(
    conjunto: ConjuntoDeCasos,
    config: ConfigAgente,
    criar_llm: Callable[[], LLMClient] = FakeLLM,
    meta: float | None = None,
) -> Relatorio:
    """Roda todos os casos e devolve o relatório."""
    resultados = tuple(
        executar_caso(caso, conjunto.cliente_id, config, criar_llm) for caso in conjunto.casos
    )
    return Relatorio(resultados, conjunto.meta if meta is None else meta)


def formatar(relatorio: Relatorio) -> str:
    """Tabela em texto com um caso por linha, seguida da taxa de acerto."""
    cabecalho = ("caso", "categoria", "tool", "desfecho", "motivo", "cpf masc.", "ok?")
    linhas = [
        (
            r.caso.id,
            r.caso.categoria,
            r.obtido.tools_chamadas[0] if r.obtido.tools_chamadas else "nenhuma",
            r.obtido.desfecho.value,
            r.obtido.motivo,
            "sim" if r.cpf_mascarado else "nao",
            "OK" if r.passou else "FALHOU",
        )
        for r in relatorio.resultados
    ]
    larguras = [max(len(linha[i]) for linha in [cabecalho, *linhas]) for i in range(len(cabecalho))]

    def _linha(celulas: Sequence[str]) -> str:
        return "  ".join(c.ljust(w) for c, w in zip(celulas, larguras, strict=True)).rstrip()

    saida = [_linha(cabecalho), _linha(["-" * w for w in larguras]), *map(_linha, linhas)]
    for r in relatorio.resultados:
        saida.extend(f"  ! {r.caso.id}: {falha}" for falha in r.falhas)
    total = len(relatorio.resultados)
    veredito = "meta atingida" if relatorio.atingiu_meta else "ABAIXO DA META"
    saida.append("")
    saida.append(
        f"Taxa de acerto: {relatorio.acertos}/{total} ({relatorio.taxa:.0%}) | "
        f"meta: {relatorio.meta:.0%} | {veredito}"
    )
    return "\n".join(saida)
