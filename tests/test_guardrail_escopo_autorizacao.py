"""Escopo (só status de pedido) e autorização (só pedidos do cliente da sessão)."""

from __future__ import annotations

import pytest

from agente_varejo.dominio import Pedido
from agente_varejo.guardrails import Escopo, VerificadorEscopo, carregar_guardrails, pode_ver_pedido


@pytest.fixture(scope="module")
def escopo() -> VerificadorEscopo:
    return carregar_guardrails().escopo


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Qual o status do pedido PED-1001?", Escopo.DENTRO),
        ("ped-1002", Escopo.DENTRO),  # só o número, em minúsculas
        ("Minha encomenda já chegou?", Escopo.DENTRO),
        ("QUANDO SERÁ A ENTREGA?", Escopo.DENTRO),
        ("O rastreamento não atualiza", Escopo.DENTRO),
        ("Quero falar com um advogado sobre o pedido PED-1001", Escopo.FORA),
        ("Vou processar a loja e acionar o Procon", Escopo.FORA),
        ("QUERO MEU REEMBOLSO", Escopo.FORA),
        ("Como faço a devolução do pedido PED-1004?", Escopo.FORA),
        ("Tenho uma reclamação jurídica", Escopo.FORA),
        ("oi", Escopo.INDEFINIDO),
        ("Qual a previsão do tempo para amanhã?", Escopo.DENTRO),  # falso positivo conhecido
        ("Me conta uma piada", Escopo.INDEFINIDO),
        ("", Escopo.INDEFINIDO),
    ],
)
def test_classificacao(escopo: VerificadorEscopo, texto: str, esperado: Escopo) -> None:
    assert escopo.classificar(texto) is esperado


def _pedido(cliente_id: str) -> Pedido:
    return Pedido(id="PED-1001", cliente_id=cliente_id, status="pago")


def test_cliente_ve_o_proprio_pedido() -> None:
    assert pode_ver_pedido("CLI-001", _pedido("CLI-001"))


@pytest.mark.parametrize("cliente_da_sessao", ["CLI-002", "cli-001", "CLI-001 ", ""])
def test_cliente_nao_ve_pedido_de_outro(cliente_da_sessao: str) -> None:
    assert not pode_ver_pedido(cliente_da_sessao, _pedido("CLI-001"))
