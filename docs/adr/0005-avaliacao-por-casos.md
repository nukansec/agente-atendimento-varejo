# ADR-0005 — Avaliação por casos com checagens determinísticas

- Status: aceita
- Data: 2026-11-16

## Contexto

"O agente parece bom" não é evidência. É preciso um conjunto versionado de
entradas com resultado esperado, que rode a cada mudança de prompt, de
guardrail ou de modelo e que funcione como gate (falha = exit code diferente
de zero).

## Decisão

- Os casos ficam em `tests/casos/casos_v1.yaml`, validados por schema pydantic.
  Um caso é uma conversa de um ou mais turnos; avalia-se o **último turno**.
- As checagens são determinísticas e sobre o **comportamento**, não sobre o
  texto: desfecho, tool chamada (ou nenhuma), status informado, motivo,
  número de tentativas na API e CPF mascarado. Em todo caso o runner também
  verifica que nenhum CPF aparece no que foi enviado ao LLM, na resposta e no
  log.
- Cada caso roda isolado: sessão, LLM, API em memória e log novos.
- A meta (100%) fica no próprio arquivo de casos; `make eval` sai com código 1
  abaixo dela. Um teste adultera um caso para provar que o gate falha.
- O runner aceita `--llm gemini` para rodar os mesmos casos no modelo real.

## Alternativas consideradas

- **Comparar o texto da resposta** (igualdade ou similaridade): frágil, pois o
  texto muda a cada modelo sem que o comportamento mude.
- **LLM-as-judge**: útil para avaliar tom e clareza, mas custa, não é
  determinístico e não roda offline. Fica para uma camada posterior.
- **Só os testes unitários**: cobrem as peças, não o comportamento combinado
  descrito na linguagem do negócio.

## Consequências

- Com o `FakeLLM`, 15/15 significa "o código em volta do modelo faz o que
  deveria quando o modelo se comporta"; **não** mede a qualidade do modelo.
  O valor aqui é de teste de regressão do pipeline.
- 15 casos são poucos: servem como fumaça, não como estimativa estatística.
- Na avaliação as esperas de backoff são puladas e o timeout é reduzido
  (0,1 s) para o conjunto rodar em segundos.
