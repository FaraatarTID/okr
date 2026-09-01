# Darkube pre-release setup

Documentation HQ: [README](../../../README.md)

This directory describes the disposable GitHub-to-Darkube pre-release target.
It is a manual console procedure, not a provider API client.

## Hard boundary

This environment is for synthetic demonstrations and release rehearsal only.
It is not production, customer hosting, disaster recovery, or evidence that
production SaaS gates are closed.

- Namespace/project: `okr-pre-release`
- Source branch: protected GitHub `pre-release`
- Database: `okr-prerelease-postgres`, private and disposable
- Applications: `okr-prerelease-web`, `okr-prerelease-bff`, `okr-prerelease-api`, `okr-prerelease-worker`
- Runtime profile: `single_tenant_saas` with `OKR_SAAS_MODE=true`
- Data: synthetic records only; never copy production data or credentials

Do not infer an undocumented Darkube API, Terraform provider, service DNS
name, cross-cluster route, or rollback endpoint from this document. Where the
console does not expose a capability described below, stop and record the
provider confirmation gate instead of substituting a public database or an
unverified automation path.

## 1. Prepare GitHub

1. Create or confirm the `pre-release` branch in the repository.
2. In GitHub, open **Settings > Branches** and add branch protection for
   `pre-release`.
3. Require pull requests, required approvals, and the repository's existing
   quality checks before merging. Do not require a check name that does not
   exist in the repository.
4. Disable direct pushes and force-pushes for the branch.
5. Record the merge commit SHA for every Darkube deployment. A Git commit SHA,
   not `latest`, is the release identity.

The Darkube connection must be created from the Darkube console using the
repository's GitHub authorization flow. Do not place a GitHub personal access
token in application environment variables or repository files.

## 2. Create the disposable Darkube target

Use the Darkube console and create a project or namespace dedicated to this
pre-release target. Use the provider's current console labels; public
documentation does not establish a supported provisioning API.

Before creating applications, confirm all of the following in the console:

- The target is isolated from every production or customer project.
- The GitHub repository and `pre-release` branch can be selected.
- Application-to-application private networking is available in the same
  cluster and namespace.
- A database can be created with public access disabled.
- Logs and a previous-build or previous-version redeploy action are available.
- The target can be deleted without affecting another project.

If any confirmation fails, stop. Record the missing capability and do not
continue by enabling public database access or sharing another environment.

## 3. Create the private synthetic PostgreSQL database

Prefer a small managed PostgreSQL database in the same Hamravesh cluster and
namespace as the applications. A standalone disposable database is adequate
for this rehearsal; HA and production retention are not being claimed here.

In the database console:

1. Create PostgreSQL with a supported version compatible with the repository's
   migration and test baseline. Record the actual version.
2. Name it `okr-prerelease-postgres` or the closest provider-supported name.
3. Select the same cluster and namespace used by the four applications.
4. Disable public access. Do not add a public allowlist as a workaround.
5. Create a dedicated non-production database user and password. Do not use a
   production user or distribute the default superuser credentials.
6. Copy the private connection details shown by the console into the Darkube
   secret configuration only. Never commit the URL or password.
7. Verify that the private address is reachable from the API terminal before
   migrating. Use the exact address shown by the provider; do not invent a
   hostname such as `postgres`.

If the console cannot place the database and apps in a shared private network,
or cannot provide a private address, this setup is blocked pending Hamravesh
confirmation. Do not enable public database access.

## 4. Create the four GitHub-connected applications

Create each application through the Darkube console's GitHub repository flow.
For every app, select the same repository, the `pre-release` branch, and the
same merged commit. Use the build context and Dockerfile path shown below.
The Dockerfile paths are repository-relative. The backend API and worker share
the repository-root context and image; the BFF and web use their own
directory-scoped contexts.

| App | Name | Build context | Dockerfile | Port | Command | Public ingress |
| --- | --- | --- | --- | --- | --- |
| Web | `okr-prerelease-web` | `spa-web` | `spa-web/Dockerfile` | `3000` | `npm run start` (image default) | Yes, HTTPS |
| BFF | `okr-prerelease-bff` | `spa-bff` | `spa-bff/Dockerfile` | `3001` | `node dist/src/server.js` (image default) | Only if the browser needs a public BFF URL |
| API | `okr-prerelease-api` | repository root | `deploy/docker/Dockerfile` | `8100` | `python -m backend_app.run_api` (image default) | No; use provider-supported internal probing |
| Worker | `okr-prerelease-worker` | repository root | `deploy/docker/Dockerfile` | None | `python -m backend_app.worker` | No |

For each application, enter these console values:

1. **Source:** the same GitHub repository and `pre-release` branch.
2. **Build context:** the exact context in the table. Use repository root for
   API and worker, `spa-bff` for BFF, and `spa-web` for web.
3. **Dockerfile:** the exact path in the table. For BFF and web, select the
   Dockerfile relative to that directory if the console asks for a
   context-relative path.
4. **Port:** only the port in the table. The worker has no HTTP port.
5. **Command:** keep the Dockerfile default where shown; use the table only
   when Darkube requires an explicit command override.
6. **Resources:** start with the smallest useful non-production plan and
   increase only when observed build or runtime behavior requires it.
7. **Replicas:** one for the first rehearsal. Do not attach a persistent disk
   to a multi-replica app unless the provider confirms that combination.
8. **Deploy trigger:** enable the GitHub-connected branch deployment behavior
   only after a manual first build succeeds.

The API and worker must use the same backend image inputs and commit. All four
apps must report the same source commit in the deployment record. If Darkube
builds them from different commits, stop the release.

## 5. Configure networking and TLS

Keep API, worker, and database private. Configure the BFF to reach the API
using the internal address or service reference actually displayed or
documented by Darkube. Configure the web to use the BFF origin required by the
application, using the real pre-release URL after TLS is provisioned.

Do not guess provider service names or assume Docker Compose service names are
available. Darkube documents limited Compose translation, not full Compose
networking semantics.

For ingress:

1. Choose a disposable pre-release domain under a domain controlled by the
   team, or use the provider-generated URL while validating the deployment.
2. Attach the domain only to the web app, and to the BFF only when browser
   traffic requires it.
3. Use a Darkube-supported load balancer/ingress and enable TLS through the
   console's documented certificate flow.
4. Confirm HTTPS, certificate validity, health checks, and the final public
   origin before enabling `BFF_COOKIE_SECURE=true`.
5. Do not publish the API or database to the internet.

TLS issuance, DNS ownership, custom-domain limits, internal service routing,
and certificate renewal are provider confirmation gates if the console does
not expose them. Do not claim TLS or private routing until tested.

## 6. Configure non-production secrets

Store values in Darkube application configuration as secrets, not in GitHub
source, Dockerfiles, logs, or evidence artifacts. Generate fresh values for
this disposable target and rotate them by destroying and recreating the
target.

Required runtime values include:

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

Secret values must include the private `OKR_DATABASE_URL`,
`OKR_BACKEND_SERVICE_TOKEN`, `OKR_BACKEND_SIGNING_SECRET`,
`BFF_SESSION_SECRET` of at least 32 characters, and a synthetic
`OKR_BOOTSTRAP_ADMIN_PASSWORD`. Keep optional AI/PDF provider keys disabled
unless they are separately approved non-production credentials.

Keep `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_ANON_KEY`
empty in this SaaS-profile rehearsal. Do not add production backup, cloud
admin, customer, or company-server credentials.

Set component-specific values only from the repository's existing runtime
configuration contract. Do not invent variable names. The BFF must receive
the actual API internal origin, and the web/BFF origin values must match the
actual TLS URLs.

## 7. First deployment and migration

1. Build each app manually from the selected merged `pre-release` commit.
2. Inspect build logs for credentials, unexpected source refs, and the exact
   Dockerfile/context.
3. Start the database, API, worker, BFF, and web in that order only if the
   console requires ordering. Do not rely on Compose `depends_on` behavior.
4. Open the API terminal provided by the Darkube console and run the one-time
   schema command from the repository root:

```sh
alembic upgrade head
```

Run this once per database reset, against this disposable database only. Do
not run migrations concurrently from API replicas. If Darkube does not offer
an approved terminal or one-shot command facility, stop at the provider
confirmation gate and record the limitation.

5. Confirm the API `/healthz`, BFF `/healthz`, web shell, and worker startup
   signal. Continue with the verification steps in
   [`docs/saas/prerelease-runbook.md`](../../../docs/saas/prerelease-runbook.md).

## 8. Build/runtime logs and evidence

Use the Darkube console to inspect build logs, runtime logs, events, and health
status for each app. Record only sanitized metadata:

- Git commit SHA
- Darkube app names and provider build/deployment IDs, if shown
- Database resource ID and PostgreSQL version, without connection details
- Migration head
- Health, smoke, and worker results
- Operator and UTC timestamp
- Links to provider log views, if access-controlled

Never upload environment dumps, database URLs, passwords, tokens, cookies,
private kubeconfig values, or log excerpts containing secrets. If the console
cannot provide sufficient build/runtime logs, mark observability as blocked;
do not infer health from a successful build.

## 9. Reset, destroy, and redeploy

The complete reset is deliberately destructive because this target has no
valuable data:

1. Freeze the `pre-release` branch and record the current commit/build IDs.
2. Stop public ingress.
3. Delete the four apps and the disposable database from the Darkube console,
   confirming the target names before each destructive action.
4. Remove the target's DNS/TLS attachment and revoke its non-production
   secrets.
5. Confirm in the console that no production or customer resource was
   selected.
6. Recreate the database and apps using this document, then run `alembic
   upgrade head` once.

For a previous-version redeployment without a database reset:

1. Freeze new merges.
2. Identify the previous known-good Git commit and the Darkube build/version
   shown in the console.
3. Use the console's documented previous-build or previous-version redeploy
   action for all four apps, keeping their commits aligned.
4. Do not rebuild from a moving branch and do not use `latest` as a rollback
   reference.
5. Re-run API/BFF/web health checks, synthetic login, bounded smoke tests, and
   worker verification.
6. If the failed release changed the schema, reset the disposable database
   and rerun the controlled migration instead of attempting an unverified
   downgrade.
7. Record the operator, reason, old/new commit and build IDs, result, and
   verification output.

If the console has no previous-build redeploy action, the rollback rehearsal
is blocked pending Hamravesh confirmation. Do not invent a provider endpoint.

## Provider confirmation gates

The following must be confirmed manually in the current Darkube console before
this setup is called ready-to-use:

- GitHub monorepo path and Dockerfile selection work for all four apps.
- A merged `pre-release` commit triggers the expected builds.
- API, BFF, worker, and database private networking works as required.
- The required PostgreSQL version is available and public access stays off.
- Darkube secrets are hidden from logs and runtime configuration views as
  intended.
- Custom-domain DNS and TLS issuance/renewal work for the pre-release URL.
- Build logs, runtime logs, events, and health status are available.
- A prior build/version can be redeployed without rebuilding source.
- The namespace/project and database can be destroyed without affecting other
  environments.

Public Darkube documentation does not establish a general provisioning API,
Terraform provider, cross-cluster private networking, service DNS naming,
provider backup export, or automated rollback API. Those are explicitly
unconfirmed until Hamravesh provides and the operator tests them.

## No-production-data rules

- Never connect this environment to a production database.
- Never restore a production dump, backup, customer export, or real user data.
- Never reuse production passwords, signing keys, session secrets, API keys,
  backup credentials, domains, or cloud access tokens.
- Use synthetic users, synthetic OKRs, and test-only provider accounts.
- Keep the database private and the API/worker free of public ingress.
- Stop and destroy the target if a production value is pasted into its
  configuration or logs.
- This setup does not close production backup, RPO/RTO, rollback, ownership,
  or SaaS evidence gates.
