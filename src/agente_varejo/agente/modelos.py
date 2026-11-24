"""Tipos do agente: sessão, desfecho do turno e o schema da saída do LLM."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agente_varejo.dominio import StatusPedido
from agente_varejo.llm.base import Mensagem


class Desfecho(StrEnum):
    """Como um turno termina. É o que a avaliação compara com o esperado."""

    STATUS = "status"  # informou o status vindo da tool
    ESCLARECIMENTO = "esclarecimento"  # pediu o número do pedido
    CONFIRMACAO = "confirmacao"  # pedido não encontrado: pediu para conferir o número
    RECUSA = "recusa"  # guardrail barrou (injection, autorização, tamanho)
    HANDOFF = "handoff"  # transferiu para humano


@dataclass
class Sessao:
    """Estado de curto prazo de uma conversa. O `cliente_id` vem da autenticação."""

    cliente_id: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    historico: list[Mensagem] = field(default_factory=list)
    nao_encontrados: int = 0
    turnos: int = 0


@dataclass(frozen=True)
class ResultadoTurno:
    """Resposta ao usuário mais os metadados usados em log e avaliação."""

    resposta: str
    desfecho: Desfecho
    motivo: str
    tools_chamadas: tuple[str, ...] = ()
    status_pedido: str | None = None
    guardrails: tuple[str, ...] = ()


class SaidaAgente(BaseModel):
    """Formato obrigatório da resposta final do LLM (ver `prompts/system_v1.md`)."""

    model_config = ConfigDict(extra="forbid")

    resposta: str = Field(min_length=1, max_length=600)
    status_pedido: StatusPedido | None
    confianca: float = Field(ge=0.0, le=1.0)
    precisa_humano: bool


class SaidaInvalida(ValueError):
    """A saída do LLM não passou na validação; a mensagem diz o porquê, sem ecoar o texto."""


def _sem_cerca_de_codigo(texto: str) -> str:
    """Remove a cerca ```json ... ``` que alguns modelos colocam em volta do JSON."""
    limpo = texto.strip()
    if limpo.startswith("```"):
        limpo = limpo.split("\n", 1)[1] if "\n" in limpo else ""
        limpo = limpo.rsplit("```", 1)[0]
    return limpo.strip()


def validar_saida(texto: str | None, status_da_tool: str | None) -> SaidaAgente:
    """Valida o JSON final do LLM e confere o status contra o resultado da tool.

    A segunda checagem é o *grounding*: o modelo só pode afirmar um status que a
    tool devolveu neste turno. Status sem lastro é tratado como saída inválida.
    """
    if not texto or not texto.strip():
        raise SaidaInvalida("resposta vazia")
    try:
        dados = json.loads(_sem_cerca_de_codigo(texto))
    except json.JSONDecodeError as erro:
        raise SaidaInvalida("não é um JSON válido") from erro
    try:
        saida = SaidaAgente.model_validate(dados)
    except ValidationError as erro:
        campos = sorted({".".join(str(p) for p in e["loc"]) or "raiz" for e in erro.errors()})
        raise SaidaInvalida(f"campos inválidos: {', '.join(campos)}") from erro
    if saida.status_pedido is not None and saida.status_pedido != status_da_tool:
        raise SaidaInvalida("status_pedido não corresponde ao resultado da tool")
    return saida
