"""Aplicação FastAPI que simula o sistema de pedidos da loja."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException

from agente_varejo.api_simulada.dados import DadosPedidos, carregar_pedidos
from agente_varejo.dominio import Pedido


def criar_app(dados: DadosPedidos | None = None) -> FastAPI:
    """Monta a API. `dados` permite injetar pedidos e atrasos nos testes."""
    dados = dados or carregar_pedidos()
    pedidos = dados.por_id()
    falhas = dados.falhas_simuladas
    api = FastAPI(title="API simulada de varejo", version="0.1.0")

    @api.get("/health")
    async def health() -> dict[str, str]:
        """Sinal de vida usado para saber se o servidor subiu."""
        return {"status": "ok"}

    @api.get("/pedidos/{id_pedido}")
    async def obter_pedido(id_pedido: str) -> Pedido:
        """Devolve o pedido; dois ids especiais simulam timeout e erro 500."""
        if id_pedido == falhas.id_timeout:
            # Segura a resposta além do timeout do cliente. Se o cliente esperar
            # mesmo assim, recebe 504: o desfecho é falha nos dois casos.
            await asyncio.sleep(falhas.atraso_timeout_s)
            raise HTTPException(status_code=504, detail="tempo esgotado no sistema de pedidos")
        if id_pedido == falhas.id_erro_500:
            raise HTTPException(status_code=500, detail="erro interno simulado")
        pedido = pedidos.get(id_pedido)
        if pedido is None:
            raise HTTPException(status_code=404, detail="pedido não encontrado")
        return pedido

    return api


app = criar_app()
