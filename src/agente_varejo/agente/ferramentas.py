"""A única tool do agente: `consultar_pedido`, sobre a API de varejo."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agente_varejo.config import carregar_yaml
from agente_varejo.dominio import FORMATO_ID_PEDIDO, Pedido
from agente_varejo.llm.base import DefinicaoTool

NOME_TOOL = "consultar_pedido"

TipoResultado = Literal["ok", "nao_encontrado", "falha", "argumento_invalido"]


class ArgumentosConsulta(BaseModel):
    """Argumentos aceitos da tool. O que o LLM gera é entrada não confiável."""

    model_config = ConfigDict(extra="forbid")

    id_pedido: str = Field(pattern=rf"^{FORMATO_ID_PEDIDO}$")


@dataclass(frozen=True)
class ResultadoConsulta:
    """Resultado de uma execução da tool, já classificado."""

    tipo: TipoResultado
    id_pedido: str | None = None
    pedido: Pedido | None = None
    tentativas: int = 1
    detalhe: str = ""

    def para_llm(self) -> str:
        """Serializa só o que o modelo precisa ver (sem `cliente_id`)."""
        if self.tipo == "ok" and self.pedido is not None:
            corpo: dict[str, Any] = {
                "encontrado": True,
                "id_pedido": self.pedido.id,
                "status": self.pedido.status,
                "previsao_entrega": self.pedido.previsao_entrega,
            }
        elif self.tipo == "nao_encontrado":
            corpo = {"encontrado": False, "id_pedido": self.id_pedido}
        else:
            corpo = {"erro": self.detalhe or self.tipo}
        return json.dumps(corpo, ensure_ascii=False)


def validar_argumentos(argumentos: dict[str, Any]) -> str | None:
    """Devolve o `id_pedido` normalizado, ou `None` se os argumentos forem inválidos."""
    bruto = argumentos.get("id_pedido")
    if isinstance(bruto, str):
        argumentos = {**argumentos, "id_pedido": bruto.strip().upper()}
    try:
        return ArgumentosConsulta.model_validate(argumentos).id_pedido
    except ValidationError:
        return None


class ClientePedidos:
    """Cliente HTTP da API de pedidos. Recebe o `httpx.Client` pronto (injeção)."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def consultar(self, id_pedido: str) -> ResultadoConsulta:
        """Busca um pedido e classifica o resultado em ok / não encontrado / falha."""
        try:
            resposta = self._http.get(f"/pedidos/{id_pedido}")
        except httpx.HTTPError as erro:
            return ResultadoConsulta("falha", id_pedido, detalhe=type(erro).__name__)
        if resposta.status_code == 404:
            return ResultadoConsulta("nao_encontrado", id_pedido)
        if resposta.status_code != 200:
            return ResultadoConsulta("falha", id_pedido, detalhe=f"http_{resposta.status_code}")
        try:
            pedido = Pedido.model_validate(resposta.json())
        except (ValueError, ValidationError):
            return ResultadoConsulta("falha", id_pedido, detalhe="resposta_fora_do_contrato")
        return ResultadoConsulta("ok", id_pedido, pedido=pedido)


def carregar_definicoes_tools(caminho_relativo: str) -> list[DefinicaoTool]:
    """Lê de `prompts/` as definições de tool enviadas ao LLM."""
    return [
        DefinicaoTool(nome=item["nome"], descricao=item["descricao"], parametros=item["parametros"])
        for item in carregar_yaml(caminho_relativo)
    ]
