# Progresso

| Épico | Status | Branch | Comandos para reproduzir | Pendências para o Brunno |
|---|---|---|---|---|
| E0 — Fundação | concluído | `feat/e0-fundacao` | `make setup && make lint && make test` | Conferir o CI no primeiro push; avaliar fixar as actions por SHA. |
| E1 — API + agente + FakeLLM | concluído | `feat/e1-agente-tool` | `make test`; `make api` e, em outro terminal, `make chat` | **[verificar]** adaptador Gemini (`src/agente_varejo/llm/gemini.py`) nunca foi executado: testar com a sua chave (ver seção abaixo). |
| E2 — Guardrails, retry, handoff, logs | pendente | `feat/e2-guardrails` | | |
| E3 — Avaliação | pendente | `feat/e3-avaliacao` | | |
| E4 — README e estudo | pendente | `feat/e4-readme` | | |

## Itens [verificar]

- **Adaptador Gemini** — escrito a partir da documentação do SDK `google-genai`
  (3.3.0), sem execução. Pontos a conferir com a chave:
  1. `types.FunctionDeclaration(parameters_json_schema=...)` aceita o schema de
     `prompts/tools_v1.yaml`;
  2. `response.function_calls[i].name` / `.args` existem como usados;
  3. o resultado da tool é aceito com `role="tool"` e
     `Part.from_function_response`;
  4. reenviar `response.candidates[0].content` sem alteração basta para
     preservar as assinaturas de raciocínio (thought signatures);
  5. o SDK 3.x usa a API `v1` por padrão: confirmar que `system_instruction` e
     `tools` funcionam nela;
  6. o id do modelo em `config/agente.yaml` (`gemini-3.5-flash-lite`) existe e
     está na camada gratuita (a documentação consultada não confirma a
     gratuidade).
