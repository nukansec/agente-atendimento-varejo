# Progresso

Estado: os cinco épicos (E0–E4) estão concluídos e mesclados na `main`. Num
clone limpo, `make setup`, `make lint`, `make test` (164 testes) e `make eval`
(15/15) passam sem chave de API. Pendências e próximos passos ficam nas
[issues](../../issues) do repositório.

## Épicos

| Épico | Entregas | Como reproduzir |
|---|---|---|
| E0 — Fundação | `.gitignore`, `.env.example`, `pyproject.toml` com versões fixadas, ruff, pytest, `Makefile`, CI, `docs/arquitetura.md`, ADR-0001, `CLAUDE.md` | `make setup && make lint && make test` |
| E1 — API, agente e FakeLLM | API FastAPI com 6 pedidos sintéticos e 2 ids de falha; interface `LLMClient`; `FakeLLM`; adaptador Gemini; loop de tool calling; validação de saída; system prompt v1; ADR-0002 e 0003 | `make test`; `make api` e, em outro terminal, `make chat` |
| E2 — Guardrails, retry, handoff, logs | CPF, injection, escopo, autorização; retry com backoff e jitter; handoff; log JSON mascarado; ADR-0004 | `make test`; `python -m pytest tests/test_guardrail_cpf.py -v` para os casos de borda |
| E3 — Avaliação | 15 casos em YAML; runner com tabela, taxa e exit code; avaliação no CI; ADR-0005 | `make eval`; `python -m agente_varejo.avaliacao --meta 0.9` |
| E4 — README | README completo com riscos (OWASP LLM Top 10), mitigações e avaliação | `make eval` reproduz a saída colada no README |

## Itens a verificar no adaptador Gemini

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

## Por que cada decisão

- **Guardrails em código (ADR-0001).** Um LLM não separa instrução de dado de
  forma garantida, então regra no prompt é contornável. Código é determinístico
  e testável com teste unitário comum.
- **Autorização na tool, com o `cliente_id` da sessão.** A tool exposta ao
  modelo só tem `id_pedido`. Mesmo um modelo totalmente dominado não consegue
  pedir dado de outro cliente, porque a decisão não passa por ele.
- **LLM atrás de interface + `FakeLLM` (ADR-0002).** É o que permite rodar sem
  chave e sem rede. O modo *roteiro* simula o modelo errando; o modo *regras*
  simula o modelo colaborando.
- **API chamada em memória (ADR-0003).** Um transporte httpx próprio executa o
  app FastAPI sem abrir porta e aplica o timeout de verdade. O `TestClient` foi
  descartado porque ignora timeout e, nesta versão, está obsoleto com `httpx`.
- **CPF mascarado pelo formato, e de novo no registrador de log (ADR-0004).**
  Validar dígito verificador criaria falso negativo no dado sensível. Mascarar
  na saída do log tira a garantia da disciplina de quem chama.
- **Injection com pesos.** Sinal forte bloqueia sozinho; sinal fraco precisa de
  dois. Reduz o falso positivo sem abrir mão dos ataques óbvios.
- **Texto barrado fora do histórico.** Evita que um ataque recusado volte ao
  contexto do modelo no turno seguinte.
- **Desfechos decididos pelo código.** Não encontrado, API fora e pedido de
  outro cliente usam mensagem fixa; o LLM só redige quando há status real.
- **Grounding na validação.** O status do modelo precisa ser igual ao da tool
  no turno; é a mitigação concreta de alucinação.
- **Retry próprio.** Cerca de 20 linhas, com `dormir` e `rng` injetáveis; só
  falha transitória é repetida, com teto baixo para não agravar sobrecarga.
- **Avaliação sobre comportamento, não texto (ADR-0005).** Texto muda a cada
  modelo; desfecho, tool e status não deveriam mudar.

Decisões pequenas tomadas sem ADR: o limite de tamanho da entrada foi
adicionado como guardrail extra (LLM10); a avaliação também roda no CI.

## Comandos úteis

```bash
make setup && make lint && make test && make eval
make api      # terminal 1
make chat     # terminal 2
python -m agente_varejo.avaliacao --meta 0.9        # sobrepõe a meta
python -m pytest tests/test_fluxos_guardrails.py -v # fluxos de ponta a ponta
```

## Riscos e dívidas técnicas

- O 15/15 vem do LLM falso: mede o pipeline, não o modelo.
- Detector de injection burlável por paráfrase e outros idiomas; falsos
  positivos conhecidos ("aja como…", "previsão do tempo").
- Só CPF é mascarado; o log guarda o texto livre do cliente.
- Falha do LLM real (rede, cota) não é tratada: estoura exceção em vez de
  virar handoff.
- A recusa por autorização revela que o pedido existe.
- Alguns commits intermediários do E2 não passam nos testes isoladamente (a
  ponta da `main` passa).
- `make chat` não foi executado; o caminho HTTP real (uvicorn + agente) foi
  verificado uma vez à mão, sem teste automatizado.
- Sem registro de tokens/custo nem métricas agregadas.
- Numeração do OWASP conferida na página oficial (edição 2025); não foi
  possível descartar uma edição mais nova.
