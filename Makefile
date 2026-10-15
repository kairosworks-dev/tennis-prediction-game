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

.DEFAULT_GOAL := help
.PHONY: help install db reset-db run run-mock run-backend run-frontend \
        test test-frontend test-backend test-integration lint typecheck check clean hooks \
        docker-build

help: ## List the targets
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{ printf "  \033[1m%-14s\033[0m %s\n", $$1, $$2 }'
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
		( cd backend && REPOSITORY_BACKEND=sqlite DATABASE_URL=$(DATABASE_URL) \
			uv run uvicorn app.main:app --port $(BACKEND_PORT) --log-level warning ) & \
		( cd frontend && VITE_API_CLIENT=http \
			npm run dev -- --port $(FRONTEND_PORT) --strictPort ) & \
		wait

run-mock: ## Run the frontend alone on in-memory fixtures
	cd frontend && VITE_API_CLIENT=mock npm run dev -- --port $(FRONTEND_PORT) --strictPort

run-backend: db ## Run the backend alone
	cd backend && REPOSITORY_BACKEND=sqlite DATABASE_URL=$(DATABASE_URL) \
		uv run uvicorn app.main:app --port $(BACKEND_PORT) --reload

run-frontend: ## Run the frontend alone against an already-running backend
	cd frontend && VITE_API_CLIENT=http npm run dev -- --port $(FRONTEND_PORT) --strictPort

test: test-frontend test-backend ## Run every test

test-frontend: ## Vitest
	cd frontend && npm run test

test-backend: ## pytest, against both repository implementations
	cd backend && uv run pytest

test-integration: ## Build the compose stack on its own project, test it over HTTP, tear it down
	@set -u; \
	trap 'docker compose -p $(IT_PROJECT) down -v --remove-orphans' EXIT; \
	trap 'exit 130' INT TERM; \
	docker compose -p $(IT_PROJECT) down -v --remove-orphans || exit 1; \
	APP_PORT=$(IT_PORT) docker compose -p $(IT_PROJECT) up -d --build || exit 1; \
	APP_URL=http://localhost:$(IT_PORT) \
		uv run --project backend pytest -c tests/integration/pytest.ini tests/integration; \
	rc=$$?; \
	if [ $$rc -ne 0 ]; then docker compose -p $(IT_PROJECT) logs app; fi; \
	exit $$rc

lint: ## ESLint and ruff
	cd frontend && npm run lint
	cd backend && uv run ruff check .

typecheck: ## tsc --noEmit
	cd frontend && npm run typecheck

check: lint typecheck test ## Everything CI would run, plus the commit-gate tests
	agent-hooks/test-hooks.sh

docker-build: ## Build the container image (backend serving the built frontend)
	docker build -t tennis-prediction-game .

hooks: ## Enable the commit gate (git pre-commit hook) for this clone
	git config core.hooksPath agent-hooks
	@echo "  commit gate enabled: agent-hooks/commit-gate.sh runs before every commit"

clean: ## Remove build output and the database
	rm -rf frontend/dist frontend/node_modules/.vite
	rm -f backend/tennis.db
