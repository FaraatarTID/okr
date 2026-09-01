# Canonical cross-platform developer commands.
# Prerequisites: just, uv, Node.js/npm, and Docker for stack commands.

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

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
    uv run python scripts/check_ci_script_references.py
    uv run python scripts/check_openapi_drift.py
    npm --prefix spa-web run check:gen:api
    npm --prefix spa-bff run check:gen:api
    uv run python scripts/check_import_boundaries.py
    uv run python scripts/check_spa_bff_boundaries.py
    uv run python scripts/check_deployment_topology.py

generate-api:
    uv run python scripts/export_openapi.py
    npm --prefix spa-web run gen:api
    npm --prefix spa-bff run gen:api

saas-evidence:
    uv run python scripts/check_saas_phase1_evidence.py

measure:
    uv run python scripts/measure_task_graph.py

check: lint typecheck test contracts

start:
    docker compose -f deploy/docker/docker-compose.yml up -d --build backend-api backend-worker spa-bff spa-web

stop:
    docker compose -f deploy/docker/docker-compose.yml down

health:
    docker compose -f deploy/docker/docker-compose.yml ps

saas-provision MANIFEST CREDENTIAL_FILE STATE_FILE="tmp/saas-environments.json":
    uv run python scripts/provision_saas_environment.py provision --manifest "{{MANIFEST}}" --credential-file "{{CREDENTIAL_FILE}}" --state-file "{{STATE_FILE}}"

saas-suspend ENVIRONMENT_ID CREDENTIAL_FILE STATE_FILE="tmp/saas-environments.json":
    uv run python scripts/provision_saas_environment.py suspend --environment-id "{{ENVIRONMENT_ID}}" --credential-file "{{CREDENTIAL_FILE}}" --state-file "{{STATE_FILE}}"

saas-retire ENVIRONMENT_ID CREDENTIAL_FILE STATE_FILE="tmp/saas-environments.json":
    uv run python scripts/provision_saas_environment.py retire --environment-id "{{ENVIRONMENT_ID}}" --credential-file "{{CREDENTIAL_FILE}}" --state-file "{{STATE_FILE}}"
