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

.DEFAULT_GOAL := help
.PHONY: help install db reset-db run run-mock run-backend run-frontend \
        test test-frontend test-backend lint typecheck check clean

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

lint: ## ESLint and ruff
	cd frontend && npm run lint
	cd backend && uv run ruff check .

typecheck: ## tsc --noEmit
	cd frontend && npm run typecheck

check: lint typecheck test ## Everything CI would run

clean: ## Remove build output and the database
	rm -rf frontend/dist frontend/node_modules/.vite
	rm -f backend/tennis.db
