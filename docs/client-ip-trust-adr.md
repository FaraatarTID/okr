# ADR: Client IP Trust for Rate Limiting and Login Throttling

Documentation HQ: [README](../README.md)

Status: `APPLIED` in-repository for P0-4 — the decision below is settled and is not reopened —
implemented at `8820e5d`, `3034cdd`, and `cfcd513`. The deployed network path is **not verified**,
and one in-repository test gap remains; both are recorded under *Verification status*.

## Context

Two controls key on the client IP:

- the request rate limiter, keyed `ip:<client_ip>` (`backend_app/security.py:226`);
- the login lockout, keyed `(scope="ip", identifier)` in `src/crud_auth_helpers.py`.

The address was derived, at the time of this decision, in `backend_app/security.py`: the immediate
peer (`request.client.host`), upgraded to `X-Forwarded-For`[0] when a service token is valid. That
derivation has since been replaced by the decision below; it is described here because it is the
state the decision was made against.

Every part of that is wrong for the job:

- **`X-Forwarded-For`[0] is the leftmost hop, and it is caller-controlled.** `deploy/nginx.conf:16`
  uses `$proxy_add_x_forwarded_for`, which *appends* to whatever the client sent, so a caller can
  prepend an arbitrary address. Honouring it would let a caller rotate the rate-limit key per
  request, i.e. remove the limit while appearing to enforce it.
- **The immediate peer is the BFF.** When the header is absent the key is the BFF container's
  address, so every user shares one bucket and a single attacker can exhaust it for everyone.
- **No client address arrives at all on the real path.** `spa-web/src/lib/bff-proxy.ts` forwards a
  fixed allowlist that omits both `x-forwarded-for` and `x-real-ip`, so the BFF has nothing to pass on.
- **`spa-bff/src/server.ts` sets `trustProxy: true`**, which trusts every hop, and `request.ip` is
  never read anywhere.

P0-6 removed a caller-supplied `client_ip` field from the login body, which was a
denial-of-service primitive. That fix deliberately left the IP dimension unkeyed rather than key
it on any of the addresses above, so this decision is what unblocks it.

## Decision

Introduce one application-private header, `X-OKR-Client-IP`, that is **overwritten** at every hop,
written only by components this repository controls, and read by the backend **only** when the
request is authenticated as originating from the BFF.

The rule set, in full:

1. **Overwrite, never append.** Each hop that sets the header replaces any existing value. Appending
   is what made `X-Forwarded-For` unusable, and it is impossible to get wrong if no hop appends.
2. **Written only by our edge and internal components.** `deploy/nginx.conf` sets it from
   `$remote_addr`; the SPA's server-side boundary forwards it; the BFF forwards it. Nothing else sets it.
3. **Read only under service-token authentication.** The backend ignores the header unless
   `service_token_valid`, so a caller able to reach the backend directly cannot forge it. This gate
   is load-bearing, not decorative.
4. **`X-Forwarded-For` and `X-Real-IP` are not trusted anywhere.** Neither may key a control. They may
   be logged for diagnostics only.
5. **An absent header means no IP key - for the login lockout.** A shared bucket would lock out every
   user, so the lockout stays unkeyed and relies on its per-user dimension. It must never fall back
   to the peer address or to `X-Forwarded-For`.
6. **The rate limiter falls back to the peer, deliberately.** With no trusted address it degrades to
   an aggregate limit over the proxy: undesirable, but still a limit, whereas dropping the key
   entirely would drop the control. The two controls reach opposite conclusions from the same missing
   input because their failure directions differ - a throughput control may degrade to aggregate; an
   account-lockout control must not degrade to shared. An earlier draft of this ADR stated one rule
   for both and was wrong.

## Rejected alternatives

**Rightmost-hop selection on `X-Forwarded-For`.** Correct only if the number of appending proxies is
known. With a single nginx it works; add any hop and the rightmost entry is that hop's view rather
than the client's.

**`trustProxy` with configured CIDRs and right-to-left selection.** The general form of the above,
and correct in principle, but it makes the trust property depend on deployment topology this
repository does not pin — and under Kubernetes those are dynamic pod addresses. A CIDR list that
drifts is a configuration that can silently fail open.

**Relaying `X-Real-IP` alone.** Strictly better than `X-Forwarded-For`, because `deploy/nginx.conf:15`
uses `X-Real-IP $remote_addr`, which *overwrites*. But it is still a standard header, and being
standard is what makes it subject to rewriting by intermediaries and CDNs outside our control. Kept
as the fallback only if a private header proves infeasible in the deployed edge configuration.

## Consequences

- The trust chain becomes a property of this repository rather than of the deployment, so it is
  reviewable and testable in CI.
- The backend gains a single, explicit source for the client address, replacing a derivation that
  currently has three branches and no test that distinguishes them.
- Deployments that do not set the header lose the IP dimension but keep the per-user one. That is
  the intended failure direction: a missing limiter is visible, whereas a wrong key is not.
- This ADR does not verify the deployed network path. It asserts a rule that the deployed
  configuration must satisfy, and that assertion is **not verifiable from CI**.

## Verification status

- **A fail-first test proving that a caller-supplied `X-Forwarded-For`, `X-Real-IP`, and
  `X-OKR-Client-IP` each fail to change the throttle key, and that absent-header leaves it unkeyed.**
  **Satisfied.** `tests/test_login_throttle_key.py` sends a valid service token together with
  `x-forwarded-for` and `x-real-ip` sentinels (parametrized over both) and asserts that no `ip`
  bucket is created, while asserting the account dimension still records the attempt so an
  unreached auth path cannot pass vacuously; it also covers the absent-header direction and the
  body-field direction. `tests/test_rate_limit_key_trust.py` covers the request limiter with a
  positive control — the trusted header must become the key — so a limiter that was never reached
  cannot satisfy the negative case.
- **A test that the backend ignores the private header when no service token is presented.**
  **Satisfied.** The header is read only inside the `service_token_valid` branch of
  `backend_app/security.py`, and that gate is asserted rather than assumed: the lockout's
  inert-when-untrusted direction is covered directly.
- **Confirmation, outside CI, that requests can reach the BFF only through the edge that sets the
  header.** **Outstanding.** This cannot be satisfied from CI, because it is a property of the
  deployed network path rather than of this repository. If the BFF is directly reachable, rule 3
  alone stands between a caller and a forged key. No deployment has been verified.

One in-repository gap remains, and it is a test rather than a control. `spa-web/src/lib/bff-proxy.ts`
adds `x-okr-client-ip` to the forwarded allowlist, but nothing covers that boundary:
`spa-web/src/lib/bff-proxy.test.ts` has five cases and all of them are about log redaction. The P0-4
row asked for exactly this test, so it is still owed. The BFF-side hop
(`spa-bff/test/forwarded_ip.test.ts`, three cases: the header is forwarded, it is omitted when the
edge did not set it, and `x-forwarded-for`/`x-real-ip` are ignored) and the backend-side key
derivation are both covered.
