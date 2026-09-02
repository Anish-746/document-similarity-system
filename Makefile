.PHONY: services-up services-down services-logs migrate migrate-down dev benchmark

PODMAN ?= podman

services-up:
	@echo "Starting PostgreSQL..."
	$(PODMAN) run -d \
		--name docsim_postgres \
		--replace \
		-e POSTGRES_USER=docsim \
		-e POSTGRES_PASSWORD=docsim_secret \
		-e POSTGRES_DB=docsim \
		-p 5432:5432 \
		-v docsim_postgres_data:/var/lib/postgresql/data \
		docker.io/postgres:16-alpine
	@echo "Starting Redis..."
	$(PODMAN) run -d \
		--name docsim_redis \
		--replace \
		-p 6379:6379 \
		docker.io/redis:7-alpine \
		redis-server --save "" --appendonly no
	@echo ""
	@echo "Waiting for Postgres to be ready..."
	@sleep 3
	@$(PODMAN) exec docsim_postgres pg_isready -U docsim -d docsim \
		&& echo "Postgres is ready." || echo "Postgres not ready yet — wait a moment and retry."
	@echo "Services started. Run 'make init-db' to apply migrations."

services-down:
	$(PODMAN) stop docsim_postgres docsim_redis 2>/dev/null || true
	$(PODMAN) rm docsim_postgres docsim_redis 2>/dev/null || true
	@echo "Services stopped."

services-logs:
	$(PODMAN) logs -f docsim_postgres &
	$(PODMAN) logs -f docsim_redis

VENV := .venv/bin

init-db:
	cd backend && $(VENV)/python scripts/init_db.py

dev:
	cd backend && $(VENV)/uvicorn main:app --reload --port 8000

benchmark:
	cd backend && $(VENV)/python scripts/benchmark.py --verbose
