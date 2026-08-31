Documentation HQ: [README](../README.md)

# Service-Aware Task-Graph Evaluation

Lifecycle: Operational | Owner: Platform/Operations | Last reviewed: 2026-08-31

## Decision

Do not adopt Turborepo or Nx yet. The repository already has npm workspaces,
`uv.lock`, source-aware CI caches, and the root `justfile`. A heavier task-graph
tool should be introduced only when measured CI waste or service growth makes
the added configuration worthwhile.

## Current task graph

```text
just install
  -> uv sync --group dev
  -> npm install

just test
  -> Python pytest
  -> npm workspace tests (spa-bff + spa-web)

just typecheck
  -> spa-web TypeScript check
  -> spa-bff build/type validation

just build
  -> workspace production builds

just contracts
  -> OpenAPI drift
  -> Python import-boundary gate
```

The current CI split is intentional: backend quality, SPA quality, deploy
build, and optional end-to-end jobs have different dependencies and failure
signals. Do not merge them merely to create a visual task graph.

## Measurement protocol

For at least five comparable runs on the same runner class, record:

| Run | Workflow/job | Total duration | Cache hit | Repeated work observed | Notes |
| --- | --- | ---: | --- | --- | --- |
| 1 |  |  |  |  |  |
| 2 |  |  |  |  |  |
| 3 |  |  |  |  |  |
| 4 |  |  |  |  |  |
| 5 |  |  |  |  |  |

Use the existing GitHub Actions job summary cache fields for Next.js and BFF
incremental state. Record external deployment observations separately because
hosted CI cache behavior does not prove deployment-environment equivalence.

For a local comparable baseline, run `just measure`. For a focused measurement,
run `uv run python scripts/measure_task_graph.py --task contracts --output
tmp/task-graph-contracts.json`. The collector records command, duration, and
exit code as JSON; it does not represent hosted cache hits.

## Promotion criteria

Trial a task-graph tool only if one or more of these conditions is evidenced:

- repeated CI work materially increases build duration as services grow;
- independent jobs cannot reuse current workspace/cache boundaries effectively;
- a measured task graph can reduce work without weakening contract, security,
  migration, or readiness gates;
- the target external deployment environments can consume the resulting graph
  and dependency contract.

Until then, maintain the `justfile`, npm workspace scripts, `uv` lockfile, and
existing source-aware caches as the supported developer and CI model.
