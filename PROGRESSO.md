# Progresso

| Épico | Status | Branch | Comandos para reproduzir | Pendências para o Brunno |
|---|---|---|---|---|
| E0 — Fundação | concluído | `feat/e0-fundacao` | `make setup && make lint && make test` | Conferir o CI no primeiro push; avaliar fixar as actions por SHA. |
| E1 — API + agente + FakeLLM | concluído | `feat/e1-agente-tool` | `make test`; `make api` e, em outro terminal, `make chat` | **[verificar]** adaptador Gemini (`src/agente_varejo/llm/gemini.py`) nunca foi executado: testar com a sua chave (ver seção abaixo). |
| E2 — Guardrails, retry, handoff, logs | concluído | `feat/e2-guardrails` | `make test` (158 testes); `python -m pytest tests/test_guardrail_cpf.py -v` para ver os casos de borda | Revisar os padrões de `config/guardrails.yaml` (falsos positivos listados na ADR-0004). |
| E3 — Avaliação | **não iniciado** (branch criada, sem código) | `feat/e3-avaliacao` | — | Sessão interrompida por limite de uso. Falta: `tests/casos/casos_v1.yaml` (15 casos), `src/agente_varejo/avaliacao/` (runner com `__main__`), teste do exit code. `make eval` ainda falha. |
| E4 — README e estudo | **não iniciado** (branch não criada) | `feat/e4-readme` | — | Falta: README completo, `docs/estudo.md`, conferir a numeração vigente do OWASP LLM Top 10 (há indício de edição 2026). |

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

## Estado ao fim da sessão de 2026-11-16

- E0, E1 e E2 concluídos e commitados; `make lint` e `make test` (158 testes) passam.
- E3 e E4 não foram feitos. O critério de sucesso (`make eval` 15/15) **ainda não é atendido**.
- Para retomar: "Continue com o E3 do prompt; leia `PROGRESSO.md`, `docs/adr/` e o `git log` antes."
  O runner pode usar `cliente_em_memoria` (API sem socket), `RegistradorMemoria` e
  `FakeLLM.recebidas` para checar desfecho, tool chamada e CPF mascarado.
- Decisão em aberto: licença do repositório (nenhuma foi adicionada).
