"""Transporte httpx que chama a API simulada em memória, respeitando o timeout.

Permite que testes e `make eval` exercitem a API FastAPI de verdade sem abrir
porta nem depender de rede. O timeout de leitura configurado no cliente é
aplicado aqui, então o cenário "API lenta" gera um `httpx.ReadTimeout` real.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

URL_BASE_EM_MEMORIA = "http://api.simulada"


class TransporteEmMemoria(httpx.BaseTransport):
    """Ponte síncrona sobre `httpx.ASGITransport` (que só existe em versão assíncrona)."""

    def __init__(self, app: Any) -> None:
        self._asgi = httpx.ASGITransport(app=app)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Executa a requisição no app ASGI e devolve a resposta já lida."""
        limite = request.extensions.get("timeout", {}).get("read")

        async def _enviar() -> httpx.Response:
            resposta = await self._asgi.handle_async_request(request)
            corpo = await resposta.aread()
            await resposta.aclose()
            return httpx.Response(resposta.status_code, headers=resposta.headers, content=corpo)

        async def _com_limite() -> httpx.Response:
            return await asyncio.wait_for(_enviar(), timeout=limite)

        try:
            return asyncio.run(_com_limite())
        except TimeoutError as erro:
            raise httpx.ReadTimeout("tempo de leitura esgotado", request=request) from erro


def cliente_em_memoria(app: Any, timeout_s: float) -> httpx.Client:
    """Cria um `httpx.Client` ligado direto ao app, sem socket."""
    return httpx.Client(
        transport=TransporteEmMemoria(app), base_url=URL_BASE_EM_MEMORIA, timeout=timeout_s
    )
