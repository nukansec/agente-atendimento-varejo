# ADR-0003 — API simulada chamada em memória nos testes e na avaliação

- Status: aceita
- Data: 2026-11-16

## Contexto

Os testes precisam exercitar a API FastAPI de verdade (rotas, status codes,
timeout), mas subir um servidor numa porta a cada execução é lento e frágil
(porta ocupada, firewall, corrida na inicialização). O `TestClient` do
Starlette resolveria, porém ignora o timeout do cliente e, na versão usada,
avisa que o uso com `httpx` está obsoleto em favor de outra biblioteca que não
está na lista permitida.

## Decisão

Um transporte próprio do httpx (`api_simulada/transporte.py`, ~30 linhas) faz
a ponte síncrona para o `httpx.ASGITransport` e aplica o timeout de leitura do
cliente. O agente recebe um `httpx.Client` por injeção: em produção ele aponta
para uma URL; em teste/eval, para o app em memória. O código do agente é o
mesmo nos dois casos.

## Alternativas consideradas

- **Servidor uvicorn em thread numa porta livre**: caminho HTTP completo, mas
  mais lento e com mais pontos de falha no CI.
- **`httpx.MockTransport` com respostas fixas**: não exercita a API.

## Consequências

- Sem socket: os testes rodam offline e em milissegundos.
- O timeout é real (`httpx.ReadTimeout`), então o cenário de API lenta é
  testado de ponta a ponta.
- O caminho de rede de verdade (`make api` + `make chat`) não é coberto por
  teste automatizado; foi verificado manualmente.
