# Tennis Prediction Game
#
# `make` on its own lists the targets. The two you want most often:
#
#   make run        the whole app — backend on SQLite, frontend talking to it
#   make run-mock   frontend only, on in-memory fixtures, no backend needed
#
# Requires Node 20+ and uv (https://docs.astral.sh/uv/).

BACKEND_PORT  ?= 8000
FRONTEND_PORT ?= 5173
DATABASE_URL  ?= sqlite:///./tennis.db
IT_PROJECT    ?= tennis-it
IT_PORT       ?= 18000
DOCKER        ?= docker

.DEFAULT_GOAL := help
.PHONY: help install db reset-db run run-mock run-backend run-frontend \
        test test-unit test-frontend test-backend test-integration docker-check \
        lint typecheck check clean hooks docker-build

help: ## List the targets
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{ printf "  \033[1m%-17s\033[0m %s\n", $$1, $$2 }'
	@echo ""
	@echo "  Backend on :$(BACKEND_PORT), frontend on :$(FRONTEND_PORT)."
	@echo "  Sign in as you@example.com or organiser@example.com."
	@echo "  Password: deuce-demo-password (anything works in mock mode)."

install: ## Install both packages
	cd frontend && npm install
	cd backend && uv sync

db: ## Create the database and seed a demo game (no-op if already seeded)
	cd backend && uv run alembic upgrade head && uv run python scripts_seed.py

reset-db: ## Throw the database away and rebuild it from empty
	rm -f backend/tennis.db
	$(MAKE) db

run: db ## Run backend and frontend together
	@echo ""
	@echo "  frontend  http://localhost:$(FRONTEND_PORT)"
	@echo "  backend   http://localhost:$(BACKEND_PORT)  (docs at /docs)"
	@echo "  Ctrl-C stops both."
	@echo ""
	@trap 'kill 0' EXIT INT TERM; \
		( cd backend && REPOSITORY_BACKEND=sqlite DATABASE_URL=$(DATABASE_URL) EMAIL_PROVIDER=console \
			uv run uvicorn app.main:app --port $(BACKEND_PORT) --log-level warning ) & \
		( cd frontend && VITE_API_CLIENT=http \
			npm run dev -- --port $(FRONTEND_PORT) --strictPort ) & \
		wait

run-mock: ## Run the frontend alone on in-memory fixtures
	cd frontend && VITE_API_CLIENT=mock npm run dev -- --port $(FRONTEND_PORT) --strictPort

run-backend: db ## Run the backend alone
	cd backend && REPOSITORY_BACKEND=sqlite DATABASE_URL=$(DATABASE_URL) EMAIL_PROVIDER=console \
		uv run uvicorn app.main:app --port $(BACKEND_PORT) --reload

run-frontend: ## Run the frontend alone against an already-running backend
	cd frontend && VITE_API_CLIENT=http npm run dev -- --port $(FRONTEND_PORT) --strictPort

# The single command. The preflight runs first, so a machine without Docker
# learns it at once; the order of the two steps lives in the recipe, not in the
# prerequisites, so `make -j` cannot reorder it. The first failing step stops
# the run.
test: docker-check ## Run every test: Vitest, pytest, then the integration tests (needs Docker)
	$(MAKE) test-unit
	$(MAKE) test-integration

# Sequenced in the recipe for the same reason: Vitest, then pytest, even under -j.
test-unit: ## Vitest, then pytest (no Docker)
	$(MAKE) test-frontend
	$(MAKE) test-backend

test-frontend: ## Vitest only
	cd frontend && npm run test

test-backend: ## pytest only, against both repository implementations
	cd backend && uv run pytest

docker-check:
	@if $(DOCKER) info >/dev/null 2>&1 && $(DOCKER) compose version >/dev/null 2>&1; then \
		:; \
	else \
		echo "Docker with the compose plugin is required for the integration tests." >&2; \
		echo "'$(DOCKER) info' or '$(DOCKER) compose version' failed: start Docker, or install the compose plugin." >&2; \
		echo "To run the tests that need no Docker, use: make test-unit" >&2; \
		exit 1; \
	fi

test-integration: docker-check ## Build the compose stack on its own project, test it over HTTP, tear it down (needs Docker)
	@set -u; \
	trap '$(DOCKER) compose -p $(IT_PROJECT) down -v --remove-orphans' EXIT; \
	trap 'exit 130' INT TERM; \
	$(DOCKER) compose -p $(IT_PROJECT) down -v --remove-orphans || exit 1; \
	APP_PORT=$(IT_PORT) $(DOCKER) compose -p $(IT_PROJECT) up -d --build || exit 1; \
	APP_URL=http://localhost:$(IT_PORT) \
		uv run --project backend pytest -c tests/integration/pytest.ini tests/integration; \
	rc=$$?; \
	if [ $$rc -ne 0 ]; then $(DOCKER) compose -p $(IT_PROJECT) logs app; fi; \
	exit $$rc

# The optional local telemetry stack (#56): the app and Postgres plus the
# Collector, Prometheus, Loki, Tempo and Grafana, on 127.0.0.1 only. Nothing
# else in this Makefile starts it. APP_PORT (default 8000) is read by Compose.
TELEMETRY_COMPOSE = $(DOCKER) compose -f docker-compose.yml -f docker-compose.telemetry.yml
TELEMETRY_VOLUMES = prometheus-data tempo-data loki-data grafana-data

.PHONY: telemetry-up telemetry-down telemetry-reset telemetry-demo

telemetry-up: docker-check ## Start the app, Postgres and the telemetry stack; return when healthy (Grafana on :3000)
	$(TELEMETRY_COMPOSE) up -d --build --wait --wait-timeout 240
	@echo "waiting for Grafana, Prometheus, Loki and Tempo to answer ..."
	@for url in http://127.0.0.1:3000/api/health http://127.0.0.1:9090/-/ready \
		http://127.0.0.1:3100/ready http://127.0.0.1:3200/ready; do \
		n=0; until curl -fsS -o /dev/null "$$url" 2>/dev/null; do \
			n=$$((n+1)); \
			if [ $$n -ge 90 ]; then echo "not ready after 90 s: $$url" >&2; exit 1; fi; \
			sleep 1; \
		done; \
	done
	@echo ""
	@echo "  Grafana  http://localhost:3000  (user admin; password: GRAFANA_ADMIN_PASSWORD, development default in docker-compose.telemetry.yml)"
	@echo "  Dashboard 'Place a prediction'; run 'make telemetry-demo' to fill it."

telemetry-down: docker-check ## Stop the stack, keeping the telemetry data
	$(TELEMETRY_COMPOSE) down --remove-orphans

telemetry-reset: docker-check ## Stop the stack and delete the telemetry volumes (not the database)
	$(TELEMETRY_COMPOSE) down --remove-orphans
	@project="$$($(TELEMETRY_COMPOSE) config --format json | python3 -c 'import json, sys; print(json.load(sys.stdin)["name"])')"; \
	for volume in $(TELEMETRY_VOLUMES); do \
		ids="$$($(DOCKER) volume ls -q \
			--filter "label=com.docker.compose.project=$$project" \
			--filter "label=com.docker.compose.volume=$$volume")"; \
		if [ -n "$$ids" ]; then $(DOCKER) volume rm $$ids || exit 1; fi; \
	done

# The alert demo (#57): Normal -> Firing -> Normal, with a stand-in receiver on the
# port of RESPONDER_URL. Start the stack with the same RESPONDER_URL.
.PHONY: telemetry-alert-demo

telemetry-alert-demo: ## Prove the 5xx alert: 4xx stay quiet, one 5xx fires, it resolves (stack up with the same RESPONDER_URL)
	DOCKER=$(DOCKER) telemetry/alert-demo.py

telemetry-demo: ## Drive the six-step journey against the running stack (REPEAT=n to repeat)
	telemetry/demo-journey.sh

lint: ## ESLint and ruff
	cd frontend && npm run lint
	cd backend && uv run ruff check .

typecheck: ## tsc --noEmit
	cd frontend && npm run typecheck

check: lint typecheck test-unit ## Lint, typecheck, unit tests and the commit-gate tests (no Docker)
	agent-hooks/test-hooks.sh

docker-build: ## Build the container image (backend serving the built frontend)
	docker build -t tennis-prediction-game .

hooks: ## Enable the commit gate (git pre-commit hook) for this clone
	git config core.hooksPath agent-hooks
	@echo "  commit gate enabled: agent-hooks/commit-gate.sh runs before every commit"

clean: ## Remove build output and the database
	rm -rf frontend/dist frontend/node_modules/.vite
	rm -f backend/tennis.db
