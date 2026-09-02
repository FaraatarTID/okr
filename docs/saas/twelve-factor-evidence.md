# Twelve-Factor Evidence Ledger

This ledger applies the [Twelve-Factor App methodology](https://12factor.net/)
to the dedicated-server-per-customer deployment model. Each customer receives
an isolated application environment and PostgreSQL database. Shared
multi-tenancy and RLS are not part of this architecture.

## Status rules

- `PASS`: the specific repository contract or provider evidence is attached and successful.
- `PARTIAL`: the repository contract exists, but operational evidence is incomplete.
- `PENDING_PROVIDER_EVIDENCE`: requires Darkube or Hamravesh access and must not be inferred from local tests.
- A repository `PASS` never implies provider `PASS`. `verify_environment_parity.py` reports these separately.

| Factor | Current status | Evidence | Remaining work |
|---|---|---|---|
| I. Codebase | PASS | One revision-controlled repository builds all service artifacts. | None identified. |
| II. Dependencies | PASS | `pyproject.toml`/`uv.lock` and npm workspace lockfiles are checked by CI. | Keep lockfiles synchronized. |
| III. Config | PASS | Runtime configuration and production secrets are environment-injected and validated. | Keep provider secret names aligned. |
| IV. Backing services | PASS | PostgreSQL and external services are configured by URL/resource settings. | Attach provider evidence when configured. |
| V. Build, release, run | PASS | CI builds immutable GHCR artifacts and promotion uses the release manifest. | Reconfirm on each release workflow change. |
| VI. Processes | PASS | API, worker, BFF, and web run as separate processes; customer data is externalized to PostgreSQL; control-plane persistence is opt-in for operator processes. | None identified in repository/runtime contract. |
| VII. Port binding | PASS | Services bind configured ports and expose health endpoints. | None identified. |
| VIII. Concurrency | PASS | API worker counts and service replicas are environment-driven; atomic job claiming prevents duplicate work. | Provider-level scaling evidence remains external. |
| IX. Disposability | PASS | Health checks, restart policies, cooperative worker shutdown, and smoke tests exist. | Provider restart rehearsal remains external. |
| X. Dev/prod parity | PARTIAL | Local Compose and release images share service topology; provider evidence is separately gated. | Verify the same manifest plus health, restart, and ingress observations in Darkube. |
| XI. Logs | PASS | Runtime and audit/error logs use structured process streams with secret redaction; database audit persistence is separate. | Provider retention/alert evidence remains external. |
| XII. Admin processes | PASS | Migrations and operational verifiers run as explicit one-off commands. | Keep migration and recovery evidence current. |

## Provider evidence gate

The following cannot be closed by repository tests alone:

1. Darkube private GHCR pull, service health, restart, resource, scaling, and failure-isolation evidence.
2. Application rollback using two immutable release manifests.
3. Hamravesh production PostgreSQL backup and isolated restore evidence.

Until those operations are performed, the relevant rows remain
`PENDING_PROVIDER_EVIDENCE` and customer-data onboarding remains blocked by
the production recovery prerequisite.

Evidence validators are intentionally fail-closed. A `PASS` from a repository
validator means only that the supplied record is structurally complete, marked
successful, bound to its canonical payload, and includes a non-synthetic
attestation envelope. Failed, local/test/fixture, unsigned, or incomplete
records are rejected. The validators do not authenticate a provider signature
or claim that a provider operation occurred; that requires external evidence.

## Verification commands

```bash
python scripts/verify_twelve_factor_contract.py
python scripts/verify_process_contract.py
python scripts/verify_logging_contract.py
python scripts/verify_environment_parity.py
# With sanitized provider evidence and its matching release manifest:
python scripts/verify_environment_parity.py --manifest release-manifest.json --evidence darkube-deployment-evidence.json
python scripts/verify_admin_process_contract.py
```

## Sanitized Darkube evidence contract

`verify_darkube_deployment.py` requires schema version 2. Evidence must contain
the exact release commit and image digests for `web`, `bff`, `api`, and `worker`,
plus all of the following independently observed results:

- `health`: `passed` for every application.
- `restart`: `status: passed` and a service list containing every application.
- `ingress`: `status: passed` and checks for `web`, `bff-health`, and `api-health`.

Absent evidence is reported as `PENDING_PROVIDER_EVIDENCE`. Supplied evidence
that is incomplete, failed, or mismatched exits non-zero. The verifier does not
contact Darkube and cannot authenticate operator claims; only sanitized evidence
produced from an actual provider observation may be supplied.
