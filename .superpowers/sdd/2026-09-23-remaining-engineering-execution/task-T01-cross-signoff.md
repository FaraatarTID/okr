Documentation HQ: [README](../../../README.md)

# T01 final baseline cross-signoff addendum — 2026-09-23

**Final verdict: PASS — T00/T01 baseline cross-signoff complete locally.** The canonical contradictions were corrected and independently approved in both `task-T00-canonical-fix-review.md` and `task-T00-canonical-fix-review-T00.md`. A fresh structural check reconfirmed all 55 T00 rows and all four 36-packet inventories. Downstream packets may proceed subject to their individual dependencies, file reservations, and owner/external gates. This accepts the baseline reconciliation; it does not claim implementation, merge, remote CI, or deployed verification.

## Resolved blocking finding and follow-up correction

The initial cross-signoff found that `docs/REMAINING_ENGINEERING_PLAN.md:474` claimed the four most recent commits covered “the OIDC flow and stateless session logout revocation.” This conflicted with that file's D2 issue and explicit **D1, D2, D5, D7 | Not started** progress row. It also overstated D3a's same-process replay correction, whose restart/cross-instance/unknown-session remainder stays open.

The register's corrected Assumptions at lines 480–485 now explicitly record absent BFF/SPA OIDC routes, D1/D2/D5/D7 not started, and D3a's limited scope. T00's round-3 correction at `task-T00-report.md:156–198` records the checkout evidence and adjudication. The ledger supersedes premature local acceptance notes at lines 100 and 149 and records the ruling at line 162. These now agree with the execution plan's baseline and T00/T01 D2 evidence. Both independent scoped reviewers approved the correction; the initial blocking verdict in this addendum is superseded.

The follow-up scoped review also resolved the unsafe D4 limiter-key instruction. Register lines 380–393, T24, the plan's integration rule, and ledger now require private `X-OKR-Client-IP`, with raw immediate socket-peer fallback when absent, excluding proxy-derived `request.ip`, XFF, and X-Real-IP. Login lockout retains its separate IP-unkeyed absent-header behavior. Future behavioral cases remain required at T24; this documentation correction does not prove a limiter exists. T31 retains deployed edge overwrite and reachability evidence.

## Reconciled portions

- T00 contains exactly **55 unique current-register rows**: 47 A–F plus P0-1 through P0-8, with no missing or extra IDs. D1/D2/D5/D7 remain not started; D3a remains a qualified subset. The canonical assumption now agrees with this reconciliation.
- The plan packet tables, plan self-consistency table, ledger checklist, and ledger self-consistency table each contain exactly **36 unique IDs in order T00–T35**. The old 32-packet count and “preserve 32” amendment in the original T01 report are historical findings superseded by the steward's explicit expansion ruling at `progress.md:147`.
- The active P0 mapping at plan lines 97–108 preserves P0-1/P0-6/P0-7 as qualified baseline history; P0-2 maps to T02; P0-3 to T32; P0-4 to T33 plus T31 deployed proof; P0-5 to T34; and P0-8 to T35. The canonical status instructions at register lines 436–440 now preserve the distinct historical P0-00…P0-06 namespace.
- The plan and ledger conflict matrices now reserve concrete shared read/security, session/schema, workflow, frontend, typing, lockfile, and pooler lanes. Exact file reservation remains a per-packet pre-dispatch obligation. T32 follows T02/T03; T33 precedes T24; T35 follows T32; T34 retains its identity-design/customer-gate dependencies.
- T19 now requires current target recount and provisioning/linking authorization before production integration implementation. T27 inspects the existing strict `--record` path before proposing code. T00 B5 distinguishes today's `migration-quality` step from the historical job name. These address the original T01 timing, workflow, and status-routing findings.
- T24 remains the indivisible D2+D4 unit after D1 and the remaining identity contracts. Its browser-write Origin policy and narrowly validated cross-site callback exception are explicit. T33 claims only SPA relay behavior; actual private-header overwrite and deployed direct-BFF reachability remain T31 evidence.

## Owner and external gates retained

The plan explicitly blocks T06 while genuine fresh/clean clones are unavailable; T19 production integration without target facts and authorized provisioning; T20 production login without the selected IdP claim guarantee; T23 without T22 owner approval; T25 without customer requirement and owner; T28–T31 and live E3 rehearsal without provider/target/ingress/owner facts. T16 engine changes require observed image/CI runtime. T32/T35 require real non-skipping PostgreSQL/PgBouncer evidence, with pooling default unchanged absent proof. Local file presence and fixtures do not satisfy these gates. T24 cannot bypass the upstream identity gates.

## Minor retained for T27 and final review

`progress.md:150` now records the E3 reviewer minor in the required deferred-minor form:

> Task 0: minor (deferred): T00 report calls E3 code remainder open although the strict `--record` workflow exists; T27 must identify a concrete code gap before changes — risk of overstating work.

This minor remains deferred, bounded by T27's explicit inspect-first contract; it is not silently resolved. The coordinator may now record this final local cross-signoff in the ledger. Canonical `IMPLEMENTED`/`VERIFIED` claims still require the register's integration, CI, and drill evidence.

## Inspection evidence and limits

Read the current plan, canonical register (including its trailing assumptions), T00 report, prior T01 audit, progress ledger, and both final scoped review artifacts. The original structural check reported `T00 rows 55 unique 55 missing [] extra []`; its subsequent Unicode source-print step failed under the Windows default console encoding and was repeated with UTF-8 output. After the corrections, a fresh assertion-based structural check exited 0: T00 has 55 unique expected rows; plan packet tables/self-scan and ledger checklist/self-scan each have 36 unique contiguous ordered T00–T35 IDs; the exact deferred-minor entry exists. Both scoped reviews are PASS, with no Critical/Important findings; one independently reran docs HQ, quality baseline, scoped whitespace, and structural checks successfully. No behavioral tests, Git writes, source edits, provider operations, or remote queries were performed for this cross-signoff. Only this addendum was written.
