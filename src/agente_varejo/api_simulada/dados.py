"""Carga dos pedidos sintéticos e dos ids que simulam falha."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agente_varejo.config import carregar_yaml
from agente_varejo.dominio import Pedido


class FalhasSimuladas(BaseModel):
    """Ids especiais que fazem a API falhar de propósito."""

    model_config = ConfigDict(extra="forbid")

    id_timeout: str
    id_erro_500: str
    atraso_timeout_s: float = Field(ge=0)


class DadosPedidos(BaseModel):
    """Conteúdo validado de `config/pedidos.yaml`."""

    model_config = ConfigDict(extra="forbid")

    falhas_simuladas: FalhasSimuladas
    pedidos: list[Pedido]

    def por_id(self) -> dict[str, Pedido]:
        """Indexa os pedidos pelo id."""
        return {pedido.id: pedido for pedido in self.pedidos}


def carregar_pedidos(caminho_relativo: str = "config/pedidos.yaml") -> DadosPedidos:
    """Lê e valida o arquivo de pedidos sintéticos."""
    return DadosPedidos.model_validate(carregar_yaml(caminho_relativo))
