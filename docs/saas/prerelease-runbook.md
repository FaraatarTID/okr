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

## Previous-version redeployment rehearsal

The rollback target is the previous known-good Darkube build/version or its
exact Git commit, selected in the provider console. It is not a mutable tag.

1. Freeze the branch and identify old and current commit/build IDs.
2. Use only the Darkube console action documented by the provider to redeploy
   the previous version for web, BFF, API, and worker.
3. Keep all four components aligned to the same previous release identity.
4. Verify health, synthetic login, smoke, and worker status.
5. Record operator, reason, old/new identities, result, and verification.

If Darkube does not expose a previous-build redeploy action, mark the rehearsal
BLOCKED and request provider confirmation. Do not invent an API, SSH path, or
host-level rollback mechanism.

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
