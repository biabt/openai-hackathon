SHELL := /bin/sh

.PHONY: install artifacts test demo smoke

install:
	cd backend && uv sync --frozen
	cd frontend && npm ci

artifacts:
	uv run --project backend python scripts/demo_prepare.py

test: artifacts
	cd backend && uv run pytest -q
	cd frontend && npm run contracts:check
	cd frontend && npm test
	cd frontend && npm run typecheck

demo: artifacts
	uv run --project backend python scripts/demo_start.py

smoke: artifacts
	uv run --project backend python scripts/demo_smoke.py
