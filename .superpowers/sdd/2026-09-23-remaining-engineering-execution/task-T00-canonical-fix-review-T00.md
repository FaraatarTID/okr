# T00 canonical correction — independent scoped review

Documentation HQ: [README](../../../README.md)

Date: 2026-09-23

Assessment: **PASS for the scoped canonical corrections.** Both Important findings in `task-PLAN-RECONCILIATION-review-round2.md` are resolved in the actual authoritative register, with matching report and ledger qualifications. No new Critical or Important finding was identified in this scope. This is local document acceptance, not merged/CI-closed packet status or proof of future limiter behavior.

## Findings verified

| Item | Disposition | Evidence |
| --- | --- | --- |
| Incorrect OIDC baseline, formerly register line 474 | Resolved | `docs/REMAINING_ENGINEERING_PLAN.md:480-485` now says no BFF OIDC authorize/callback routes or matching SPA passthroughs exist; D1/D2/D5/D7 remain not started; D3a covers only same-process replay, with restart, cross-instance and unknown-session revocation open. B7 history is separated from current work in progress. Actual routes in `spa-bff/src/server.ts:321,435,490` and the three files under `spa-web/src/app/api/session/` support the baseline. `spa-bff/src/session.ts:165-172` still accepts absent/unknown session IDs. |
| Unsafe D4 limiter key | Resolved as an implementation contract | `docs/REMAINING_ENGINEERING_PLAN.md:380-393` now requires private `X-OKR-Client-IP`, raw immediate socket peer only when absent, and explicitly excludes proxy-derived `request.ip`, XFF and X-Real-IP. It preserves the login lockout's separate no-IP fallback and the per-replica limit qualification. This agrees with `docs/client-ip-trust-adr.md:38-63`, current `trustProxy: true` at `spa-bff/src/server.ts:243`, and private-header forwarding at `spa-bff/src/proxy.ts:105-117`. |
| Downstream contract propagation | Consistent | Execution-plan T24 at `docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md:72`, its self-scan at `:176`, and exposure gate at `:192` use the same key rule and require presence, absence and conflicting-forwarding-header behavioral cases. D2+D4 remain indivisible behind D1. T31 at `:84` retains edge overwrite and deployed BFF reachability proof. |
| T00 report truthfulness | Consistent | `task-T00-report.md:156-198` explains both corrected contradictions and separates documentation checks from future T24 behavior and T31 deployment evidence. It leaves cross-signoff pending independent review. The cited successful checks are implementer-reported results; this reviewer did not rerun them. |
| Ledger status and rulings | Consistent | `progress.md:100,149` explicitly supersede earlier local completion/acceptance notes. The T00 checkbox remains unchecked at `:31`, and `:106,164` preserve pending final cross-signoff. Rulings at `:162-163` each contain a decision, reason and cost if wrong. Their content agrees with the corrected canonical instructions. |

## Prior T00 minor finding and exact syntax

My prior T00 review identified E3's phrase `blocked, code remainder open` as overstating an unestablished code gap. That wording is **not fixed**: it remains at `task-T00-report.md:52`. The existing strict workflow at `.github/workflows/rollback-execution-verification.yml:61-84` attaches execution data and invokes `--record`.

The issue is correctly deferred, not silently closed. `progress.md:150` reads:

> Task 0: minor (deferred): T00 report calls E3 code remainder open although the strict `--record` workflow exists; T27 must identify a concrete code gap before changes — risk of overstating work.

This matches the exact `Task <N>: minor (deferred): <one-liner>` form in the subagent-driven-development skill, line 362. Retain this minor item for final review/T27; do not describe it as resolved. The separate prior review finding about stale T00 completion notes is resolved by the explicit supersession text.

## Review boundary

Read the prior plan review, corrected register sections, report, ledger, relevant execution-plan clauses, trust ADR, and cited BFF/SPA source. No behavioral tests, documentation validators, remote CI queries, deployments, or Git writes were performed. Only this review addendum was created; no source artifact was edited. The scoped corrections are ready for the parent's final T00/T01 cross-signoff decision; this addendum does not independently close other packets or external gates.
