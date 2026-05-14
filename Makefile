.PHONY: install dev test lint migrate clean \
        frontend-install frontend-dev frontend-build frontend-lint

# ── Backend ───────────────────────────────────────────────────────────────────

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

dev:
	uvicorn backend.main:app --reload --port 8000

test:
	pytest backend/tests/ -v --tb=short

lint:
	ruff check backend/

migrate:
	@echo "Run migrations in Supabase SQL Editor (in order):"
	@echo "  1. backend/schema/migrations/001_initial.sql"
	@echo "  2. backend/schema/migrations/002_rls_policies.sql"
	@echo "  3. backend/schema/migrations/003_merchants.sql"
	@echo "  4. backend/schema/migrations/004_add_shiprocket_source.sql"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean complete."

# ── Frontend ──────────────────────────────────────────────────────────────────

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-lint:
	cd frontend && npm run lint
