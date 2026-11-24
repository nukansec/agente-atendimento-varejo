"""Mascaramento de CPF, com casos de borda. Todos os CPFs aqui são fictícios."""

from __future__ import annotations

import pytest

from agente_varejo.guardrails import MASCARA_CPF, contem_cpf, mascarar_cpf, mascarar_profundo


@pytest.mark.parametrize(
    "cpf",
    [
        "123.456.789-09",  # com pontuação
        "12345678909",  # só dígitos
        "123 456 789 09",  # com espaços
        "123.456.789 09",  # pontuação misturada
        "123456789-09",
        "111.111.111-11",  # dígitos verificadores inválidos: mascara mesmo assim
        "123.456.789-00",  # idem
    ],
)
def test_mascara_formatos_de_cpf(cpf: str) -> None:
    texto, quantidade = mascarar_cpf(cpf)
    assert texto == MASCARA_CPF
    assert quantidade == 1


def test_cpf_no_meio_do_texto_preserva_o_resto() -> None:
    texto, quantidade = mascarar_cpf("Oi, meu CPF é 123.456.789-09 e o pedido é PED-1001, ok?")
    assert texto == f"Oi, meu CPF é {MASCARA_CPF} e o pedido é PED-1001, ok?"
    assert quantidade == 1


def test_cpf_colado_em_letras_e_pontuacao() -> None:
    assert mascarar_cpf("cpf:12345678909.")[0] == f"cpf:{MASCARA_CPF}."
    assert mascarar_cpf("(123.456.789-09)")[0] == f"({MASCARA_CPF})"
    assert mascarar_cpf("CPF12345678909fim")[0] == f"CPF{MASCARA_CPF}fim"


def test_varios_cpfs_e_quebra_de_linha() -> None:
    texto, quantidade = mascarar_cpf("123.456.789-09\n987.654.321-00 e 11144477735")
    assert quantidade == 3
    assert not contem_cpf(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "PED-1001",
        "1234567890",  # 10 dígitos
        "123456789012",  # 12 dígitos
        "12.345.678/0001-99",  # CNPJ formatado
        "12345678000199",  # CNPJ sem pontuação (14 dígitos)
        "previsão 2026-11-25, pedido PED-1003",
        "CEP 74000-000",
        "",
    ],
)
def test_nao_mascara_o_que_nao_e_cpf(texto: str) -> None:
    assert mascarar_cpf(texto) == (texto, 0)


def test_mascarar_e_idempotente() -> None:
    uma_vez = mascarar_cpf("cpf 123.456.789-09")[0]
    assert mascarar_cpf(uma_vez) == (uma_vez, 0)


def test_mascarar_profundo_percorre_estruturas() -> None:
    entrada = {
        "texto": "cpf 123.456.789-09",
        "lista": ["12345678909", {"aninhado": ("ok", "987.654.321-00")}],
        "numero": 12345678909,
        "outros": [42, 3.5, True, None],
        "111.444.777-35": "cpf na chave",
    }
    assert mascarar_profundo(entrada) == {
        "texto": f"cpf {MASCARA_CPF}",
        "lista": [MASCARA_CPF, {"aninhado": ["ok", MASCARA_CPF]}],
        "numero": MASCARA_CPF,
        "outros": [42, 3.5, True, None],
        MASCARA_CPF: "cpf na chave",
    }
