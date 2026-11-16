"""Teste de fumaça da fundação: o pacote instala e importa."""

import agente_varejo


def test_pacote_importa_com_versao() -> None:
    assert agente_varejo.__version__ == "0.1.0"
