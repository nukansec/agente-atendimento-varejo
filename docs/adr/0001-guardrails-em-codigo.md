# ADR-0001 — Guardrails em código, não só no prompt

- Status: aceita
- Data: 2026-11-16

## Contexto

O agente recebe texto livre de um usuário não confiável e tem acesso a uma
tool que lê dados de pedidos. Um LLM não distingue, de forma garantida,
"instrução" de "dado": qualquer regra escrita no system prompt pode ser
contornada por prompt injection, e o comportamento do modelo é probabilístico
(muda com modelo, versão e temperatura).

## Decisão

Todo controle de segurança é implementado em **código determinístico**, fora
do LLM:

1. mascaramento de CPF antes de o texto chegar ao LLM, ao histórico ou ao log;
2. detecção de prompt injection (padrões + pontuação) antes do LLM;
3. checagem de escopo antes do LLM;
4. **autorização** na camada da tool: o `cliente_id` vem da sessão, nunca de
   argumento gerado pelo modelo;
5. validação da saída do LLM (schema pydantic + conferência com o resultado da
   tool) antes de responder.

O system prompt repete as regras, mas apenas como **defesa em profundidade**:
nenhuma garantia de segurança depende dele.

## Alternativas consideradas

- **Só o system prompt** ("nunca revele dados de outro cliente"): simples, mas
  contornável e não testável de forma determinística.
- **Um segundo LLM como classificador/juiz**: cobre mais variações de ataque,
  porém custa tokens e latência, também é atacável por injection e não roda
  offline nos testes. Fica como evolução possível, *atrás* dos filtros em
  código.
- **Biblioteca de guardrails pronta**: esconderia a lógica que o projeto quer
  demonstrar e adicionaria dependência.

## Consequências

- Os guardrails são testáveis com testes unitários comuns e rodam igual com
  qualquer modelo — inclusive quando o modelo erra.
- Filtros por padrão têm falso positivo (recusar mensagem legítima) e falso
  negativo (paráfrase que escapa). Por isso o detector de injection **não** é
  a barreira de autorização: mesmo que um ataque passe por ele, a tool só
  devolve pedidos do cliente da sessão.
- Padrões e termos ficam em `config/guardrails.yaml`, ajustáveis sem mexer no
  motor; cada ajuste deve vir acompanhado de um caso em `tests/`.
