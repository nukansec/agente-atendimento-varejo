"""Retry com backoff exponencial e classificação das falhas da tool."""

from __future__ import annotations

import random
from collections.abc import Callable

import httpx
import pytest

from agente_varejo.agente.ferramentas import ClientePedidos
from agente_varejo.agente.retry import PoliticaRetry, executar_com_retry

PEDIDO = {"id": "PED-1001", "cliente_id": "CLI-001", "status": "pago", "previsao_entrega": None}


def test_espera_cresce_exponencialmente_com_jitter_limitado() -> None:
    politica = PoliticaRetry(retries=3, base_s=0.5, fator=2.0, jitter_s=0.25)
    rng = random.Random(7)
    esperas = [politica.espera(n, rng) for n in range(3)]
    for espera, base in zip(esperas, [0.5, 1.0, 2.0], strict=True):
        assert base <= espera <= base + 0.25


def test_sem_jitter_a_espera_e_exata() -> None:
    politica = PoliticaRetry(base_s=0.5, fator=2.0, jitter_s=0.0)
    assert [politica.espera(n, random.Random(0)) for n in range(3)] == [0.5, 1.0, 2.0]


def test_executa_uma_vez_quando_da_certo() -> None:
    esperas: list[float] = []
    resultado, tentativas = executar_com_retry(
        lambda: "ok", lambda r: r != "ok", PoliticaRetry(), dormir=esperas.append
    )
    assert (resultado, tentativas, esperas) == ("ok", 1, [])


def test_para_depois_de_dois_retries() -> None:
    esperas: list[float] = []
    politica = PoliticaRetry(retries=2, base_s=0.5, fator=2.0, jitter_s=0.0)
    resultado, tentativas = executar_com_retry(
        lambda: "falha", lambda r: True, politica, dormir=esperas.append
    )
    assert (resultado, tentativas) == ("falha", 3)
    assert esperas == [0.5, 1.0]  # dorme entre as tentativas, não depois da última


def _cliente(
    responder: Callable[[httpx.Request], httpx.Response], esperas: list[float]
) -> ClientePedidos:
    http = httpx.Client(transport=httpx.MockTransport(responder), base_url="http://api.teste")
    politica = PoliticaRetry(retries=2, base_s=0.5, fator=2.0, jitter_s=0.0)
    return ClientePedidos(http, politica=politica, dormir=esperas.append)


def test_tool_se_recupera_de_falha_transitoria() -> None:
    respostas = iter([httpx.Response(500), httpx.Response(503), httpx.Response(200, json=PEDIDO)])
    esperas: list[float] = []
    consulta = _cliente(lambda _: next(respostas), esperas).consultar("PED-1001")
    assert (consulta.tipo, consulta.tentativas) == ("ok", 3)
    assert esperas == [0.5, 1.0]


@pytest.mark.parametrize("codigo", [500, 502, 503, 504, 429])
def test_falha_transitoria_esgota_as_tentativas(codigo: int) -> None:
    esperas: list[float] = []
    consulta = _cliente(lambda _: httpx.Response(codigo), esperas).consultar("PED-1001")
    assert (consulta.tipo, consulta.tentativas) == ("falha", 3)
    assert consulta.detalhe == f"http_{codigo}"


def test_timeout_e_repetido_e_vira_falha() -> None:
    def estourar(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento", request=request)

    consulta = _cliente(estourar, []).consultar("PED-1001")
    assert (consulta.tipo, consulta.detalhe, consulta.tentativas) == ("falha", "timeout", 3)


def test_erro_de_conexao_e_repetido() -> None:
    def recusar(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("recusada", request=request)

    consulta = _cliente(recusar, []).consultar("PED-1001")
    assert (consulta.tipo, consulta.detalhe, consulta.tentativas) == (
        "falha",
        "rede_ConnectError",
        3,
    )


def test_404_nao_e_repetido() -> None:
    esperas: list[float] = []
    consulta = _cliente(lambda _: httpx.Response(404), esperas).consultar("PED-0000")
    assert (consulta.tipo, consulta.tentativas, esperas) == ("nao_encontrado", 1, [])


@pytest.mark.parametrize("codigo", [400, 401, 403])
def test_erro_do_cliente_nao_e_repetido(codigo: int) -> None:
    consulta = _cliente(lambda _: httpx.Response(codigo), []).consultar("PED-1001")
    assert (consulta.tipo, consulta.tentativas) == ("falha", 1)


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(200, text="<html>erro</html>"),
        httpx.Response(200, json={"id": "PED-1001"}),
        httpx.Response(200, json={**PEDIDO, "status": "teletransportado"}),
    ],
)
def test_resposta_fora_do_contrato_e_falha_sem_retry(resposta: httpx.Response) -> None:
    consulta = _cliente(lambda _: resposta, []).consultar("PED-1001")
    assert (consulta.tipo, consulta.detalhe, consulta.tentativas) == (
        "falha",
        "resposta_fora_do_contrato",
        1,
    )
