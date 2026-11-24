# ADR-0002 — LLM atrás de uma interface, com FakeLLM determinístico

- Status: aceita
- Data: 2026-11-16

## Contexto

O critério de sucesso do projeto é `make test` e `make eval` rodarem num clone
limpo, sem chave de API e sem internet. Ao mesmo tempo, o agente precisa
funcionar com um modelo real. Chamar um LLM de verdade nos testes os tornaria
lentos, pagos, não determinísticos e dependentes de segredo no CI.

## Decisão

- O loop do agente depende só do protocolo `LLMClient` (`llm/base.py`):
  `gerar(sistema, mensagens, tools) -> RespostaLLM`, em que a resposta é
  **texto final ou chamadas de tool**.
- `FakeLLM` implementa o protocolo sem rede. Tem dois modos: *roteiro*
  (respostas pré-definidas, para simular um modelo que erra) e *regras*
  (um modelo bem-comportado: pede a tool quando há número de pedido e responde
  a partir do resultado).
- `GeminiLLM` é o adaptador real, com o SDK como dependência **opcional**
  (`.[gemini]`) e import tardio.
- O loop de tool calling é escrito à mão, sem framework de agente.

## Alternativas consideradas

- **Mock com `unittest.mock` em cada teste**: espalha o conhecimento do
  formato do provedor pelos testes e não serve para o `make eval`.
- **Gravar e reproduzir respostas reais (cassetes)**: mais fiel, mas exige
  chave para regravar e os arquivos envelhecem a cada mudança de prompt.
- **Framework de agente**: esconde o loop que o projeto quer demonstrar.

## Consequências

- Testes e avaliação são rápidos, gratuitos e reprodutíveis.
- **Limite importante:** com o `FakeLLM`, a avaliação mede o *código em volta
  do modelo* (guardrails, tool, validação, handoff), não a qualidade do modelo.
  O roteiro cobre os modos de falha do modelo que conhecemos; os que não
  conhecemos só aparecem rodando os mesmos casos contra o adaptador real.
- O adaptador real precisa ser validado manualmente com uma chave.
