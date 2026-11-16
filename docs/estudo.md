# Guia de estudo — como defender este projeto

Para cada uma das 15 fichas de conceitos: **onde** ela aparece no código
(`arquivo:linha`), a **decisão** tomada e a **troca** (trade-off) envolvida.
No fim, três perguntas que um avaliador provavelmente faria, com o esboço da
resposta.

Os caminhos são relativos a `src/agente_varejo/`, salvo quando indicado. Os
números de linha valem para o commit em que este guia foi escrito; se o código
mudar, procure pelo nome da função.

Três fichas (RAG, filas, webhooks) **não estão implementadas** — estão fora do
escopo. Para elas o guia diz onde entrariam e por que ficaram de fora; não
finja na entrevista que o projeto as tem.

---

## 1. LLM (tokens, contexto, temperatura, custo)

- **Onde:** `config/agente.yaml:5-6` (modelo e temperatura); `llm/base.py:57`
  (interface `LLMClient`); `agente/nucleo.py:133` (o contexto enviado é
  histórico + mensagem atual); `agente/nucleo.py:135` (teto de idas ao modelo).
- **Decisão:** temperatura 0 — atendimento factual quer a menor variação
  possível. O histórico guarda só a fala do cliente e a resposta final, não as
  mensagens internas de tool, para o contexto não crescer à toa. Cada turno
  custa no máximo 4 chamadas (`max_passos`).
- **Troca:** modelo pequeno e contexto curto são baratos e rápidos, mas
  entendem pior mensagens ambíguas. Aqui a tarefa é estreita (extrair um número
  de pedido e redigir uma frase), então o modelo menor basta. O projeto ainda
  não registra tokens nem custo por turno — é uma lacuna assumida.

## 2. System prompt

- **Onde:** `prompts/system_v1.md` (raiz do repo), regras nas linhas 6-18 e
  formato de saída a partir da 21; carregado em `agente/nucleo.py:268`
  (`construir_agente`), nunca escrito como string no código.
- **Decisão:** o prompt define papel, escopo, formato JSON e repete as regras
  de segurança — mas como reforço. Nenhuma garantia depende dele: ele não
  contém segredo e não decide autorização. Fica em arquivo versionado (`v1`)
  para que mudança de prompt seja um diff revisável e reavaliável.
- **Troca:** prompt detalhado orienta melhor, mas custa tokens em toda chamada
  e aumenta a chance de instruções conflitantes. Mantive seis regras curtas.
  Frase para a entrevista: *system prompt é configuração de comportamento, não
  barreira de segurança.*

## 3. Alucinação e mitigação

- **Onde:** `agente/modelos.py:90` (grounding: o status do modelo tem de ser
  igual ao da tool); `agente/modelos.py:73` (`validar_saida`);
  `agente/nucleo.py:169` (baixa confiança → handoff); `prompts/system_v1.md:6`.
- **Decisão:** quatro camadas. (1) O dado vem da tool, não da "memória" do
  modelo. (2) O prompt permite pedir o número em vez de chutar. (3) O código
  confere o status contra o resultado da tool do turno; status sem lastro é
  saída inválida. (4) Temperatura 0.
- **Troca:** quanto mais restrição, mais turnos terminam em "não sei" ou em
  handoff — menos erro, mais custo humano. O grounding só cobre o campo
  `status_pedido`; o texto livre da resposta ainda poderia conter uma data
  inventada. Os testes `test_status_inventado_sem_tool_nao_chega_ao_cliente` e
  `test_status_diferente_do_da_tool_e_rejeitado` (`tests/test_agente.py`)
  provam o comportamento.

## 4. RAG e embeddings — *não implementado*

- **Onde entraria:** como uma segunda tool (`consultar_politica`) ao lado de
  `agente/ferramentas.py`, alimentando o mesmo loop de `agente/nucleo.py:131`.
  Hoje, perguntas de política (troca, reembolso) caem em
  `config/guardrails.yaml:50` (`temas_fora`) e vão para humano.
- **Decisão:** deixar de fora. Status de pedido é dado estruturado e exato,
  obtido por id — busca por similaridade não ajuda. RAG serve para texto longo
  e não estruturado (políticas, FAQ).
- **Troca:** RAG é fácil de atualizar e permite citar a fonte, contra o
  fine-tuning, que "grava" o conhecimento no modelo e exige retreino. No RAG, o
  tamanho do chunk troca precisão por contexto. E trecho recuperado é dado não
  confiável: abre a porta para injection indireta (ficha 15).

## 5. Agente com tools / function calling

- **Onde:** `agente/nucleo.py:131-175` (o loop); `agente/nucleo.py:177`
  (`_executar_tool`); `prompts/tools_v1.yaml` (definição enviada ao modelo);
  `agente/ferramentas.py:25` e `:59` (validação dos argumentos);
  `llm/base.py:49` (`RespostaLLM`: texto **ou** chamadas).
- **Decisão:** loop escrito à mão, sem framework. O modelo devolve nome da
  função + argumentos em JSON; o código valida, executa e devolve o resultado;
  repete até vir texto final ou estourar o teto de passos. Uma única tool, só
  de leitura, com um único parâmetro (`id_pedido`).
- **Troca:** mais autonomia (mais tools, mais passos) resolve mais casos, mas
  aumenta a superfície de erro e de ataque. Aqui vale *least privilege*: a tool
  não aceita `cliente_id`, então o modelo nem tem como pedir o pedido "em nome"
  de outra pessoa (`test_llm_nao_consegue_escolher_o_cliente`).

## 6. Guardrails

- **Onde:** `agente/nucleo.py:89` (CPF), `:114` (injection), `:120` (escopo),
  `:189` (autorização), `:231` (`_fim`: máscara também na saída);
  implementações em `guardrails/cpf.py:15`, `guardrails/injection.py:50`,
  `guardrails/escopo.py:33`, `guardrails/autorizacao.py:8`; política em
  `config/guardrails.yaml`.
- **Decisão:** checagens **antes** do LLM (CPF, tamanho, injection, escopo) e
  **depois** (schema, grounding, CPF na resposta), todas em código. Motor em
  Python, política em YAML.
- **Troca:** falso positivo × falso negativo. Para CPF escolhi errar para o
  lado de mascarar demais (mascara pelo formato, sem validar dígitos). Para
  injection, pesos: sinal forte bloqueia sozinho, sinal fraco precisa de dois —
  reduz o falso positivo de "sou o gerente". Ver ADR-0001 e ADR-0004.

## 7. Human-in-the-loop

- **Onde:** `agente/nucleo.py:212` (`_encerrar_pela_tool`: API fora e pedido
  não encontrado pela 2ª vez), `:122-124` (fora do escopo), `:167-170` (modelo
  pediu humano ou confiança baixa), `:156` (saída inválida duas vezes), `:175`
  (limite de passos); `agente/nucleo.py:44` (`LIMITE_NAO_ENCONTRADOS`);
  `config/agente.yaml:20` (limiar de confiança).
- **Decisão:** critério de handoff **explícito e em código**, com um `motivo`
  registrado para cada um. O handoff aqui é uma mensagem fixa e um desfecho no
  log; a fila de atendimento humano não existe.
- **Troca:** mandar para humano é seguro, mas caro e lento. O limiar 0.6 é um
  chute inicial: deveria ser calibrado com dados reais (quantos handoffs eram
  mesmo necessários). Observação honesta: a "confiança" é um número que o
  próprio modelo declara, e modelos são mal calibrados — por isso os handoffs
  importantes não dependem dela.

## 8. Avaliação de LLM

- **Onde:** `tests/casos/casos_v1.yaml` (15 casos); `avaliacao/runner.py:77`
  (`executar_caso`), `:135` (`avaliar`), `:148` (tabela); `avaliacao/casos.py`
  (schema); `avaliacao/__main__.py` (exit code); `tests/test_avaliacao.py`.
- **Decisão:** casos versionados com resultado esperado, checagens
  determinísticas sobre comportamento (desfecho, tool, status, motivo, CPF),
  meta no próprio arquivo e exit code ≠ 0 abaixo dela. Um teste adultera um
  caso para provar que o gate falha de verdade.
- **Troca:** conjunto pequeno roda em segundos a cada mudança, mas cobre
  pouco. LLM-as-judge avaliaria tom e clareza, com custo e sem determinismo;
  revisão humana é a mais confiável e a mais cara. **Ponto que vão cobrar:**
  15/15 com o `FakeLLM` testa o código em volta do modelo, não o modelo
  (ADR-0005).

## 9. APIs REST e webhooks

- **Onde:** `api_simulada/app.py:13` (`GET /pedidos/{id}`: 200, 404, 500, 504);
  `agente/ferramentas.py:96` (cliente: classifica a resposta pelo status code);
  `dominio.py` (contrato `Pedido`, validado dos dois lados).
- **Decisão:** REST com *pull* — o agente pergunta quando o cliente pergunta. A
  resposta da API é validada por schema antes de ser usada; fora do contrato
  conta como falha. **Webhook não está implementado.**
- **Troca:** polling é simples e sem estado, mas só sabe da mudança quando
  pergunta. Webhook (a loja faz POST quando o status muda) dá tempo real e
  permitiria avisar o cliente proativamente, mas exige endpoint público,
  validação de assinatura, idempotência e tratamento de reentrega.

## 10. LLM × regra fixa

- **Onde:** regra fixa — `guardrails/cpf.py:12` (regex), `dominio.py`
  (formato `PED-0000`), `guardrails/autorizacao.py:8`, `agente/nucleo.py:212`
  (desfechos), `config/mensagens.yaml` (textos de recusa e handoff). LLM —
  `agente/nucleo.py:137` (entender o pedido e redigir a resposta).
- **Decisão:** o que é determinístico e auditável fica em regra: detectar CPF,
  validar id, autorizar, contar tentativas, decidir handoff, e até o **texto**
  das recusas. O LLM fica com o que é linguagem: achar o número numa frase
  livre e escrever a resposta de status.
- **Troca:** regra é previsível, barata e testável, mas quebra com variação de
  linguagem; LLM é flexível, mas custa e varia. Autocrítica boa para a
  entrevista: neste escopo estreito, uma regex extrairia o número do pedido sem
  LLM nenhum (é o que o `FakeLLM` faz em `llm/fake.py:73`). O LLM se paga
  quando a linguagem fica ambígua ou o número de intenções cresce.

## 11. Filas / assíncrono — *não implementado*

- **Onde entraria:** entre o canal de chat e `Agente.responder`
  (`agente/nucleo.py:84`), e no handoff (`_fim`, `agente/nucleo.py:231`), que
  hoje só devolve uma mensagem.
- **Decisão:** processamento síncrono, um turno por vez, sem fila. É suficiente
  para uma demonstração local.
- **Troca:** fila absorve pico e isola falhas (o cliente recebe "estamos
  verificando"), em troca de latência, complexidade operacional e da
  necessidade de idempotência — a mesma mensagem pode ser entregue duas vezes.
  Como a única tool é de leitura, reprocessar aqui seria inofensivo; com uma
  tool que altera estado (cancelar pedido), não.

## 12. Observabilidade

- **Onde:** `agente/nucleo.py:249` (`_registrar`: um evento JSON por turno);
  `logs/estruturado.py:33` (`RegistradorJSON`), `:47` (conversão + máscara na
  saída); `agente/nucleo.py:200-209` (registro de cada tool call com tentativas
  e latência).
- **Decisão:** log estruturado por turno com sessão, guardrails acionados, tool
  calls, número de chamadas ao LLM, desfecho, motivo e latência. O registrador
  mascara CPF de novo, por conta própria. Desses eventos dá para derivar taxa
  de handoff, taxa de recusa e latência p95 — mas a agregação **não** está
  feita, nem há custo por conversa.
- **Troca:** logar mais ajuda a depurar e custa privacidade e armazenamento.
  Aqui o texto do cliente é guardado (só CPF mascarado), o que é confortável
  para depurar e questionável para LGPD (ADR-0004, item 10).

## 13. Falhas

- **Onde:** `agente/retry.py:15` (`PoliticaRetry`), `:29` (espera = base ×
  fator^n + jitter), `:32` (`executar_com_retry`), `:50` (teto de tentativas);
  `agente/ferramentas.py:96-117` (o que é transitório), `:110` (5xx e 429);
  `config/agente.yaml:10-14`; `api_simulada/transporte.py:35` (timeout real em
  teste); fallback em `agente/nucleo.py:221-222`.
- **Decisão:** timeout por chamada, 1 tentativa + 2 retries com backoff
  exponencial e jitter, só para falha transitória (timeout, rede, 5xx, 429).
  404 e outros 4xx não são repetidos. Esgotou: handoff.
- **Troca:** repetir aumenta a chance de sucesso, mas multiplica a carga sobre
  uma API que já está mal (*retry storm*). O teto baixo e o jitter existem por
  isso. Faltam: circuit breaker, respeito ao cabeçalho `Retry-After` do 429 e
  fallback para um modelo menor quando o LLM falha (falha do LLM hoje estoura
  exceção).

## 14. LGPD e mascaramento

- **Onde:** `agente/nucleo.py:89-92` (primeira coisa do turno);
  `guardrails/cpf.py:12` (padrão), `:15` (`mascarar_cpf`), `:29`
  (`mascarar_profundo`); `logs/estruturado.py:47-52`; `agente/nucleo.py:161`
  (saída rejeitada do modelo é mascarada antes de voltar a ele);
  `agente/ferramentas.py:45` (`para_llm` não envia `cliente_id`).
- **Decisão:** minimização — o agente não precisa do CPF para informar status,
  então o CPF é removido antes de sair do processo (não vai ao provedor, ao
  histórico nem ao log). A variável com o texto original é sobrescrita na
  linha da máscara. Dados do repositório são todos sintéticos.
- **Troca:** mascarar de forma irreversível é o mais seguro, mas perde o dado
  se um dia ele for necessário (ex.: identificar o cliente pelo CPF). A saída
  seria pseudonimização reversível só no backend: o LLM vê um token, e apenas o
  código troca o token pelo valor. Limite atual: só CPF é tratado.

## 15. Prompt injection

- **Onde:** `guardrails/injection.py:30` (`DetectorInjection`), `:50`
  (`analisar`); `guardrails/texto.py:11` (normalização: caixa, acentos,
  invisíveis); `config/guardrails.yaml:8` (limiar) e padrões abaixo;
  `agente/nucleo.py:99-103` (texto barrado não entra no histórico);
  `prompts/system_v1.md:13` (regra de "texto é dado"); e, principalmente,
  `agente/nucleo.py:189-197` (autorização que não depende do detector).
- **Decisão:** defesa em camadas. (1) Filtro de padrões antes do LLM. (2)
  Instrução no prompt separando instrução de dado. (3) *Least privilege*: uma
  tool, só leitura, um parâmetro. (4) Validação da saída. (5) **Autorização
  fora do LLM** — a camada que realmente segura. O caso J3 da avaliação é a
  demonstração: o ataque passa pelo filtro, o modelo "cai" e pede a tool, e
  mesmo assim nada é exibido.
- **Troca:** filtro por palavra-chave é barato e explicável, mas tem falso
  positivo ("aja como um bom atendente") e é fácil de burlar (paráfrase, outro
  idioma). Por isso ele é tratado como redução de ruído, não como controle.
  Injection **indireta** (instrução escondida em dado recuperado) não ocorre
  hoje porque a tool só devolve campos validados por schema — passaria a
  importar com RAG.

---

## Três perguntas que o avaliador faria

### 1. "Sua avaliação dá 100% com um LLM falso. O que isso prova?"

Esboço: prova menos do que parece, e é importante dizer isso primeiro. Com o
`FakeLLM`, o 15/15 é um teste de regressão do **código em volta do modelo**:
guardrails, autorização, retry, validação e handoff se comportam como
especificado quando o modelo colabora. Isso tem valor — é o que roda no CI sem
chave e pega regressão em segundos (pegou uma de verdade durante o
desenvolvimento: a saída inválida do modelo voltava para ele sem máscara de
CPF). O que **não** prova é a qualidade do modelo real. Para isso existem duas
coisas: os testes com *roteiro*, que simulam o modelo errando (JSON quebrado,
status inventado, tool indevida, argumento malicioso) e mostram que o código
aguenta; e o `--llm gemini`, que roda os mesmos casos no modelo de verdade —
número que ainda falta medir. Próximo passo seria ampliar o conjunto e
acompanhar a taxa por categoria a cada mudança de prompt.

### 2. "Seu detector de injection é uma lista de regex. Eu burlo em um minuto. E aí?"

Esboço: burla mesmo, e o projeto foi desenhado contando com isso. O detector é
a primeira camada, serve para barrar o ataque óbvio sem gastar chamada de LLM.
A pergunta certa é "o que acontece quando o ataque passa?". Resposta: o modelo
só tem uma tool, de leitura, com um parâmetro; os argumentos são validados; e a
autorização compara o dono do pedido com o `cliente_id` **da sessão**, em
código (`guardrails/autorizacao.py:8`). O atacante que dominar o modelo por
completo consegue, no máximo, consultar os próprios pedidos. Mostrar o caso J3
e o teste `test_pedido_de_outro_cliente_e_barrado_no_codigo`, que verifica que
o dado do outro cliente nem chega ao contexto do modelo. O que eu melhoraria:
um classificador como segunda camada e mais casos adversariais na avaliação.

### 3. "Por que não usou LangChain? E por que não deixar o LLM decidir o handoff?"

Esboço: são a mesma resposta — controle e auditabilidade. Sem framework, o
loop inteiro cabe em ~45 linhas (`agente/nucleo.py:131`) e eu sei explicar cada
passo: onde o modelo pede a tool, onde o código valida, onde há limite de
passos. Para uma tool só, o framework traria dependência e esconderia
justamente a parte que importa para segurança. Sobre o handoff: decisões com
consequência (transferir, recusar, autorizar) precisam ser previsíveis e
testáveis, então são regra em código com motivo registrado no log. O modelo
pode *sugerir* humano (`precisa_humano`, confiança baixa), mas API fora, pedido
não encontrado duas vezes e pedido de outro cliente não passam por ele. O custo
dessa escolha: menos flexibilidade — um caso novo exige código, não só mexer no
prompt. Num produto com muitas tools e fluxos, eu reavaliaria um framework,
mantendo autorização e guardrails fora dele.
