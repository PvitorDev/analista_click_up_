.PHONY: env up down reset restart logs sql psql api worker client status teams

COMPOSE := docker compose

env:
	@test -f .env || (cp .env.example .env && echo "Criado .env a partir de .env.example — edite tokens antes do sync.")
	@test -f client/.env.local || (cp client/.env.local.example client/.env.local && echo "Criado client/.env.local")

# Sobe Postgres, aplica SQL, API, worker e front.
up: env
	$(COMPOSE) up --build

# Mesmo que up, em background.
up-d: env
	$(COMPOSE) up --build -d
	@echo "API  http://localhost:8000"
	@echo "Front http://localhost:3000"

down:
	$(COMPOSE) down

# Apaga Postgres e Redis (dados do app). Preserva client_node_modules e o cache FastEmbed.
reset: env
	@echo "Reset: apaga relatórios, sync, sessões, chat e o índice Redis deste projeto."
	$(COMPOSE) down
	@proj=$$(basename "$(CURDIR)" | tr '[:upper:]' '[:lower:]' | tr -d ' -'); \
	echo "Removendo $${proj}_pgdata $${proj}_redisdata"; \
	docker volume rm $${proj}_pgdata $${proj}_redisdata 2>/dev/null || true
	$(MAKE) up

restart: down up-d

logs:
	$(COMPOSE) logs -f

status:
	$(COMPOSE) ps

# Reaplica schema.sql e views.sql no Postgres já no ar.
sql: env
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm migrate

psql:
	$(COMPOSE) exec postgres psql -U clickup -d clickup_analyst

api:
	$(COMPOSE) up --build api

worker:
	$(COMPOSE) up --build worker

client:
	$(COMPOSE) up --build client

# Lista workspaces do token de serviço (GET /v2/team) e os ids para CLICKUP_TEAM_ID.
teams: env
	$(COMPOSE) run --rm --no-deps --entrypoint python api -m app.teams
