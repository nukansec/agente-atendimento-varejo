"""A avaliação acerta com o agente correto e FALHA quando o agente erra."""

from __future__ import annotations

from collections import Counter

import pytest

from agente_varejo.avaliacao import avaliar, carregar_casos, executar_caso, formatar
from agente_varejo.avaliacao.__main__ import main
from agente_varejo.config import ConfigAgente
from agente_varejo.llm import FakeLLM, RespostaLLM, resposta_json


def test_conjunto_v1_tem_a_composicao_combinada() -> None:
    conjunto = carregar_casos()
    assert len(conjunto.casos) == 15
    assert len({caso.id for caso in conjunto.casos}) == 15
    assert Counter(caso.categoria for caso in conjunto.casos) == {
        "normal": 5,
        "inexistente": 2,
        "cpf": 2,
        "injection": 3,
        "falha_api": 2,
        "fora_do_escopo": 1,
    }


def test_agente_acerta_os_15_casos(config: ConfigAgente) -> None:
    relatorio = avaliar(carregar_casos(), config)
    assert [(r.caso.id, r.falhas) for r in relatorio.resultados if not r.passou] == []
    assert (relatorio.acertos, relatorio.taxa, relatorio.atingiu_meta) == (15, 1.0, True)


def test_llm_que_erra_derruba_a_taxa(config: ConfigAgente) -> None:
    """Prova que o gate detecta regressão: um modelo que nunca chama a tool reprova."""

    def llm_preguicoso() -> FakeLLM:
        return FakeLLM(roteiro=[resposta_json("Não sei, qual é o número?")] * 20)

    relatorio = avaliar(carregar_casos(), config, criar_llm=llm_preguicoso)
    assert not relatorio.atingiu_meta
    reprovados = {r.caso.id for r in relatorio.resultados if not r.passou}
    assert {"N1", "N2", "N3", "N5", "I1", "C1", "J3", "F1", "F2"} <= reprovados
    # Os casos barrados antes do LLM continuam passando: não dependem do modelo.
    assert {"J1", "J2", "E1"}.isdisjoint(reprovados)
    assert "ABAIXO DA META" in formatar(relatorio)


def test_cpf_em_saida_invalida_do_llm_nao_volta_para_ele(config: ConfigAgente) -> None:
    caso = next(c for c in carregar_casos().casos if c.id == "C2")
    eco = RespostaLLM(texto='{"resposta": "cpf 111.444.777-35 anotado", "status_pedido": null,')
    resultado = executar_caso(caso, "CLI-001", config, lambda: FakeLLM(roteiro=[eco]))
    # Saída inválida -> pedido de correção. O texto rejeitado é reenviado mascarado.
    assert resultado.falhas == ()


def test_cli_sai_com_zero_quando_atinge_a_meta(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    saida = capsys.readouterr().out
    assert "Taxa de acerto: 15/15 (100%)" in saida
    assert "meta atingida" in saida


def test_cli_sai_com_um_abaixo_da_meta(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regressão de exit code: com os casos esperando o impossível, o gate tem de falhar."""
    import agente_varejo.avaliacao.__main__ as cli

    conjunto = carregar_casos()
    primeiro = conjunto.casos[0]
    errado = primeiro.model_copy(
        update={"esperado": primeiro.esperado.model_copy(update={"status": "cancelado"})}
    )
    adulterado = conjunto.model_copy(update={"casos": [errado, *conjunto.casos[1:]]})
    monkeypatch.setattr(cli, "carregar_casos", lambda _caminho: adulterado)

    assert main([]) == 1
    saida = capsys.readouterr().out
    assert "14/15" in saida
    assert "! N1: status=pago (esperado cancelado)" in saida
