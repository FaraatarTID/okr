# SDD ledger - plan: docs/superpowers/plans/2026-09-01-single-tenant-saas-plan.md

Task 1: complete (focused tests 22 passed; review clean after fix round 1)
Task 1: fix round 1/5 (4 addressed, 0 open; environment contract, documentation, and tests)
Ruling: control plane is modeled as an external management boundary, not a customer-environment deployment profile - this preserves the approved control-plane separation; if wrong, a later contract revision is required.
Task 2: complete (focused tests 27 passed; review clean after fix rounds 1-3)
Task 2: fix round 1/5 (runtime preflight, explicit SaaS template, compatibility coverage)
Task 2: fix round 2/5 (normalized SaaS flags, env-file enforcement, empty URL semantics)
Task 2: fix round 3/5 (behavioral fallback/rejection tests)
Task 3: complete (focused tests 14 passed; review clean after fix rounds 1-3)
Task 3: fix round 1/5 (persistent metadata provider, compensation, CLI safety)
Task 3: fix round 2/5 (atomic persistence, validation ordering, cleanup continuation, immutable inputs)
Task 3: fix round 3/5 (atomic-write regression, cross-process retirement, typed state reload)
Ruling: provisioning metadata is persisted locally only as a disposable adapter and customer-domain data remains outside the lifecycle store - this keeps Phase 0 provider-neutral; if wrong, a durable control-plane store is needed in a later task.
Task 4: complete (focused tests 13 passed; review clean after fix rounds 1-3)
Task 4: fix round 1/5 (artifact binding, result statuses, persistence, exception rollback, CLI safety)
Task 4: fix round 2/5 (Compose release-image mapping and audit wording)
Task 4: fix round 3/5 (artifact-to-Compose mapping and behavioral tests)
Ruling: release rollback is application-only and must never use database restore as its routine mechanism - this limits blast radius and preserves the approved separation of concerns; if wrong, the release contract must be redesigned before production rollout.
Task 5: complete (focused tests 18 passed; review clean after fix rounds 1-4)
Task 5: fix round 1/5 (provider contract, checksum, status persistence, target safety)
Task 5: fix round 2/5 (failure-state persistence and registered restore targets)
Task 5: fix round 3/5 (provider failure persistence, RPO/RTO validation, evidence count)
Task 5: fix round 4/5 (adapter-independent verification failure metadata)
Ruling: no cloud-specific backup provider was invented before a provider is selected; the provider contract and test-only adapter are the safe boundary - if wrong, a provider-specific adapter must be added before real SaaS data onboarding.
Task 6: complete (focused/boundary tests 34 passed; review clean after fix round 1)
Task 6: fix round 1/5 (production route, import checks, metadata coverage, operator authorization, durable audit state)
Ruling: control-plane operator authorization retains an admin compatibility fallback while exposing a distinct operator seam - this preserves existing deployments while enabling separation; if unsafe in a production identity system, the fallback must be removed before onboarding operators.
Task 7: complete (documentation/evidence checks passed; review clean after fix rounds 1-2)
Task 7: fix round 1/5 (concrete local evidence, final test counts, provider gaps, ownership status)
Task 7: fix round 2/5 (consistent release artifact labels)
Ruling: Phase 1 remains BLOCKED despite clean local evidence because no provider-specific production backup, deployment artifact, measured RPO/RTO, or operations owner is available - this prevents false SaaS readiness; if wrong, the missing production evidence must be supplied before changing the status.

Final blocker fix wave: complete (structured evidence validation, persistent crash-safe locking, canonical provider IDs, failure reconciliation, authenticated lifecycle audit, and multi-process control-plane merge protection)
Evidence: affected regression suites and the executable `just saas-evidence` gate validate required evidence values rather than headings, bounded lock recovery without lock-path deletion, degraded failure states, operator identity, canonical database IDs, and concurrent metadata/event preservation. Provider-backed backup/rollback evidence and named operations ownership remain production gates.
Status ruling: whole-plan integration is hardened without changing normalized profiles, on-premise compatibility, metadata-only control-plane scope, or the explicit Phase 1 production block. Shared-database RLS, tenant schema, and real-data onboarding remain deferred.

Final whole-plan review remediation: implemented (machine-readable production
attestation gate, authenticated credential-file/token lifecycle identity,
credential-aware just recipes, shared persistence locking for local release and
backup state, and strict canonical provider database-resource validation).
Current evidence remains intentionally blocked for missing real provider
evidence, measured production values, and named operations ownership. No live
provider was invoked and tenant/RLS/customer-domain behavior was unchanged.
Verification: affected suites `73 passed in 3.50s`; Ruff passed; documentation
link check passed for 76 Markdown files. The current evidence gate correctly
fails closed with missing production attestation fields. Direct `just --dry-run`
invocation was attempted for all three lifecycle recipes but Windows denied
execution of the installed `just.exe`; recipe definitions and credential
arguments were inspected without invoking any lifecycle operation.

Final trust-boundary hardening wave: implemented (HMAC-SHA256 attestation
verification with canonical payload binding, typed authenticated operator
credentials at all lifecycle service APIs, and guarded control-plane
initialization writes). Current evidence remains blocked because provider
evidence, named operations ownership, and the configured attestation secret are
unavailable. No live provider was invoked; tenant/RLS/customer-domain behavior
was unchanged.

Final review hardening pass: complete (80 focused tests passed; Ruff and import-boundary checks passed; evidence gate remains intentionally blocked by absent production provider/owner evidence). Fixed HMAC evidence identity/measurement binding, lock-scoped release/backup persistence, backup response environment validation, and production fail-closed control-plane authorization. Scope unchanged: no tenant/RLS work and no real provider onboarding.
# Final review

- Final whole-plan review initially found four hardening issues: incomplete HMAC cross-binding, stale-snapshot release/backup writes, missing backup environment validation, and permissive production operator fallback.
- Hardening pass resolved all four issues and added regression coverage.
- Scoped re-review: PASS. Focused tests: 46 passed. Ruff and import-boundary checks passed in the hardening pass.
- Production evidence gate remains intentionally blocked because no real provider, production measurements, operations owner, approval, or signed production attestation are available.
- Shared-database tenancy and RLS remain explicitly deferred; the delivered architecture is dedicated application plus dedicated database per enterprise.
