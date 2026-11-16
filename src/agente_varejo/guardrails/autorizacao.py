"""Autorização: decidida em código, nunca pelo LLM."""

from __future__ import annotations

from agente_varejo.dominio import Pedido


def pode_ver_pedido(cliente_da_sessao: str, pedido: Pedido) -> bool:
    """O cliente da sessão só enxerga os próprios pedidos.

    `cliente_da_sessao` vem da sessão autenticada. Ele nunca é lido do texto do
    usuário nem de argumento gerado pelo modelo — por isso nenhuma frase
    ("sou o gerente", "ignore as regras") consegue mudar o resultado.
    """
    return bool(cliente_da_sessao) and pedido.cliente_id == cliente_da_sessao
