# ADR-0004 — Política dos guardrails, do retry e do handoff

- Status: aceita
- Data: 2026-11-16

## Contexto

A ADR-0001 decidiu *onde* ficam os controles (em código). Esta registra *como*
cada um se comporta nos pontos em que havia mais de uma opção razoável.

## Decisões

1. **CPF é mascarado pelo formato, sem validar dígitos verificadores.**
   Qualquer sequência de 11 dígitos no formato de CPF (com ponto, hífen, espaço
   ou nada) vira `***.***.***-**`. Um CPF digitado errado ainda é quase o dado
   de alguém; exigir dígito válido criaria falso negativo justamente no dado
   sensível. Custo aceito: um telefone com DDD escrito sem separadores (11
   dígitos) também é mascarado — e telefone também é dado pessoal.
2. **O registrador de log mascara de novo na saída.** O agente já entrega
   texto mascarado, mas `RegistradorJSON` percorre todo o evento e mascara
   strings e inteiros. "Todo log sem CPF" vira propriedade do registrador, não
   disciplina de quem chama.
3. **Injection por padrões com peso e limiar.** Sinal forte (peso 1.0) bloqueia
   sozinho; sinal fraco (0.5), como "sou o gerente", só bloqueia combinado com
   outro. O texto é normalizado antes (caixa, acentos, caracteres invisíveis,
   letras de largura total). O detector é a primeira barreira, não a única.
4. **Texto barrado não entra no histórico.** Só turnos que passaram pelos
   guardrails de entrada são guardados na sessão; assim um ataque recusado não
   volta ao contexto do LLM no turno seguinte.
5. **Escopo em três classes.** Tema proibido (jurídico, reembolso, troca...)
   → handoff. Sinal de pedido/entrega ou número `PED-0000` → segue para o LLM.
   Nenhum sinal → o código pede o número do pedido, sem gastar chamada de LLM.
   Tema proibido tem precedência: "quero processar a loja pelo pedido X" vai
   para humano.
6. **Autorização na camada da tool.** A tool exposta ao LLM só tem `id_pedido`;
   o `cliente_id` vem da sessão. Se o pedido é de outro cliente, o resultado é
   descartado antes de chegar ao modelo e o turno termina em recusa.
   Argumentos extras gerados pelo modelo (ex.: `cliente_id`) são rejeitados.
7. **Desfechos decididos pelo código, não pelo LLM.** Pedido não encontrado
   (1ª vez: pedir confirmação; 2ª: handoff), API fora e pedido de outro cliente
   encerram o turno com mensagem fixa de `config/mensagens.yaml`. O LLM só
   redige quando há um status real para informar ou quando falta o número.
8. **Retry próprio em vez de `tenacity`.** 1 chamada + 2 novas tentativas, com
   espera `base * fator^n + jitter`. Só falha transitória é repetida (timeout,
   erro de rede, 5xx, 429); 404, outros 4xx e resposta fora do contrato não.
   São ~20 linhas, com `dormir` e `rng` injetáveis para testar sem esperar.
9. **Validação de saída com grounding.** Além do schema pydantic, o
   `status_pedido` do LLM precisa ser igual ao que a tool devolveu no turno.
   Status sem lastro conta como saída inválida (1 correção, depois handoff).
10. **O log guarda o texto do cliente (mascarado), truncado ao limite de
    entrada.** Facilita depurar e avaliar; em produção, com outros dados
    pessoais possíveis no texto livre, o padrão deveria ser não guardar.

## Alternativas consideradas

- Validar dígitos do CPF antes de mascarar (rejeitada: item 1).
- Classificador de escopo/injection por LLM (rejeitada na ADR-0001; fica como
  segunda camada futura).
- Devolver "pedido de outro cliente" ao LLM como erro e deixá-lo redigir a
  recusa (rejeitada: daria ao modelo um papel na decisão de autorização).
- `tenacity` (permitida, mas desnecessária para um caso só).

## Consequências

- Falsos positivos conhecidos: "previsão do tempo" passa pelo escopo por causa
  de "previsão"; "aja como um bom atendente" é recusado como injection. Ambos
  estão documentados nos testes ou no README.
- Falsos negativos são esperados em paráfrases e outros idiomas; o dano fica
  limitado porque autorização, escopo da tool e validação de saída não dependem
  do detector.
- A recusa por autorização tem texto diferente do "não encontrado", então
  revela que o número existe. Aceito aqui; em produção as duas respostas
  deveriam ser indistinguíveis.
