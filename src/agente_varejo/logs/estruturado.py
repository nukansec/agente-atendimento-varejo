"""Log estruturado: uma linha JSON por evento, sempre com CPF mascarado."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agente_varejo.guardrails.cpf import mascarar_profundo

Destino = Callable[[str], None]


def destino_stderr(linha: str) -> None:
    """Escreve a linha no stderr (padrão: log vai para o fluxo, não para arquivo)."""
    print(linha, file=sys.stderr)


def destino_arquivo(caminho: Path) -> Destino:
    """Cria um destino que acrescenta linhas a um arquivo `.jsonl`."""
    caminho.parent.mkdir(parents=True, exist_ok=True)

    def _escrever(linha: str) -> None:
        with caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write(linha + "\n")

    return _escrever


class RegistradorJSON:
    """Serializa eventos em JSON e entrega a um ou mais destinos.

    O mascaramento acontece AQUI, na saída, sobre todas as strings do evento.
    Assim o log não depende de quem chamou ter lembrado de mascarar.
    """

    def __init__(self, *destinos: Destino) -> None:
        self._destinos = destinos or (destino_stderr,)

    def registrar(self, evento: str, **campos: Any) -> str:
        """Emite um evento e devolve a linha JSON gerada."""
        # Converte tudo para tipos JSON puros (objetos viram texto) ANTES de mascarar,
        # para que nada escape da máscara por estar "escondido" dentro de um objeto.
        puros = json.loads(json.dumps(campos, ensure_ascii=False, default=str))
        registro = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "evento": evento,
            **mascarar_profundo(puros),
        }
        linha = json.dumps(registro, ensure_ascii=False)
        for destino in self._destinos:
            destino(linha)
        return linha


class RegistradorMemoria(RegistradorJSON):
    """Guarda as linhas em memória; usado em testes e na avaliação."""

    def __init__(self) -> None:
        self.linhas: list[str] = []
        super().__init__(self.linhas.append)

    def eventos(self) -> list[dict[str, Any]]:
        """Devolve os eventos já decodificados."""
        return [json.loads(linha) for linha in self.linhas]
