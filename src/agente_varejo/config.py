"""Localização da raiz do projeto e carga validada dos arquivos de configuração."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

VAR_RAIZ = "AGENTE_VAREJO_RAIZ"


def raiz_projeto() -> Path:
    """Devolve a pasta que contém `config/` e `prompts/`.

    Por padrão é a raiz do repositório (layout `src/`); a variável de ambiente
    `AGENTE_VAREJO_RAIZ` permite apontar para outro lugar.
    """
    personalizada = os.environ.get(VAR_RAIZ)
    if personalizada:
        return Path(personalizada)
    return Path(__file__).resolve().parents[2]


def carregar_yaml(caminho_relativo: str) -> Any:
    """Lê um YAML relativo à raiz do projeto usando o carregador seguro."""
    with (raiz_projeto() / caminho_relativo).open(encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def ler_texto(caminho_relativo: str) -> str:
    """Lê um arquivo de texto (ex.: prompt) relativo à raiz do projeto."""
    return (raiz_projeto() / caminho_relativo).read_text(encoding="utf-8")


class _Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConfigLLM(_Estrito):
    """Provedor e parâmetros de geração."""

    provedor: Literal["fake", "gemini"] = "fake"
    modelo: str
    temperatura: float = Field(ge=0.0, le=2.0)


class ConfigAPI(_Estrito):
    """Como o agente fala com a API de pedidos."""

    base_url: str
    timeout_s: float = Field(gt=0)
    retries: int = Field(ge=0, le=5)
    backoff_base_s: float = Field(ge=0)
    backoff_fator: float = Field(ge=1)
    jitter_s: float = Field(ge=0)


class ConfigLoop(_Estrito):
    """Limites do loop do agente."""

    prompt_sistema: str
    definicao_tools: str
    max_passos: int = Field(ge=1, le=10)
    limiar_confianca: float = Field(ge=0.0, le=1.0)
    max_chars_entrada: int = Field(ge=1)


class ConfigAgente(_Estrito):
    """Conteúdo de `config/agente.yaml`."""

    llm: ConfigLLM
    api: ConfigAPI
    agente: ConfigLoop


def carregar_config(caminho_relativo: str = "config/agente.yaml") -> ConfigAgente:
    """Carrega e valida a configuração do agente (erro claro se o YAML estiver errado)."""
    return ConfigAgente.model_validate(carregar_yaml(caminho_relativo))


def carregar_mensagens(caminho_relativo: str = "config/mensagens.yaml") -> dict[str, str]:
    """Carrega os textos fixos enviados pelo código (recusa, handoff...)."""
    dados = carregar_yaml(caminho_relativo)
    return {chave: str(valor).strip() for chave, valor in dados.items()}
