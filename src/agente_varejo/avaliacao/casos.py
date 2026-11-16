"""Schema e carga do conjunto de casos de avaliação."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agente_varejo.agente.modelos import Desfecho
from agente_varejo.config import carregar_yaml
from agente_varejo.dominio import StatusPedido

CASOS_PADRAO = "tests/casos/casos_v1.yaml"


class _Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Esperado(_Estrito):
    """O que o último turno do caso deve produzir."""

    tool: Literal["consultar_pedido", "nenhuma"]
    desfecho: Desfecho
    cpf_mascarado: bool
    status: StatusPedido | None = None
    motivo: str | None = None
    tentativas_api: int | None = None


class Caso(_Estrito):
    """Um caso de avaliação: conversa de um ou mais turnos e o resultado esperado."""

    id: str
    categoria: str
    turnos: list[str] = Field(min_length=1)
    esperado: Esperado


class ConjuntoDeCasos(_Estrito):
    """Arquivo de casos completo."""

    versao: int
    meta: float = Field(ge=0.0, le=1.0)
    cliente_id: str
    casos: list[Caso] = Field(min_length=1)


def carregar_casos(caminho_relativo: str = CASOS_PADRAO) -> ConjuntoDeCasos:
    """Lê e valida o YAML de casos (erro claro se um caso estiver malformado)."""
    return ConjuntoDeCasos.model_validate(carregar_yaml(caminho_relativo))
