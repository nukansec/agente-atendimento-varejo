"""Loop de tool calling e validação da saída do LLM."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from agente_varejo.agente import Agente, Desfecho, Sessao
from agente_varejo.agente.modelos import SaidaInvalida, validar_saida
from agente_varejo.llm import ChamadaTool, FakeLLM, RespostaLLM, resposta_json

Montar = Callable[..., Agente]


def _tool(id_pedido: str) -> RespostaLLM:
    return RespostaLLM(chamadas=(ChamadaTool("consultar_pedido", {"id_pedido": id_pedido}),))


@pytest.mark.parametrize(
    ("id_pedido", "status"),
    [
        ("PED-1001", "pago"),
        ("PED-1002", "separando"),
        ("PED-1003", "enviado"),
        ("PED-1004", "entregue"),
        ("PED-1006", "atrasado"),
    ],
)
def test_consulta_normal_informa_status(
    montar: Montar, sessao: Sessao, id_pedido: str, status: str
) -> None:
    resultado = montar().responder(sessao, f"Qual o status do pedido {id_pedido}?")
    assert resultado.desfecho is Desfecho.STATUS
    assert resultado.status_pedido == status
    assert resultado.tools_chamadas == ("consultar_pedido",)
    assert status in resultado.resposta


def test_sem_numero_pede_esclarecimento_sem_chamar_tool(montar: Montar, sessao: Sessao) -> None:
    resultado = montar().responder(sessao, "Quero saber do meu pedido")
    assert resultado.desfecho is Desfecho.ESCLARECIMENTO
    assert resultado.tools_chamadas == ()


def test_resultado_da_tool_volta_para_o_llm_sem_cliente_id(montar: Montar, sessao: Sessao) -> None:
    llm = FakeLLM()
    montar(llm).responder(sessao, "status do PED-1001")
    mensagens_tool = [m for m in llm.recebidas[-1].mensagens if m.papel == "tool"]
    assert len(mensagens_tool) == 1
    corpo = json.loads(mensagens_tool[0].conteudo)
    assert corpo == {
        "encontrado": True,
        "id_pedido": "PED-1001",
        "status": "pago",
        "previsao_entrega": "2026-11-25",
    }


def test_historico_guarda_o_turno(montar: Montar, sessao: Sessao) -> None:
    montar().responder(sessao, "status do PED-1001")
    assert [m.papel for m in sessao.historico] == ["usuario", "assistente"]
    assert sessao.turnos == 1


def test_saida_invalida_tem_uma_nova_tentativa(montar: Montar, sessao: Sessao) -> None:
    llm = FakeLLM(roteiro=[_tool("PED-1001"), RespostaLLM(texto="O pedido foi pago!")])
    resultado = montar(llm).responder(sessao, "status do PED-1001")
    # 3 idas ao LLM: tool, texto inválido, correção (regras devolvem JSON válido).
    assert len(llm.recebidas) == 3
    assert llm.recebidas[-1].mensagens[-1].conteudo.startswith("[formato]")
    assert resultado.desfecho is Desfecho.STATUS


def test_saida_invalida_duas_vezes_vira_handoff(montar: Montar, sessao: Sessao) -> None:
    llm = FakeLLM(roteiro=[RespostaLLM(texto="oi"), RespostaLLM(texto='{"resposta": 1}')])
    resultado = montar(llm).responder(sessao, "status do PED-1001")
    assert resultado.desfecho is Desfecho.HANDOFF
    assert resultado.motivo == "saida_invalida"


def test_status_inventado_sem_tool_nao_chega_ao_cliente(montar: Montar, sessao: Sessao) -> None:
    alucinacao = resposta_json("Seu pedido já foi entregue!", "entregue")
    llm = FakeLLM(roteiro=[alucinacao, alucinacao])
    resultado = montar(llm).responder(sessao, "status do PED-1001")
    assert resultado.desfecho is Desfecho.HANDOFF
    assert "entregue" not in resultado.resposta


def test_status_diferente_do_da_tool_e_rejeitado(montar: Montar, sessao: Sessao) -> None:
    errado = resposta_json("Seu pedido foi entregue.", "entregue")
    llm = FakeLLM(roteiro=[_tool("PED-1001"), errado, errado])
    resultado = montar(llm).responder(sessao, "status do PED-1001")
    assert resultado.desfecho is Desfecho.HANDOFF


def test_baixa_confianca_vira_handoff(montar: Montar, sessao: Sessao) -> None:
    llm = FakeLLM(roteiro=[resposta_json("Acho que é isso...", confianca=0.3)])
    resultado = montar(llm).responder(sessao, "status do PED-1001")
    assert (resultado.desfecho, resultado.motivo) == (Desfecho.HANDOFF, "baixa_confianca")


def test_llm_pede_humano_vira_handoff(montar: Montar, sessao: Sessao) -> None:
    llm = FakeLLM(roteiro=[resposta_json("Vou encaminhar.", precisa_humano=True)])
    resultado = montar(llm).responder(sessao, "status do PED-1001")
    assert (resultado.desfecho, resultado.motivo) == (Desfecho.HANDOFF, "llm_pediu_humano")


def test_limite_de_passos_interrompe_loop_de_tools(montar: Montar, sessao: Sessao) -> None:
    llm = FakeLLM(roteiro=[_tool("PED-1001")] * 10)
    resultado = montar(llm).responder(sessao, "status do PED-1001")
    assert (resultado.desfecho, resultado.motivo) == (Desfecho.HANDOFF, "limite_de_passos")
    assert len(llm.recebidas) == 4


@pytest.mark.parametrize("argumentos", [{"id_pedido": "../admin"}, {"id": "PED-1001"}, {}])
def test_argumento_invalido_do_llm_nao_vira_requisicao(
    montar: Montar, sessao: Sessao, argumentos: dict[str, str]
) -> None:
    llm = FakeLLM(roteiro=[RespostaLLM(chamadas=(ChamadaTool("consultar_pedido", argumentos),))])
    montar(llm).responder(sessao, "oi, e o meu pedido?")
    erro = json.loads(llm.recebidas[-1].mensagens[-1].conteudo)
    assert erro == {"erro": "id_pedido fora do formato"}


def test_tool_desconhecida_e_recusada(montar: Montar, sessao: Sessao) -> None:
    llm = FakeLLM(roteiro=[RespostaLLM(chamadas=(ChamadaTool("apagar_pedido", {}),))])
    montar(llm).responder(sessao, "oi, e o meu pedido?")
    assert json.loads(llm.recebidas[-1].mensagens[-1].conteudo) == {"erro": "tool desconhecida"}


def test_validar_saida_aceita_json_com_cerca_de_codigo() -> None:
    texto = '```json\n{"resposta": "ok", "status_pedido": null, "confianca": 1, '
    texto += '"precisa_humano": false}\n```'
    assert validar_saida(texto, None).resposta == "ok"


@pytest.mark.parametrize(
    "texto",
    [
        None,
        "",
        "texto solto",
        "[1, 2]",
        '{"resposta": "ok"}',
        '{"resposta": "", "status_pedido": null, "confianca": 1, "precisa_humano": false}',
        '{"resposta": "ok", "status_pedido": null, "confianca": 2, "precisa_humano": false}',
        '{"resposta": "ok", "status_pedido": "voando", "confianca": 1, "precisa_humano": false}',
        '{"resposta": "ok", "status_pedido": null, "confianca": 1, "precisa_humano": false,'
        ' "extra": 1}',
    ],
)
def test_validar_saida_rejeita_formatos_errados(texto: str | None) -> None:
    with pytest.raises(SaidaInvalida):
        validar_saida(texto, None)
