# GitHub to Darkube pre-release operational runbook

Documentation HQ: [README](../../README.md)

**Target:** disposable `okr-pre-release` namespace/project on Hamravesh
Darkube  
**Source:** protected GitHub `pre-release` branch  
**Status:** manual pre-release rehearsal only  
**Data policy:** synthetic data only

This runbook operates the four-app pre-release described in
[`deploy/darkube/prerelease/README.md`](../../deploy/darkube/prerelease/README.md).
It deliberately stops at manual provider confirmation where Hamravesh's
public documentation does not establish an API or behavior. It does not
authorize production deployment.

## Operating contract

| App | Port/command | Ingress |
| --- | --- | --- |
| `okr-prerelease-web` | `3000`, `npm run start` | Public HTTPS |
| `okr-prerelease-bff` | `3001`, `node dist/src/server.js` | Public only if required by browser flow |
| `okr-prerelease-api` | `8100`, `python -m backend_app.run_api` | Private |
| `okr-prerelease-worker` | no port, `python -m backend_app.worker` | None |
| `okr-prerelease-postgres` | private PostgreSQL address from console | None |

The API and worker use the same backend image inputs. All four apps use one
merged commit. The database is empty before migration and may be destroyed at
any time.

## Build, release, and run contract

CI is the only build authority for a release candidate. It builds the web,
BFF, backend API, and worker from one commit and publishes the resulting
images to private GHCR. The release manifest binds that commit to the four
image digests, signatures, and staging verification evidence.

Darkube must run the digests from that approved manifest. Production promotion
is a promotion of the same artifacts that passed staging, not a rebuild or a
mutable-tag lookup. Keep the previous complete manifest available so the API,
worker, BFF, and web can be rolled back as a compatible set.

Runtime secrets and configuration are injected by Darkube. They are not copied
into images or source, and migrations are run as a separate release operation,
not implicitly as an application boot side effect. The local Compose
`--build` workflow is for development only and is not evidence of an immutable
staging or production release.

## Horizontal scaling procedure

Scale the independently deployable services according to the observed
bottleneck:

| Service | Scaling purpose | Operational constraint |
| --- | --- | --- |
| `okr-prerelease-api` | HTTP request concurrency | Keep replicas stateless and use private service ingress. |
| `okr-prerelease-worker` | Queue/job throughput | Use multiple consumers only with the database-backed job claim contract. |
| `okr-prerelease-bff` | Browser request/session capacity | Share the configured session-secret contract across replicas. |
| `okr-prerelease-web` | Static/document serving capacity | Keep the same immutable web artifact on every replica. |

For a Compose-compatible target, the control is explicit service scaling:

```sh
docker compose -f deploy/docker/docker-compose.yml up -d \
  --scale backend-api=2 \
  --scale backend-worker=2 \
  --scale spa-bff=2 \
  --scale spa-web=2
```

For Kubernetes, use the corresponding Deployment replica count or
`kubectl scale deployment`. Do not treat `deploy.replicas` as proof that
ordinary `docker compose up` created replicas. After scaling, record health,
latency, queue depth, and database connection usage. Darkube ingress routing,
restart behavior, and resource limits still require provider-side evidence.

## Start/release procedure

1. Confirm the GitHub `pre-release` branch is protected and the target commit
   passed the repository's required checks.
2. Confirm the Darkube target is `okr-pre-release`, not a production or
   customer project.
3. Confirm the database is private, synthetic, and in the same provider scope
   required for private application connectivity.
4. In the Darkube console, verify each app points to the same repository,
   branch, commit, build context, and Dockerfile listed above.
5. Start/build the database and four apps using the console. Do not assume
   Docker Compose dependency or networking semantics.
6. Inspect build logs before exposing the web URL. Stop if credentials or
   unexpected source refs appear.
7. Run the migration once from the API terminal:

```sh
alembic upgrade head
```

8. Verify the API, BFF, web, and worker using the checklist below.
9. Copy the four observed image references and digests from the Darkube
   console into the workflow's `darkube_deployment_evidence_json` input. Use
   the JSON contract in [`deploy/darkube/prerelease/README.md`](../../deploy/darkube/prerelease/README.md#41-capture-deployment-evidence-for-digest-verification).
10. Confirm the workflow's `deployment-verification.json` artifact reports
    `"verified": true` before announcing the pre-release URL.
11. Record sanitized evidence before announcing the pre-release URL.

## Configuration checklist

Set the documented SaaS profile values in Darkube configuration:

```text
OKR_DEPLOYMENT_PROFILE=single_tenant_saas
OKR_SAAS_MODE=true
OKR_DATA_ACCESS_MODE=database
OKR_ENVIRONMENT_ID=okr-prerelease
OKR_CUSTOMER_ID=synthetic-prerelease
OKR_BACKUP_PROVIDER=deferred
OKR_BACKUP_SCHEDULE=deferred
OKR_BACKEND_ENFORCE_TOKEN=true
OKR_BACKEND_ENFORCE_REQUEST_SIGNING=true
OKR_BACKEND_PROXY_MUTATIONS=true
OKR_BACKEND_PROXY_READS=true
OKR_ALLOW_LOCAL_MUTATION_FALLBACK=false
OKR_ALLOW_LOCAL_READ_FALLBACK=false
OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN=false
OKR_ENFORCE_STRONG_PASSWORD_POLICY=true
OKR_STRICT_RUNTIME_PREFLIGHT=true
BFF_COOKIE_SECURE=true
```

`OKR_DATA_ACCESS_MODE` is an explicit backing-service adapter selection, not a
fail-open fallback. `database` uses the environment-provided PostgreSQL URL;
`supabase_api` uses the environment-provided `SUPABASE_URL` and API key for
the operations supported by that adapter. Select one mode deliberately for an
environment and validate its complete operation coverage before release.

Store the private database URL, backend token/signing secret, BFF session
secret, and synthetic administrator password as Darkube secrets. Keep
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_ANON_KEY` empty.
Generate fresh values for every reset. Never place secret values in this file,
GitHub, or evidence.

## Verification checklist

Record PASS/FAIL and the observation time for every item:

- Web public HTTPS URL returns a successful response and renders the shell.
- TLS certificate is valid for the actual pre-release domain.
- BFF `/healthz` returns an OK response through its approved route.
- API `/healthz` returns an OK response through a private or provider-approved
  probe path.
- Worker status is running and its runtime log contains a startup/healthy
  signal.
- Synthetic login succeeds; no real identity is used.
- The existing bounded web smoke or Playwright login-to-Atlas journey passes
  against the pre-release URL.
- Database connectivity works and the Alembic head is recorded.
- API and worker are using the same commit/build identity.
- Build/runtime logs are accessible and contain no secret values.
- Previous-version redeployment has either passed or is explicitly blocked by
  a provider confirmation gate.

When live URLs are available, the existing repository probes may be used. Run
them from a controlled operator workstation and do not include passwords in
shell history or CI logs:

```sh
python scripts/verify_deploy_readiness.py --help
python scripts/slo_probe.py --base-url https://<pre-release-web-or-bff-url> \
  --username <synthetic-user> --password <synthetic-password>
```

The angle-bracket values are operator placeholders, not literal deployment
values. Do not claim a probe passed if it was not run against the live target.

## Logs and evidence

Use the Darkube console for build logs, runtime logs, events, and health state.
Capture sanitized evidence with:

- `okr-pre-release` target name
- four application names
- Git commit SHA
- provider build/deployment IDs, if the console shows them
- database resource ID and PostgreSQL version, without connection details
- migration head
- health/smoke/SLO results
- rollback/redeployment result
- operator and UTC timestamp

Do not capture environment pages, database URLs, passwords, tokens, session
cookies, kubeconfig content, or unredacted log output. If provider logs are
not retained or cannot be accessed, mark the log gate FAIL rather than
assuming the deployment is healthy.

## Failure handling

### Build failure

1. Keep the failed commit recorded.
2. Read the failing app's Darkube build log.
3. Do not fix by changing the production target or by adding secrets to Git.
4. Correct the branch through a reviewed commit and repeat the four-app
   same-commit deployment.

### Runtime or health failure

1. Stop announcing the URL and freeze new merges.
2. Check the app's runtime logs, port, command, and environment configuration.
3. Confirm private API-to-database and BFF-to-API routing using provider-
   supported addresses only.
4. If the schema changed, do not downgrade the database. Reset this disposable
   database and run `alembic upgrade head` once.
5. Redeploy the previous known-good version as described below.

### Migration failure

1. Stop all API/worker rollout activity.
2. Preserve the failed commit and migration output without secrets.
3. Do not run the migration concurrently or attempt an unverified downgrade.
4. Destroy and recreate the disposable database, then rerun the approved head
   migration after the branch is corrected.

## Application rollback rehearsal: paired BFF/backend artifacts

**Current status: NOT PERFORMED.** This section defines the rehearsal; it is
not evidence that a rehearsal has occurred. Do not mark it `PASS` until the
operator has executed every step and attached sanitized provider evidence.

This is an **application-artifact rollback only**. The rollback unit is the
previous known-good release identity shared by `okr-prerelease-bff`,
`okr-prerelease-api`, and `okr-prerelease-worker`, with the web artifact kept
on the same release identity. Do not change, downgrade, restore, or otherwise
recover the database during this rehearsal. Database backup and recovery are
a separate operational capability and remain governed by their own approved
procedure and owner decision.

### Preconditions

1. Use the disposable `okr-pre-release` target only; never use a customer or
   production target.
2. Freeze deployments and record the current release identity (`new`): Git
   SHA, image references, image digests, Darkube build/deployment IDs, and
   migration head.
3. Select the previous immutable known-good release identity (`old`) in the
   Darkube console. Do not use a mutable tag or an unverified image.
4. Confirm that the old BFF, API, worker, and web artifacts are available and
   were built from the same release identity.
5. Confirm synthetic credentials are available without writing them to shell
   history, logs, or this record.
6. Capture a baseline for all health checks below while `new` is serving.

If Darkube cannot identify and redeploy an immutable previous build, mark the
rehearsal `BLOCKED` and request provider confirmation. Do not invent an API,
SSH path, host-level rollback, or database operation.

### Execution

1. Announce the rehearsal start to the responsible operator and record the UTC
   start time.
2. Use only the documented Darkube redeploy action to deploy `old` to web,
   BFF, API, and worker. Keep the four artifacts aligned; do not roll back
   only the BFF or only the backend.
3. Wait for provider rollout completion and record the resulting artifact
   identities and deployment events.
4. Run the health gates in order:
   - web public HTTPS responds successfully and renders the shell;
   - BFF `/healthz` responds successfully through the approved route;
   - API `/healthz` responds successfully through a private or approved probe;
   - worker reports running and emits its startup/healthy signal;
   - BFF-to-API connectivity succeeds without public database exposure;
   - synthetic login succeeds and the login-to-Atlas smoke journey passes;
   - a representative read and mutation succeed through the BFF path;
   - runtime logs contain no credentials, tokens, cookies, or signing secrets.
5. Confirm the database resource, schema, and data were not modified by the
   rehearsal. Record the observed migration head only; do not run Alembic
   downgrade, restore a dump, or alter database data.
6. Record the rehearsal result and UTC end time. If any gate fails, mark the
   rehearsal `FAIL`, stop announcing the URL, preserve sanitized evidence,
   and escalate before attempting another deployment.
7. If the exercise requires returning to `new`, perform a separate documented
   redeployment of the same immutable `new` identity and repeat the health
   gates. Record that restoration independently from the rollback result.

### Required rehearsal evidence

Copy this record into the approved evidence location and replace every
placeholder. Leave the status as `NOT PERFORMED` when no live rehearsal has
been run.

```text
Application rollback rehearsal status: NOT PERFORMED | PASS | FAIL | BLOCKED
Target: okr-pre-release
Operator:
UTC start:
UTC end:
Reason/change reference:

New release identity (serving before rehearsal):
  Git SHA:
  web image@digest:
  BFF image@digest:
  API image@digest:
  worker image@digest:
  Darkube build/deployment IDs:

Old release identity (rollback target):
  Git SHA:
  web image@digest:
  BFF image@digest:
  API image@digest:
  worker image@digest:
  Darkube build/deployment IDs:

Health gates:
  web HTTPS shell: NOT RUN | PASS | FAIL
  BFF /healthz: NOT RUN | PASS | FAIL
  API /healthz: NOT RUN | PASS | FAIL
  worker running/healthy signal: NOT RUN | PASS | FAIL
  BFF-to-API connectivity: NOT RUN | PASS | FAIL
  synthetic login and smoke: NOT RUN | PASS | FAIL
  representative read/mutation through BFF: NOT RUN | PASS | FAIL
  secret-free logs: NOT RUN | PASS | FAIL

Database separation:
  database changed: NO | YES | UNKNOWN
  migration head before/after:
  backup/restore/downgrade attempted: NO | YES
  database recovery evidence reference (if separately approved):

Restoration to new release (if performed):
  result: NOT RUN | PASS | FAIL
  resulting identities/digests:

Evidence references (sanitized logs, events, probes, screenshots):
Failure/blocker and follow-up owner:
```

The evidence must not contain environment pages, database URLs, passwords,
tokens, session cookies, kubeconfig content, or unredacted logs. A successful
application rollback rehearsal does not close the database backup/recovery,
RPO/RTO, or provider-recovery gates.

## Reset and destroy

This procedure intentionally destroys all pre-release data:

1. Confirm the target name and record current evidence.
2. Remove or disable public ingress.
3. Delete the four Darkube apps and the disposable PostgreSQL resource in the
   console, verifying the resource name before each action.
4. Remove the disposable DNS/TLS attachment and revoke all pre-release
   secrets.
5. Confirm no production/customer resource was selected.
6. Recreate the private database and four GitHub-connected apps, then migrate
   once from the API terminal.

If the console cannot prove isolated deletion, stop and request Hamravesh
confirmation. Never delete a shared or production resource to reset this
environment.

## Provider confirmation gates

These are not assumptions:

- private cross-app routing and the actual service/address syntax
- database version and private connectivity
- secret masking and secret visibility behavior
- custom-domain DNS, TLS issuance, and renewal
- build/runtime log access and retention
- previous-build redeployment
- isolated namespace/database deletion
- any provider API, Terraform provider, webhook, or automated backup export

An unconfirmed item is a BLOCKED operational gate, not a reason to substitute
public access, a guessed hostname, or undocumented automation.

## No-production-data stop rules

Stop immediately and destroy the target if any of the following occurs:

- a production database URL, dump, backup, export, or customer data is used;
- a production password, signing key, session secret, API key, backup
  credential, domain, or cloud-admin token is entered;
- public database access is enabled as a workaround;
- the API or worker is exposed publicly without an explicit reviewed reason;
- a GitHub or Hamravesh administrative credential is placed in source or logs.

This pre-release target does not close production backup/recovery, provider
selection, RPO/RTO, operations ownership, rollback rehearsal, or SaaS Phase 1
evidence gates.
