# Progresso

| Épico | Status | Branch | Comandos para reproduzir | Pendências para o Brunno |
|---|---|---|---|---|
| E0 — Fundação | concluído | `feat/e0-fundacao` | `make setup && make lint && make test` | Conferir o CI no primeiro push; avaliar fixar as actions por SHA. |
| E1 — API + agente + FakeLLM | concluído | `feat/e1-agente-tool` | `make test`; `make api` e, em outro terminal, `make chat` | **[verificar]** adaptador Gemini (`src/agente_varejo/llm/gemini.py`) nunca foi executado: testar com a sua chave (ver seção abaixo). |
| E2 — Guardrails, retry, handoff, logs | concluído | `feat/e2-guardrails` | `make test`; `python -m pytest tests/test_guardrail_cpf.py -v` para ver os casos de borda | Revisar os padrões de `config/guardrails.yaml` (falsos positivos listados na ADR-0004). |
| E3 — Avaliação | concluído | `feat/e3-avaliacao` | `make eval` (15/15); `python -m agente_varejo.avaliacao --meta 0.9` | Rodar `python -m agente_varejo.avaliacao --llm gemini` com a sua chave: é só aí que o modelo é avaliado de fato. |
| E4 — README e estudo | concluído | `feat/e4-readme` | abrir `README.md` e `docs/estudo.md`; `make eval` reproduz a saída colada no README | Ler `docs/estudo.md` conferindo as linhas citadas; reescrever as fichas com as suas palavras. |

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

---

# Relatório final (2026-11-16)

Estado: os cinco épicos estão concluídos. Num clone limpo, `make setup`,
`make lint`, `make test` (164 testes) e `make eval` (15/15) passam sem chave de
API. Nada foi enviado para fora: sem remote, push ou PR.

## a) O que foi feito

| Épico | Branch | Entregas |
|---|---|---|
| E0 | `feat/e0-fundacao` | `.gitignore`, `.env.example`, `pyproject.toml` com versões fixadas, ruff, pytest, `Makefile`, CI, `docs/arquitetura.md`, ADR-0001, `CLAUDE.md` |
| E1 | `feat/e1-agente-tool` | API FastAPI com 6 pedidos sintéticos e 2 ids de falha; interface `LLMClient`; `FakeLLM`; adaptador Gemini; loop de tool calling; validação de saída; system prompt v1; ADR-0002 e 0003 |
| E2 | `feat/e2-guardrails` | CPF, injection, escopo, autorização; retry com backoff e jitter; handoff; log JSON mascarado; ADR-0004 |
| E3 | `feat/e3-avaliacao` | 15 casos em YAML; runner com tabela, taxa e exit code; avaliação no CI; ADR-0005 |
| E4 | `feat/e4-readme` | README completo; `docs/estudo.md` |

Cada branch parte da anterior; `feat/e4-readme` contém tudo.

## b) Por que cada decisão

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

Decisões pequenas tomadas sem ADR: `docs/estudo.md` traz 3 perguntas de
avaliador no total (não 3 por ficha); o limite de tamanho da entrada foi
adicionado como guardrail extra (LLM10); a avaliação também roda no CI.

## c) Comandos para reproduzir

```bash
git switch feat/e4-readme
make setup && make lint && make test && make eval
make api      # terminal 1
make chat     # terminal 2
python -m agente_varejo.avaliacao --meta 0.9        # sobrepõe a meta
python -m pytest tests/test_fluxos_guardrails.py -v # fluxos de ponta a ponta
```

## d) Descrição de PR

**Título:** feat: agente de atendimento com guardrails em código, handoff e avaliação

**O quê.** Agente que informa status de pedido por tool calling sobre uma API
FastAPI simulada. Inclui mascaramento de CPF, detector de prompt injection,
checagem de escopo, autorização fora do LLM, retry com backoff, handoff para
humano, log JSON por turno e avaliação por 15 casos.

**Por quê.** Demonstrar que os controles de segurança de uma aplicação com LLM
podem (e devem) ficar em código determinístico, com o modelo restrito a
interpretar linguagem e redigir a resposta.

**Como testar.** `make setup && make lint && make test && make eval`. Esperado:
164 testes passando e `Taxa de acerto: 15/15 (100%)`. Não precisa de chave.

**Onde revisar com atenção.**

- `src/agente_varejo/agente/nucleo.py` — ordem dos guardrails e o loop;
- `src/agente_varejo/guardrails/cpf.py` — a regex de CPF e seus limites;
- `config/guardrails.yaml` — padrões de injection e termos de escopo;
- `src/agente_varejo/llm/gemini.py` — nunca executado;
- `src/agente_varejo/api_simulada/transporte.py` — ponte síncrona sobre ASGI.

## e) Riscos, dívidas e o que falta antes de publicar

**Para o Brunno fazer:**

1. Testar o adaptador Gemini com a sua chave (lista em "Itens [verificar]") e
   rodar `python -m agente_varejo.avaliacao --llm gemini`. Colocar o resultado
   real no README.
2. Escolher a licença (nenhuma foi adicionada) e criar o arquivo `LICENSE`.
3. Criar o repositório público, definir a `main` e fazer o push. As branches
   estão empilhadas: dá para abrir um PR por épico ou um só a partir de
   `feat/e4-readme`.
4. Conferir o primeiro run do CI (nunca rodou) e considerar fixar as actions
   por SHA.
5. Revisar `git log` e o diff completo antes de publicar. `.claude/settings.json`
   e `CLAUDE.md` estão versionados; decidir se ficam no repositório público.
6. Reescrever as fichas de `docs/estudo.md` com as suas palavras.

**Riscos e dívidas técnicas:**

- O 15/15 vem do LLM falso: mede o pipeline, não o modelo.
- Detector de injection burlável por paráfrase e outros idiomas; falsos
  positivos conhecidos ("aja como…", "previsão do tempo").
- Só CPF é mascarado; o log guarda o texto livre do cliente.
- Falha do LLM real (rede, cota) não é tratada: estoura exceção em vez de
  virar handoff.
- A recusa por autorização revela que o pedido existe.
- Alguns commits intermediários do E2 não passam nos testes isoladamente (a
  ponta de cada branch passa).
- `make chat` não foi executado; o caminho HTTP real (uvicorn + agente) foi
  verificado uma vez à mão, sem teste automatizado.
- Sem registro de tokens/custo nem métricas agregadas.
- Numeração do OWASP conferida na página oficial (edição 2025); não foi
  possível descartar uma edição mais nova.
