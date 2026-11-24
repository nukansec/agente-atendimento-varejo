"""API de varejo simulada (FastAPI) com pedidos sintéticos."""

from agente_varejo.api_simulada.app import app, criar_app
from agente_varejo.api_simulada.dados import DadosPedidos, carregar_pedidos
from agente_varejo.api_simulada.transporte import TransporteEmMemoria, cliente_em_memoria

__all__ = [
    "DadosPedidos",
    "TransporteEmMemoria",
    "app",
    "carregar_pedidos",
    "cliente_em_memoria",
    "criar_app",
]
