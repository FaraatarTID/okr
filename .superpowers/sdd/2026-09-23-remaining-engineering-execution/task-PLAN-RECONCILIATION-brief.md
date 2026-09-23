Documentation HQ: [README](../../../README.md)

# Execution plan reconciliation brief (T01 findings)

Update only `docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md` to make it cover the active work in authoritative `docs/REMAINING_ENGINEERING_PLAN.md`; do not change application code. Follow T01 audit `.superpowers/sdd/2026-09-23-remaining-engineering-execution/task-T01-report.md`, its independent review, and `p0-scope-audit.md`. Keep README Docs HQ plan link.

## Required decisions to encode

- Expand packet count from 32 to 36 (`T00`–`T35`) so the PostgreSQL snapshot budget, SPA→BFF client-IP test, callerless identity-control disposition, and PgBouncer transaction-pooling verification are independently reviewable packets. Record this as the steward's ruling with the cost if wrong in progress ledger.
- Expand T00 and T01 reconciliation scope to include Phase 1 progress P0-1…P0-8. P0-1/P0-6/P0-7 are closed baseline history (retain evidence caveats); P0-2/P0-3/P0-5/P0-8 open; P0-4 repository-complete but deployed edge verification open.
- Map P0-2 to T02 with predicate decision before code changes; cover owner-visible and assignee-visible rows and explicit task-error behavior, do not silently drop on broad exceptions.
- Add T32 (after T02/T03): PostgreSQL `ritual.snapshot` read-path budget; non-skipping PostgreSQL fixture; measure scope resolution/statement/physical connection effects and test HTTPS RPC fallback. Do not count SQLite 500 as acceptance.
- Add T33: SPA web→BFF private client-IP boundary behavioral test, before T24's IP-keyed limiter. Preserve the client-IP trust ADR; test approved forwarding and rejection of caller-controlled forwarding headers.
- Add T34 after T22/T23/T25: P0-5 disposition of only `revokeSessionsForIdentity` and `src/saas/identity_ports.py`; either prove a real production path and behavioral coverage if selected identity design needs it, or remove/relabel inert controls; do not reopen P0-6/D3a or expand customer features.
- Add T35 after T32: verify `OKR_DB_USE_NULL_POOL=true` only changes after a real PgBouncer transaction-pooling harness measures both NullPool/default and QueuePool opt-in. Require topology-backed before/after budget and behavior evidence; keep default true when unavailable. Do not fold this into frontend T13.
- T31 additionally owns P0-4 deployed-edge reachability/overwriting evidence, gated on a real target/ingress; a local test cannot close it.
- T19 must make the target provisioning recount/invariant check a prerequisite before production integration implementation, per canonical R:113 (not only before enablement). Keep D8 migration/backfill blocked if unavailable.
- T27 first verifies the existing generic strict execution-record workflow/`--record` path. Implement only a specific remaining gap. Do not duplicate an existing route. Live paired rollback rehearsal stays externally gated.
- Correct the T00/B5 evidence wording that current `ci-result` depends on `migration-quality`, which contains the PostgREST Exposure Gate step; preserve historical job-name note as history.

## Required plan maintenance

- Update header/body count, packet list, P0→packet map, ordered waves, dependencies, acceptance rules, and README unaffected.
- Update shared conflict matrix with T05↔T13; T13↔T11/T12/T15; T16↔T11/T12/T14/T15; T23↔T19/T24/T18/T20; T26↔T19/T23 shared OpenAPI; T24/T30↔T04/T07/T13/T27 workflows; T08↔T02/T03/T19/T21/T23/T26; T09↔T02/T03/T17/T19/T23; T10↔all test/script authors; all doc packets↔one canonical register/status steward. Add new packet edges: T32↔T02/T03/T35; T33↔T24/T31 and frontend BFF proxy tests; T34↔T22/T23/T25; T35↔T32/T13/CI topology. Assign one owner and integrate shared files serially.
- Add one self-consistency row for each new packet and verify all packet IDs unique/contiguous. Adjust preflight instructions to require P0 mapping and validate per-packet self-consistency.
- Fix plan narrative that the decision is “preserving 32” — now count is 36.
- Revise final acceptance to include P0-3, P0-4, P0-8 evidence and P0-2/P0-5 disposition while preserving external proof gates.
- Use concrete files/tests from T01 report and `p0-scope-audit.md`. Do not invent owner/provider decisions or enable claims. Run `python scripts/check_docs_hq_links.py`, `python scripts/check_quality_gate_baseline.py`, and `git diff --check` on the plan. Record exact outputs.

`.git` is read-only and `just`/Bash launchers denied; do not attempt commits, branch/worktree or helper scripts. Work serially in this current checkout. Write a report to `.superpowers/sdd/2026-09-23-remaining-engineering-execution/task-PLAN-RECONCILIATION-report.md` listing edited sections, task count, checks, and blocked facts. No subagents.
