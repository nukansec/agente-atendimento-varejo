# Alvos do projeto. Funciona em Linux/macOS e no Windows (GNU Make com cmd ou sh).
ifeq ($(OS),Windows_NT)
PY_SISTEMA ?= python
PY := "$(CURDIR)/.venv/Scripts/python.exe"
else
PY_SISTEMA ?= python3
PY := "$(CURDIR)/.venv/bin/python"
endif

.PHONY: setup lint format test api eval chat

setup: ## cria o venv e instala as dependências fixadas
	$(PY_SISTEMA) -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

lint: ## ruff: regras + formatação (sem alterar arquivos)
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

format: ## aplica correções automáticas e formatação
	$(PY) -m ruff check . --fix
	$(PY) -m ruff format .

test: ## testes unitários e de integração (LLM falso, sem rede externa)
	$(PY) -m pytest

api: ## sobe a API simulada em http://127.0.0.1:8000
	$(PY) -m uvicorn agente_varejo.api_simulada.app:app --host 127.0.0.1 --port 8000

eval: ## roda os 15 casos e imprime a taxa de acerto (exit != 0 abaixo da meta)
	$(PY) -m agente_varejo.avaliacao

chat: ## conversa no terminal (precisa de `make api` em outro terminal)
	$(PY) -m agente_varejo.agente
