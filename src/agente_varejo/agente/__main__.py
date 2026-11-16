"""Conversa no terminal: `python -m agente_varejo.agente` (com `make api` rodando)."""

from __future__ import annotations

import argparse

import httpx

from agente_varejo.agente.modelos import Sessao
from agente_varejo.agente.nucleo import construir_agente
from agente_varejo.config import carregar_config, raiz_projeto
from agente_varejo.logs import RegistradorJSON, destino_arquivo


def main() -> None:
    """Abre um chat simples com o agente configurado em `config/agente.yaml`."""
    parser = argparse.ArgumentParser(description="Chat com o agente de atendimento.")
    parser.add_argument("--cliente", default="CLI-001", help="cliente_id da sessão (sintético)")
    argumentos = parser.parse_args()

    config = carregar_config()
    with httpx.Client(base_url=config.api.base_url, timeout=config.api.timeout_s) as http:
        # No chat o log vai para arquivo, para não se misturar com a conversa.
        caminho_log = raiz_projeto() / "logs" / "agente.jsonl"
        registrador = RegistradorJSON(destino_arquivo(caminho_log))
        agente = construir_agente(config, http, registrador=registrador)
        sessao = Sessao(cliente_id=argumentos.cliente)
        print(f"Sessão {sessao.id} · cliente {sessao.cliente_id} · LLM {config.llm.provedor}")
        print(f"Logs em {caminho_log}. Digite sua mensagem (ou 'sair').")
        while True:
            try:
                texto = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if texto.lower() in {"sair", "exit", "quit"}:
                break
            if not texto:
                continue
            resultado = agente.responder(sessao, texto)
            print(f"{resultado.resposta}  [{resultado.desfecho} · {resultado.motivo}]")


if __name__ == "__main__":
    main()
