"""Fixtures compartilhadas: API em memória, configuração e fábrica de agente."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import httpx
import pytest

from agente_varejo.agente import Agente, Sessao, construir_agente
from agente_varejo.api_simulada import carregar_pedidos, criar_app
from agente_varejo.api_simulada.transporte import cliente_em_memoria
from agente_varejo.config import ConfigAgente, carregar_config
from agente_varejo.llm import FakeLLM, LLMClient
from agente_varejo.logs import RegistradorMemoria

CLIENTE = "CLI-001"


@pytest.fixture(scope="session")
def config() -> ConfigAgente:
    """Configuração real do repositório (`config/agente.yaml`)."""
    return carregar_config()


@pytest.fixture
def http() -> Iterator[httpx.Client]:
    """Cliente HTTP ligado direto à API simulada, sem abrir porta."""
    dados = carregar_pedidos()
    dados.falhas_simuladas.atraso_timeout_s = 0.0
    with cliente_em_memoria(criar_app(dados), timeout_s=2.0) as cliente:
        yield cliente


@pytest.fixture
def registros() -> RegistradorMemoria:
    """Log em memória do teste (para verificar o que foi registrado)."""
    return RegistradorMemoria()


@pytest.fixture
def esperas() -> list[float]:
    """Esperas de backoff pedidas no teste (ninguém dorme de verdade)."""
    return []


@pytest.fixture
def montar(
    config: ConfigAgente,
    http: httpx.Client,
    registros: RegistradorMemoria,
    esperas: list[float],
) -> Callable[..., Agente]:
    """Fábrica de agente; por padrão usa o `FakeLLM` em modo de regras."""

    def _montar(llm: LLMClient | None = None, cliente_http: httpx.Client | None = None) -> Agente:
        return construir_agente(
            config,
            cliente_http or http,
            llm=llm or FakeLLM(),
            registrador=registros,
            dormir=esperas.append,
        )

    return _montar


@pytest.fixture
def sessao() -> Sessao:
    """Sessão do cliente sintético padrão."""
    return Sessao(cliente_id=CLIENTE)
