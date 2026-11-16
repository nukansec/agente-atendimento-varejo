"""Logs estruturados em JSON com mascaramento na saída."""

from agente_varejo.logs.estruturado import (
    RegistradorJSON,
    RegistradorMemoria,
    destino_arquivo,
    destino_stderr,
)

__all__ = ["RegistradorJSON", "RegistradorMemoria", "destino_arquivo", "destino_stderr"]
