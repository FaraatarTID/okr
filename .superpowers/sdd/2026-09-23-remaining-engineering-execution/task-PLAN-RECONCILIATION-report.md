Documentation HQ: [README](../../../README.md)

# Execution plan reconciliation — 2026-09-23

## Scope and result

Edited `docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md` and, for review fix round 1, `.superpowers/sdd/2026-09-23-remaining-engineering-execution/progress.md`. No application code or canonical register was edited. The plan now has **36 unique, contiguous packets, T00–T35**, with one self-consistency row for each. T32 covers P0-3, T33 covers the P0-4 SPA→BFF test, T34 covers the two P0-5 callerless controls, and T35 covers P0-8. T31 retains the separate deployed-edge part of P0-4. The steward's 32→36 ruling and coordination cost are recorded in the plan and progress ledger.

Revised the goal/status boundary; execution model and preflight; T00/T01 55-row reconciliation; T02/P0-2; T03 seven-kind actor audit; T13 frontend-only budget; T18 D1 details; T19 target recount before production integration; T23 identity interface; T24 atomic D2+D4 integration; T27 existing strict `--record` verification; T31 deployed-edge evidence; P0 mapping; hard dependencies; shared-file conflict matrix; 36-row self-consistency table; decision, acceptance, and fixed-assumption sections. The current B5 wording says `ci-result` depends on `migration-quality`, whose PostgREST Exposure Gate is a step; the old job name is historical. The README Documentation HQ link in the plan was retained.

## Requested checks — exact output

`python scripts/check_docs_hq_links.py` — exit 0:

```text
Documentation HQ link check passed (91 markdown files scanned).
```

`python scripts/check_quality_gate_baseline.py` — exit 0:

```text
Quality baseline review date: 2026-09-23
- QG-002: expires 2026-11-15 | Repo-wide mypy remains staged; broad default coverage is active for scripts plus the runtime-core backend_app modules. Measured 2026-09-20: 127 errors in 24 of 347 checked files (src 10, tests 10, backend_app 2, scripts 2), led by arg-type 56, union-attr 16 and attr-defined 15.
Quality baseline check passed.
```

`git diff --check -- docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md` — exit 0, no output. The plan is untracked (`??`), so this command does not inspect its content. Direct plan scan found `packet_rows=36; packet_unique=36; self_rows=36; self_unique=36`, exact T00–T35 sequence, zero trailing-whitespace lines, zero CR bytes, and a final newline.

## Review fix round 1

- T33 now requires behavioral proof that an edge-provided private client-IP header passes to the BFF, an absent header stays absent, and `X-Forwarded-For`/`X-Real-IP` are excluded. The SPA relay cannot establish provenance of a supplied private header. T31 owns caller-spoof overwrite and deployed direct-BFF reachability, with an actual nginx harness eligible only for overwrite proof.
- T24 keeps D2+D4 atomic and specifies exact public SPA `Origin` comparison on browser-initiated POST login/authorize, logout, and authenticated writes. The SPA proxy must preserve that header. The cross-site top-level GET callback has a narrow exception under fixed redirect URI, `HttpOnly`/`SameSite=Lax` browser-bound cookie, single-use state, nonce, and PKCE. Valid cross-site callback, invalid browser-write Origin, and replay are test requirements. The plan and ledger record the rationale and cost of the exception.
- T32 names existing `OKR_TEST_POSTGRES_URL`, CI PostgreSQL service, `pg_read_path` real HTTP data, `measure()` counters, SQLSTATE-42883 fallback and non-skipping CI. T35 names `OKR_TEST_PGBOUNCER_URL`, a transaction-mode `tests/support/pgbouncer/pgbouncer.ini`, real CI PgBouncer service/config, both actual `_create_engine` branches and non-skipping CI.
- Synchronized the ledger's conflict matrix, 36-item checklist, 36-row self-scan and T01 signoff status. Final independent plan review and T00/T01 cross-signoff remain pending; no packet is claimed merged or remote-CI closed.

Re-ran checks after the fix: `python scripts/check_docs_hq_links.py` exit 0 with `Documentation HQ link check passed (91 markdown files scanned).`; `python scripts/check_quality_gate_baseline.py` exit 0 with the exact output above; `git diff --check -- docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md .superpowers/sdd/2026-09-23-remaining-engineering-execution/progress.md` exit 0 with no output. Both paths are untracked, so direct scans are the content check. They found 36 unique contiguous IDs in the plan packet list, plan self-scan, ledger checklist and ledger self-scan; zero trailing whitespace; LF line endings; and final newlines. The ledger's seven mixed CR bytes were normalized to LF before this final result.

## Facts that remain gated

No owner decision for D3 semantics or P0-2 task visibility is inferred here. The selected IdP's client type, issuer/configuration, and boolean `email_verified` guarantee; current target provisioning counts and authorized issuer/subject backfill; external Python-token consumers; named operations owner and real-data approval remain unsupplied. Provider API/issued records, live paired rollback, deployed edge-only BFF reachability/header overwrite, target ingress/namespace/secrets/images, and real PgBouncer transaction-pooling topology and measurements remain external evidence gates. The plan claims no production enablement, remote CI, merge, or live drill from these documentation edits.
