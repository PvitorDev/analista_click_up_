# Analista ClickUp — gestão de tarefas

Primeiro braço de um ecossistema maior de agentes por setor. Este repositório cobre **apenas** a leitura da gestão de tarefas via ClickUp.

## O que este agente é

Um **analista**, não um dashboard e não um robô de automação.

A pergunta que ele responde: *o que está realmente acontecendo na gestão de tarefas desta empresa, e o que dá para melhorar?*

Ele lê o que já existe no ClickUp (descrições, comentários, histórico, quem fez o quê e quando) e devolve o que um gestor sênior devolveria depois de uma semana investigando: onde o trabalho trava, como as pessoas realmente trabalham, e o que mudar em ordem de impacto.

**Nesta versão ele só lê e reporta.** Não comenta no ClickUp, não move card, não cobra ninguém.

## O que foi feito

| Bloco | Entrega |
| --- | --- |
| **A** | Espelho em Postgres (tarefas, subtasks, descrições, comentários, membros, listas, custom fields, anexos). **Histórico de status (A2) é a primeira coisa no ar** — cada transição com timestamp. Sync por polling + tentativa de backfill. Mapa canônico de status (A4). Prioridade e Contexto como colunas (A5). Responsável primário (A6). |
| **B** | Extração do que já está escrito: cronogramas em tabelas na descrição, dependências/handoffs, riscos e pendências, decisões em comentários, área/tipo por prefixo (`[UI/UX]`, `[Backend]`, `[infra]`, `[SPBK]`) e conteúdo. |
| **C** | Views SQL: tempo em status (mediana/p85), gargalo em dias acumulados, lead/cycle time, WIP, aging 7/14/30, retrabalho, cadeia de bloqueio, prometido vs. entregue, higiene do board. |
| **D** | Perfil individual, colaboração, carga — **privado**. Cada pessoa vê o próprio perfil; admin/owner do workspace ClickUp pode ver qualquer perfil. Sem ranking. |
| **E** | Relatório narrativo, cinco melhorias priorizadas, página única com drill-down até o card, regeneração sob demanda. |

Além de A–E, o repositório também inclui:

| | O que existe |
| --- | --- |
| **Sync** | Worker em polling (`SYNC_INTERVAL_SECONDS`). Sync manual (admin). Se o último sync do workspace tem menos de 10 minutos, gerar relatório não puxa o ClickUp de novo. |
| **Cache** | Cache HTTP do ClickUp no Redis; cache das respostas `/api/*` de métricas e relatórios. Volume Docker `hfcache` para o modelo de embeddings (não some no `make reset`). |
| **Chat (WebSocket)** | `WS /ws/chat` com cookie de sessão. A resposta chega em pedaços (`assistant_delta`) enquanto o modelo gera, não num POST único. Markdown no bubble (`##`, negrito, listas). |
| **RAG** | Índice no Redis Stack (vetores 384d, FastEmbed multilíngue). Recupera trechos dos relatórios para o chat. Se o modelo ainda está baixando, o chat responde sem RAG. |
| **Streaming do relatório** | `WS /ws/reports/generate`: o diagnóstico aparece no modal enquanto o Claude escreve. Fechar o modal não cancela; toast “gerando em segundo plano” reabre o painel. Grava no Postgres só no fim (JSON + prosa). |
| **Leaderboard** | `GET /api/leaderboard` e rota `/leaderboard` — só admin. Ranking operacional de fluxo (WIP/aging) e entrega (concluídos, lead/cycle, marcos), não avaliação de desempenho. Nome liga ao perfil. |

Stack: **Postgres**, **Redis Stack** (contexto do chat + RAG dos relatórios), **Python (FastAPI + worker de sync)**, **views SQL**, **Claude** (Agent SDK com fallback Anthropic; chat e relatório em stream), **Next.js**.

O backend é Python, não NestJS. A identidade vem do **OAuth do ClickUp**.

## Fora de escopo

Base de conhecimento da empresa · escrita de volta no ClickUp · webhooks · previsão estatística de entrega · outros setores · GitHub.

## Como subir

Pré-requisito: **Docker**. Tokens do ClickUp e Anthropic vão no `.env` (criado automaticamente na primeira vez).

```bash
make up
```

Isso, nesta ordem: cria `.env` se faltar → sobe o Postgres e o Redis Stack → aplica `schema.sql` e `views.sql` → sobe a API (8000), o worker de sync e o front (3000).

Em background: `make up-d`. Parar: `make down`. Zerar dados: `make reset`. Logs: `make logs`. Reaplicar SQL: `make sql`.

Abra [http://localhost:3000](http://localhost:3000). Sem sessão, a UI mostra `/login`; o OAuth ClickUp só começa ao clicar em **Entrar**.

| Alvo | O que faz |
| --- | --- |
| `make up` | Tudo no primeiro plano (Ctrl+C derruba) |
| `make up-d` | Tudo em background |
| `make sql` | Só Postgres + migrate (schema e views) |
| `make logs` | Segue os logs |
| `make down` | Para os containers (mantém os dados) |
| `make reset` | Apaga Postgres + Redis e sobe de novo. Depois: entrar, sincronizar ClickUp e gerar relatório. |
| `make teams` | Lista workspaces do token e os ids |

Sincronização manual (admin): botão **Sincronizar ClickUp** na página do relatório. Isso também roda a extração do Bloco B.

### Variáveis de ambiente

| Variável | Uso |
| --- | --- |
| `DATABASE_URL` | Postgres |
| `CLICKUP_API_TOKEN` | Token de **serviço** do worker (somente GET). Não é o OAuth do usuário. |
| `CLICKUP_TEAM_ID` | Workspace inicial (opcional). Se vazio, o app usa o **primeiro** workspace do token. Dá para trocar no menu do header. |
| `CLICKUP_FIELD_PRIORITY` / `CLICKUP_FIELD_CONTEXT` | Nomes dos custom fields (padrão: Prioridade, Contexto) |
| `SYNC_INTERVAL_SECONDS` | Polling do worker (padrão 300) |
| `CLICKUP_CLIENT_ID` / `CLICKUP_CLIENT_SECRET` | App OAuth. Em `ENV=development`, se estiverem vazios, o login usa o `CLICKUP_API_TOKEN` (GET /user + GET /team). Em produção o OAuth é obrigatório. |
| `CLICKUP_REDIRECT_URI` | Deve ser `http://localhost:8000/auth/callback` em local (callback no FastAPI; o front chama a API em `localhost:8000` com cookie) |
| `SESSION_TTL_HOURS` | Validade da sessão |
| `ANTHROPIC_API_KEY` | Blocos D e E, chat do analista, stream do relatório e refinamento B via agente |
| `ANTHROPIC_MODEL` | Modelo Claude (padrão `claude-sonnet-4-6`; o Sonnet 4 de 20250514 foi aposentado) |
| `REDIS_URL` | Redis Stack (contexto do chat + RAG dos relatórios). No Compose: `redis://redis:6379` |
| `DEV_BYPASS_AUTH` | Só em `ENV=development`. Se `ENV=production` e isto estiver ligado, **o processo recusa subir**. |

### Como obter o `CLICKUP_TEAM_ID`

No ClickUp, workspace = team. O valor é `teams[].id` de **Get Authorized Workspaces**.

O sync usa o **token de serviço** (`CLICKUP_API_TOKEN`), não o OAuth do login.

```bash
make teams
```

Ou:

```bash
curl -s https://api.clickup.com/api/v2/team \
  -H "Authorization: $CLICKUP_API_TOKEN"
# copie teams[0].id → CLICKUP_TEAM_ID
```

Na UI: a URL é `https://app.clickup.com/{team_id}/...`.

Se o `.env` estiver vazio e o token tiver **um** workspace, o worker usa esse id sozinho. Se tiver **dois ou mais**, o sync para e lista `nome → id` para você copiar.

## Registrar o app OAuth no ClickUp

Em desenvolvimento você **não precisa** disto se `CLICKUP_API_TOKEN` já estiver no `.env`: `/auth/login` identifica o dono do token via `GET /user` e `GET /team`.

Para vários usuários (produção), registre o app:

1. No ClickUp: avatar → Settings → Apps / OAuth apps → Create new app (owner ou admin do workspace).
2. Redirect URL: o mesmo valor de `CLICKUP_REDIRECT_URI` (local: `http://localhost:8000/auth/callback`).
3. Copie `client_id` e `secret` para o `.env`.
4. Authorization URL usada pelo sistema: `https://app.clickup.com/api?client_id=...&redirect_uri=...`.
5. Troca do `code` em `POST https://api.clickup.com/api/v2/oauth/token`.

Papel (`admin` vs `member`) vem de `GET /api/v2/team` (membros do workspace). ClickUp: `1` owner, `2` admin → **admin**; `3` member, `4` guest → **member**.

**Se o token do usuário comum não trouxer `role`, o sistema assume `member`. Nunca assume admin por ausência de dado.**

Sessão: cookie **httpOnly**, **SameSite=lax**, **Secure** em produção. O `access_token` do ClickUp fica só na tabela `sessions` no Postgres, chave = id opaco no cookie. Logout apaga a linha.

Token ClickUp inválido/expirado: a sessão deixa de ser aceita (401) e o usuário entra de novo — o papel é revalidado no login, não fica cacheado além do TTL.

### Autorização do Bloco D

Rotas `/api/perfil/{pessoaId}` passam por um guard único:

1. Sem sessão → 401  
2. Pessoa inexistente nos dados sincronizados → **404**  
3. `clickup_user_id` da sessão = `pessoaId` → ok  
4. `role = admin` → ok  
5. senão → **403** genérico  

Métricas do Bloco C (gargalo, WIP, aging, higiene) são públicas para qualquer sessão válida. A UI **não oferece** links de perfil de terceiros para quem não é admin; a proteção real é o backend.

Quando um admin abre o perfil de outra pessoa, a tela mostra um banner explícito.

Validação manual esperada (sem suíte automatizada neste MVP):

- Usuário comum, próprio perfil → libera  
- Usuário comum, perfil de terceiro (API direta) → 403  
- Admin, perfil de terceiro → libera  
- Sessão expirada → 401  

## Histórico de status e Time in Status

O ClickApp **Total Time in Status** muitas vezes não está disponível (plano / ClickApp desligado). O worker **tenta** `GET /task/{id}/time_in_status` uma vez; se a API recusar, desliga essa fonte e passa a gravar transições por **diff entre polls**.

Histórico que não foi capturado **não volta**. Por isso o worker (A2) deve subir antes de qualquer análise de tempo em status.

Mapa canônico (A4): `doing`/`fazendo` → `EM_ANDAMENTO` · `review` → `EM_REVISAO` · `a fazer`/`Open` → `A_FAZER` · `feito`/`Closed`/`encerrado` → `CONCLUIDO` · `blocked` → `BLOQUEADO` · resto → `OUTRO`.

Responsável primário (A6): quem mais aparece como ator de transição de status > quem mais comenta > primeiro assignee.

## Critério de sucesso

O relatório (E1) responde, com evidência rastreável até o card:

1. Onde o trabalho está parando, e quanto isso custa?  
2. Como cada pessoa está realmente trabalhando? (no perfil 1:1, não em ranking coletivo)  
3. Quais são as 5 mudanças de maior impacto agora?  

Se um gestor experiente disser “isso eu não sabia” pelo menos duas vezes, o MVP cumpriu o papel.

## Ponto sensível — Bloco D

Cada pessoa vê o próprio perfil. Sistema secreto de avaliação destrói confiança quando vaza — e vaza.

Métricas de **processo** podem ser abertas. Métricas de **pessoa** ficam entre gestor e pessoa, em 1:1 — nunca como ranking, nunca em comunicação coletiva.

O maior risco é comportamental: se a equipe sentir que está sendo medida pelo ClickUp, ela otimiza a métrica (fatia card, para de escrever comentário difícil, fecha cedo) e some exatamente o texto rico que torna a análise possível.

**Comunique o projeto à equipe antes de ligar o Bloco D.**

## Pré-requisitos de gestão (não são código)

Podem sair via ClickUp Automations:

- Padronizar status entre Development / Design / E2 — ou aceitar o mapa A4 como permanente  
- Tornar Prioridade e Contexto obrigatórios em card novo  
- Definir 1 responsável primário por card  
- Proibir card genérico (“Março”, “Maio”)  
- Comunicar o projeto antes de ligar o Bloco D  

## Estrutura

```
server/          FastAPI, worker, SQL, agente
  app/worker.py  polling contínuo
  sql/schema.sql espelho + sessões + extrações
  sql/views.sql  métricas C
client/          Next.js — dashboard, relatórios, perfil, leaderboard, chat
```
