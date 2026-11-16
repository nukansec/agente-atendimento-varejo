"""Guardrails em código: CPF, prompt injection, escopo e autorização."""

from __future__ import annotations

from dataclasses import dataclass

from agente_varejo.config import carregar_yaml
from agente_varejo.guardrails.autorizacao import pode_ver_pedido
from agente_varejo.guardrails.cpf import MASCARA_CPF, contem_cpf, mascarar_cpf, mascarar_profundo
from agente_varejo.guardrails.escopo import Escopo, VerificadorEscopo
from agente_varejo.guardrails.injection import DetectorInjection, ResultadoInjection
from agente_varejo.guardrails.texto import normalizar


@dataclass(frozen=True)
class Guardrails:
    """Guardrails de entrada que dependem da política em YAML."""

    injection: DetectorInjection
    escopo: VerificadorEscopo


def carregar_guardrails(caminho_relativo: str = "config/guardrails.yaml") -> Guardrails:
    """Monta os guardrails a partir de `config/guardrails.yaml`."""
    politica = carregar_yaml(caminho_relativo)
    return Guardrails(
        injection=DetectorInjection.da_politica(politica["injection"]),
        escopo=VerificadorEscopo.da_politica(politica["escopo"]),
    )


__all__ = [
    "MASCARA_CPF",
    "DetectorInjection",
    "Escopo",
    "Guardrails",
    "ResultadoInjection",
    "VerificadorEscopo",
    "carregar_guardrails",
    "contem_cpf",
    "mascarar_cpf",
    "mascarar_profundo",
    "normalizar",
    "pode_ver_pedido",
]
