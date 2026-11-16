"""Contrato da API simulada."""

from __future__ import annotations

import httpx
import pytest

from agente_varejo.api_simulada import carregar_pedidos, criar_app
from agente_varejo.api_simulada.transporte import cliente_em_memoria


def test_health(http: httpx.Client) -> None:
    assert http.get("/health").json() == {"status": "ok"}


def test_seis_pedidos_com_status_distintos() -> None:
    pedidos = carregar_pedidos().pedidos
    assert len(pedidos) == 6
    assert {p.status for p in pedidos} == {
        "pago",
        "separando",
        "enviado",
        "entregue",
        "cancelado",
        "atrasado",
    }


def test_pedido_existente(http: httpx.Client) -> None:
    resposta = http.get("/pedidos/PED-1003")
    assert resposta.status_code == 200
    assert resposta.json() == {
        "id": "PED-1003",
        "cliente_id": "CLI-001",
        "status": "enviado",
        "previsao_entrega": "2026-11-20",
    }


def test_pedido_inexistente_devolve_404(http: httpx.Client) -> None:
    assert http.get("/pedidos/PED-0000").status_code == 404


@pytest.mark.parametrize(("id_pedido", "codigo"), [("PED-9001", 504), ("PED-9002", 500)])
def test_ids_especiais_forcam_falha(http: httpx.Client, id_pedido: str, codigo: int) -> None:
    assert http.get(f"/pedidos/{id_pedido}").status_code == codigo


def test_api_lenta_estoura_o_timeout_do_cliente() -> None:
    dados = carregar_pedidos()
    dados.falhas_simuladas.atraso_timeout_s = 0.5
    with (
        cliente_em_memoria(criar_app(dados), timeout_s=0.05) as cliente,
        pytest.raises(httpx.ReadTimeout),
    ):
        cliente.get("/pedidos/PED-9001")
