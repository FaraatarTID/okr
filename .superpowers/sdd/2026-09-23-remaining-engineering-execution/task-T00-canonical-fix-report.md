Documentation HQ: [README](../../../README.md)

# T00 canonical contradiction fix — 2026-09-23

## Scope and evidence

The register's Assumptions paragraph claimed that the four latest commits
included an OIDC flow and stateless logout revocation. Current `git log -4`
instead lists `0c29741`, `7dc7403`, `52102c2`, and `c086e55` (docs/status and
test changes). `spa-bff/src/server.ts` has only login/me/logout session routes;
`spa-web/src/app/api/session/` has only matching passthroughs. The register's
D2 row and Phase 3 progress row say D1/D2/D5/D7 are not started. D3a covers
same-process replay only, with restart, cross-instance, and unknown-session
revocation still open. The Assumptions paragraph now states that checkout
boundary and preserves B7's historical worklog/working-tree disposition and
the requirement to commit or park current work.

The D4 implementation note also proposed `request.ip` because
`trustProxy: true` is enabled. `docs/client-ip-trust-adr.md:38-63` instead
settles on the edge-overwritten private `X-OKR-Client-IP`; absent it, a
throughput limiter uses the raw immediate peer as an aggregate fallback.
XFF and X-Real-IP never supply a trusted client key, and the login lockout
remains IP-unkeyed when the private header is absent. The canonical D4 note,
T24 packet, plan decision rule, and plan/ledger self-scans now bind that
contract. T31 retains actual edge overwrite and deployed reachability proof.

The T00 reconciliation report records both findings and their corrections.
The progress ledger has two `Ruling: ... — why — cost if wrong` entries,
explicitly supersedes the older local T00 completion notes, and carries the
exact deferred E3 minor requested in the T01 cross-signoff addendum.

## Checks and required implementation evidence

- `python scripts/check_docs_hq_links.py`: pass, 91 markdown files scanned.
- `python scripts/check_quality_gate_baseline.py`: pass; QG-002 expiry is 2026-11-15.
- `git diff --check -- docs/REMAINING_ENGINEERING_PLAN.md`: pass, no output.
- UTF-8 format scan of the canonical register, execution plan, T00 report,
  and progress ledger: final LF, no CR bytes, no trailing whitespace.
- Markdown fences in the edited report and register were inspected with
  `rg -n '^```'`; the edited plan and ledger have none.

No application code or behavioral tests were changed in this correction.
T24 must test the BFF limiter with an edge-provided private header, conflicting
caller-supplied XFF/X-Real-IP, no private header with raw-peer aggregate
fallback, and a third request returning 429 under a limit of two. It must
retain separate login-lockout absent-header behavior. T33 tests the SPA relay;
T31 supplies actual edge overwrite and deployed reachability evidence.

T00/T01 cross-signoff remains pending scoped independent review. No Git writes,
downstream implementation, remote CI, or deployment verification are claimed.
