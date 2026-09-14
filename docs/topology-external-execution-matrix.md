# Topology external-execution matrix

This matrix is the execution record for the external-only P2 checks. Run every
row against a disposable or staging environment using the same immutable
release identifier and equivalent synthetic traffic. Never run the stop,
rollback, or migration commands against production without the applicable
change approval and backup confirmation.

For provider-specific deployment, ingress, rollback, and Hamravesh recovery
steps, use the [provider evidence checklist](saas/provider-evidence-checklist.md)
as the operational companion to this matrix. Keep one evidence bundle keyed by
the same release ID; do not create separate, conflicting status records.

Before starting, define `RELEASE_ID`, `OPERATOR`, `TOPOLOGY`, and
`EVIDENCE_DIR` for the release record:

```bash
export RELEASE_ID="<immutable image tag or commit SHA>"
export OPERATOR="<named operator>"
export TOPOLOGY="bff"                 # repeat with direct-api for the candidate
export EVIDENCE_DIR="evidence/$TOPOLOGY"
mkdir -p "$EVIDENCE_DIR"
```

| Check | Command/action | Expected result | Evidence | Failure action |
|---|---|---|---|---|
| Baseline/candidate SLO | `python scripts/slo_probe.py --base-url <origin> --username <user> --password-env <ENV> --release-id "$RELEASE_ID" --operator "$OPERATOR" --topology "$TOPOLOGY" --output "$EVIDENCE_DIR/slo.json"`; repeat with `TOPOLOGY=direct-api` and a separate output directory | Probe completes; all results and failures are recorded for both topologies | Two SLO JSON files with matching release ID, timestamps, operators, and topology names | Hold comparison; inspect `detail` and logs |
| SLO comparison | `just topology-compare evidence/bff/slo.json evidence/direct-api/slo.json evidence/topology-comparison.json` | Comparison passes and records per-SLO deltas | Comparison JSON | Do not approve simplification; investigate regressions |
| Resource overhead | `just topology-resources-sampled "$EVIDENCE_DIR/resources.json" 10 1 "$RELEASE_ID" "$OPERATOR" "$TOPOLOGY"` while synthetic probe traffic runs; repeat for the candidate | Stable container set; peak CPU and latest memory recorded | Resource JSON and traffic window for each topology | Repeat with equivalent load |
| Session/CSRF/actor/signing/allowlist/rate limits | Run `npm --prefix spa-bff test` and `python -m pytest -q tests/test_backend_private_ingress_enforcement.py tests/test_auth_rate_limit.py tests/test_backend_security_state.py`; repeat the equivalent live cases and validate with `just topology-security-review <file>` | Each control explicitly passes with a sanitized observation | Security manifest and linked observations | Do not simplify topology; fix control parity |
| BFF unavailable | `docker compose ... stop spa-bff`; run backend readiness and browser-origin checks; then `docker compose ... start spa-bff` | API remains independently diagnosable; browser path fails boundedly; recovery returns readiness | Failure-isolation scenario artifact | Restore BFF and hold release if API is masked or recovery fails |
| API unavailable | Stop `backend-api`; check BFF health and an authenticated proxied request; restart API | BFF does not claim a healthy dependency path; API recovery restores the request | Failure-isolation scenario artifact | Restore API and inspect timeout/error shaping |
| Worker unavailable | Stop `backend-worker`; check API readiness and queue/degraded behavior; restart worker | API remains ready; queue health is observable; worker recovery is recorded | Failure-isolation scenario artifact | Restore worker and inspect queued jobs |
| Application rollback | Restore previous backend/BFF/web digests, run `python scripts/verify_deploy_readiness.py ...`, then verify smoke/auth checks; record `last_known_good_release` and `candidate_release` in the rollback template | Last-known-good pair is healthy and data integrity is verified | Rollback manifest and readiness output | Keep previous release active; do not promote |
| Tenant migrations | Run `.github/workflows/saas-migrations.yml` or `just saas-migrate` with the approved inventory and URL mapping; attach the report to `$RELEASE_ID` | Every tenant reports a revision; any failure makes the release incomplete | Migration JSON report keyed to the release | Stop promotion, preserve report, repair and rerun |

## Evidence ownership and retention

Every artifact must include the release identifier, capture timestamp, operator,
topology name, and links to sanitized logs or command output. Store the complete
set under the release evidence record, retain it according to the provider’s
operations policy, and never store passwords, cookies, database URLs, tokens,
or raw request/response bodies.

The final review is complete only after the four category validators pass:

```text
just topology-security-review evidence/security-parity.json
just topology-failure-review evidence/failure-isolation.json
just topology-rollback-review evidence/rollback-rehearsal.json
just topology-review evidence/topology-review.json
```

## GitHub Actions configuration

Configure these repository or environment secrets before using the manual
workflows:

- `SAAS_PROVISIONING_STATE_JSON`: sanitized tenant inventory containing opaque
  environment and database-resource identifiers;
- `SAAS_DATABASE_URLS_JSON`: protected mapping from database-resource ID to the
  corresponding database URL;
- `TOPOLOGY_BASE_URL`, `TOPOLOGY_USERNAME`, and `TOPOLOGY_PASSWORD`: staging
  probe credentials for `topology-evidence.yml`.

Use GitHub’s protected-environment rules for staging/production approvals. Do
not place any of these values in the repository or in evidence artifacts.
