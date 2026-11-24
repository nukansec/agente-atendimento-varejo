"""Registrador de log: formato JSON e mascaramento na saída."""

from __future__ import annotations

import json
from pathlib import Path

from agente_varejo.guardrails import MASCARA_CPF, contem_cpf
from agente_varejo.logs import RegistradorJSON, RegistradorMemoria, destino_arquivo


class _ObjetoComCpf:
    def __str__(self) -> str:
        return "cliente com cpf 123.456.789-09"


def test_cada_evento_e_uma_linha_json_com_ts_e_evento() -> None:
    registros = RegistradorMemoria()
    registros.registrar("turno", desfecho="status", latencia_ms=12.5)
    (evento,) = registros.eventos()
    assert evento["evento"] == "turno"
    assert evento["desfecho"] == "status"
    assert evento["latencia_ms"] == 12.5
    assert evento["ts"].endswith("+00:00")
    assert "\n" not in registros.linhas[0]


def test_registrador_mascara_mesmo_se_quem_chamou_esqueceu() -> None:
    registros = RegistradorMemoria()
    registros.registrar(
        "teste",
        texto="cpf 123.456.789-09",
        aninhado={"lista": ["12345678909", {"k": "987 654 321 00"}]},
        numero=12345678909,
        objeto=_ObjetoComCpf(),
    )
    linha = registros.linhas[0]
    assert not contem_cpf(linha)
    assert linha.count(MASCARA_CPF) == 5
    json.loads(linha)  # continua sendo JSON válido depois da máscara


def test_destino_arquivo_acrescenta_linhas(tmp_path: Path) -> None:
    caminho = tmp_path / "logs" / "agente.jsonl"
    registrador = RegistradorJSON(destino_arquivo(caminho))
    registrador.registrar("a", cpf="123.456.789-09")
    registrador.registrar("b")
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    assert [json.loads(linha)["evento"] for linha in linhas] == ["a", "b"]
    assert not contem_cpf(linhas[0])
