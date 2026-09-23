Documentation HQ: [README](../../../README.md)

# T00 canonical correction — independent scoped review

Verdict: **PASS**

Reviewed on 2026-09-23. No Critical or Important findings in the requested correction scope. This accepts the documentation correction, not implementation of D4 or completion of the remaining engineering work. The coordinator still owns the final T00/T01 cross-signoff entry.

## Findings verified

1. **OIDC baseline and D3a:** `docs/REMAINING_ENGINEERING_PLAN.md:478-485` now states that OIDC authorize/callback routes are absent and D1/D2/D5/D7 are not started. Inspection of `spa-bff/src/server.ts` found only `/session/login`, `/session/me`, and `/session/logout`; the SPA session directory contains their three corresponding passthroughs. `git log -4` agrees with the correction report's commit list. The Assumptions paragraph, D3a progress row, execution-plan preface, and T00 report all preserve the same-process-only boundary and leave restart, cross-instance, and unknown-session revocation open.
2. **Limiter trust contract:** the canonical D4 implementation note at `docs/REMAINING_ENGINEERING_PLAN.md:380-393`, execution-plan T24 row at line 72, integration rule, and ledger T24 self-scan consistently select private `X-OKR-Client-IP`, with raw immediate socket peer fallback only when absent. They explicitly exclude proxy-derived `request.ip`, XFF, and X-Real-IP. This matches the different throughput-limiter and login-lockout failure directions in `docs/client-ip-trust-adr.md:38-63`; the absent-header login lockout stays IP-unkeyed. The existing `trustProxy: true` setting was independently located in `spa-bff/src/server.ts:243`.
3. **Concrete acceptance cases:** T24 requires trusted-header presence, conflicting caller-supplied public forwarding headers, and absent-header aggregate-peer behavior. The canonical D4 acceptance row at line 109 supplies the third-request/limit-two 429 test and `Retry-After` requirement. The canonical correction report explicitly carries these cases and the distinct absent-header lockout case. The plan keeps canonical acceptance criteria binding. These are future behavioral requirements; no claim that the limiter already exists is made.
4. **Prior accepted scope retained:** T33 still proves forwarding/absence and exclusion of both public forwarding alternatives without claiming private-header provenance. T31 retains actual edge overwrite and deployed reachability proof. T24 retains browser Origin propagation, exact comparison on browser writes, and the constrained cross-site GET callback exception with fixed redirect, HttpOnly/Lax transaction cookie, state, nonce, and PKCE. T32 and T35 still specify real PostgreSQL/PgBouncer DSNs, request/counter harnesses, non-skipping CI, and real engine branches. The P0 mapping and T19/T27 decision boundaries remain intact.
5. **Ledger accounting:** earlier T00 local completion notes are explicitly superseded and the checklist remains unchecked pending cross-signoff. Both new decisions use the required `Ruling: ... — why — cost if wrong` structure. The exact deferred E3 minor appears at `progress.md:150` and is bounded by T27's inspection-first requirement. No additional minor finding is introduced by this review. Historical review-round wording is contextualized by the explicit supersession and pending-cross-signoff statements.

## Fresh verification

- `python scripts/check_docs_hq_links.py`: exit 0; 91 markdown files scanned.
- `python scripts/check_quality_gate_baseline.py`: exit 0; QG-002 expiry remains 2026-11-15.
- `git diff --check -- docs/REMAINING_ENGINEERING_PLAN.md`: exit 0, no output.
- Direct structural scan: execution-plan packet table and self-scan, plus ledger checklist and self-scan, each contain exactly T00 through T35, 36 unique contiguous IDs.
- Direct UTF-8/whitespace scan of the canonical register, execution plan, T00 report, and progress ledger: final LF, no CR bytes, no trailing whitespace.

The first ad hoc count command accidentally included a T06 conflict-matrix row in the self-scan count. Restricting the parser to the named self-scan section resolved that inspection-script error; no source change was needed. No behavioral tests were run for this documentation-only review. No source artifacts were edited, no Git writes were attempted, and no remote CI or deployment evidence is claimed.
