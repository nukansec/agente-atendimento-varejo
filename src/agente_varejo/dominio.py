"""Tipos do domínio compartilhados entre a API simulada e o agente."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

StatusPedido = Literal["pago", "separando", "enviado", "entregue", "cancelado", "atrasado"]

FORMATO_ID_PEDIDO = r"PED-\d{4}"
"""Formato do número de pedido. Tudo que foge disso é rejeitado antes de virar URL."""

PADRAO_ID_PEDIDO = re.compile(rf"\b{FORMATO_ID_PEDIDO}\b", re.IGNORECASE)


class Pedido(BaseModel):
    """Pedido como a API de varejo devolve (contrato da resposta)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=rf"^{FORMATO_ID_PEDIDO}$")
    cliente_id: str = Field(pattern=r"^CLI-\d{3}$")
    status: StatusPedido
    previsao_entrega: str | None = None
