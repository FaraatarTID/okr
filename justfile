# Canonical cross-platform developer commands.
# Prerequisites: just, uv, Node.js/npm, and Docker for stack commands.

default:
    @just --list

install:
    uv sync --group dev
    npm install

test: test-python test-javascript

test-python:
    uv run pytest -q

test-javascript:
    npm test

typecheck:
    npm run typecheck

build:
    npm run build

lint:
    uv run ruff check backend_app scripts tests

contracts:
    uv run python scripts/check_openapi_drift.py
    uv run python scripts/check_import_boundaries.py

measure:
    uv run python scripts/measure_task_graph.py

check: lint typecheck test contracts

start:
    docker compose -f deploy/docker/docker-compose.yml up -d --build backend-api backend-worker spa-bff spa-web

stop:
    docker compose -f deploy/docker/docker-compose.yml down

health:
    docker compose -f deploy/docker/docker-compose.yml ps
