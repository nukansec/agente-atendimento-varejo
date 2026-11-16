# agente-atendimento-varejo

Agente de atendimento que consulta status de pedido numa API de varejo
simulada, com guardrails em código, handoff para humano e avaliação por casos.

## Comandos

- `make setup` — cria `.venv` e instala as dependências fixadas.
- `make lint` / `make format` — ruff.
- `make test` — pytest (sempre com o LLM falso, sem rede externa).
- `make eval` — roda `tests/casos/casos_v1.yaml` e imprime a taxa de acerto.
- `make api` — sobe a API simulada; `make chat` conversa com o agente.

## Regras do repositório

- Segurança fica em código (`src/agente_varejo/guardrails/` e na tool), nunca
  só no prompt. Ver `docs/adr/0001-guardrails-em-codigo.md`.
- Autorização nunca é decidida pelo LLM: o `cliente_id` vem da sessão.
- Nenhum texto chega ao LLM ou ao log sem passar pelo mascaramento de CPF.
- Prompts ficam em `prompts/`; domínio (pedidos, padrões, mensagens) em
  `config/*.yaml`. Nada de string de prompt espalhada no código.
- Testes, CI e `make eval` usam só o `FakeLLM`: precisam rodar sem chave de API.
- Só dados sintéticos. Nunca criar `.env` com valor; apenas `.env.example`.
- Sem frameworks de agente (o loop de tool calling é feito à mão), sem banco
  de dados, sem Docker obrigatório.
- Decisão não trivial vira ADR curto em `docs/adr/NNNN-titulo.md`.
- Commits: Conventional Commits em português, uma branch por épico.
