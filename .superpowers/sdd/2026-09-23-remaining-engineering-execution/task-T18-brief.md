Documentation HQ: [README](../../../README.md)

# T18 — ID-token verification gate

Status: READY for isolated verifier implementation. T06 is complete and its three-file Fastify repair is integrated and independently reviewed. T18 may add the audited JOSE dependency in its own serialized npm pass; no other packet may edit npm lockfiles concurrently.

## Authority and purpose

Follow `docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md` T18 and canonical register D1. Verify an OIDC ID token cryptographically before trusting any claims. Do not create or expose login, authorize, callback, or session-minting routes in T18. Route exposure is owned by T24, which couples D2 and D4.

## Hard prerequisites

1. T06 selects a supported Fastify resolution after checking the current vendor advisory, regenerates npm lockfiles with npm from a genuine fresh clone, and passes its clean-clone validation.
2. The audited JOSE package and its lockfile addition are then applied by the serialized dependency steward. Do not race T06 or hand-edit lockfiles.
3. Production issuer, JWKS URI, client ID/audience, redirect URI, SPA public origin, and secret/config ownership are not currently established. T18 may use deterministic generated signing fixtures for isolated verifier tests; it must not invent production values or claim production integration.
4. D8/D9 identity-shape and verified-email requirements remain independently gated; T18 validates claims only and does not mint application sessions.

## Allowed implementation boundary after prerequisites

- Prefer a standalone `spa-bff/src/oidc-token-verifier.ts` module plus a focused adjacent test, subject to existing conventions and exact dependency/API choice.
- Use an audited JOSE library; do not implement cryptographic primitives.
- Keep untrusted decoded payloads unavailable to callers until signature and all required checks pass.
- Keep the verifier injectable/configurable for test issuer, audience, JWKS source/cache behavior without embedding deployment secrets or endpoints.
- Do not edit `spa-bff/src/server.ts`, session formats, route policy, generated API artifacts, or SPA routes. T24 owns public-route integration.

## Acceptance criteria

- Select JWKS keys by `kid` and compatible key/use/algorithm; accept only RS256, ES256, or PS256.
- Reject `none`, every HS* algorithm, unsupported algorithms, malformed tokens, wrong key types, invalid signatures, and ambiguous/unknown keys.
- Require exact configured issuer and audience; validate expiry and issued-at with no more than the specified 60-second skew and reject future-issued or expired claims outside it.
- Compare nonce in constant time; missing/mismatched nonce fails closed.
- Cache JWKS for a bounded TTL. On unknown `kid`, perform exactly one bounded refresh; prevent unbounded network retries and concurrent refresh amplification.
- Include deterministic generated RSA and P-256 fixtures and targeted PS256 coverage where supported; test key rotation/unknown-kid refresh, cache hit/expiry, all rejection classes, and positive controls.
- Focused tests, BFF typecheck/lint, and security review pass. No route becomes reachable as part of T18.

## Stop conditions

If T06 cannot meet its genuine fresh-clone requirement due network, permission, vendor, or reproducible npm resolution constraints, leave implementation blocked and record exact outputs. Do not mutate current-checkout package/lock files as a workaround. If actual issuer/audience facts remain unavailable, complete only isolated verifier behavior and leave production integration to T24.

## Dependency and library references

The official `panva/jose` documentation describes `createRemoteJWKSet` key selection by `alg`, `kid`, `use`, and `key_ops`, JWKS refresh cooldown and cache max age; `jwtVerify` exposes algorithm allowlists, issuer/audience, clock tolerance, and required claims. Confirm the exact compatible release at implementation time and lock it through npm. References: `https://github.com/panva/jose/blob/main/docs/jwks/remote/functions/createRemoteJWKSet.md`; `https://github.com/panva/jose/blob/main/docs/jwt/verify/interfaces/JWTVerifyOptions.md`.