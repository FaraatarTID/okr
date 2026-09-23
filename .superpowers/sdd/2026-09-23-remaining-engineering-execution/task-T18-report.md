Documentation HQ: [README](../../../README.md)

# T18 implementation report — isolated OIDC ID-token verifier

## Result

Implemented an isolated ID-token verifier in `spa-bff/src/oidc-token-verifier.ts`. It accepts only RS256, ES256, and PS256; selects exactly one key by `kid`, algorithm, key type, `use`, and `key_ops`; verifies the signature and configured issuer/audience; requires `sub` to contain 1–255 ASCII characters and requires `exp`, `iat`, and nonce; allows at most 60 seconds of clock tolerance; and compares nonce values using fixed-size SHA-256 digests with Node's constant-time comparison.

Audience handling supports the OIDC string form and array form. The configured client ID must match the string audience or be present in the array. Multiple audiences require `azp` to equal the configured client ID; any supplied `azp` must match. T24 does not need to assume a single-string audience.

JWKS are cached for a configured TTL capped at five minutes. Unknown-key refresh is single-flight, limited by a configured cooldown capped at one minute, and only makes one refresh attempt per verification. Fetches have an injected abort signal and a configurable timeout capped at ten seconds (three seconds by default). Empty, malformed, or oversized JWKS sets fail closed. Returned payloads are frozen and become available only after cryptographic and claim validation succeeds.

The verifier is not imported by `server.ts` or any route. No login, authorize, callback, or session endpoint was added. Issuer, audience, fetcher, clock, TTL, and cooldown remain injected; no deployment identity facts were invented. T24 still owns route integration, and D8/D9 claim-shape and email requirements remain open.

## Dependency and lockfiles

Pinned official `panva/jose` 6.2.12 exactly in `spa-bff/package.json`. npm updated both the workspace root lockfile and standalone BFF lockfile. The first sandboxed registry attempt was denied with `EACCES`; the authorized retry succeeded. npm reported zero known vulnerabilities. The follow-up standalone lockfile-only sync did not change `node_modules`.

Official API/version references checked during implementation:

- `panva/jose` remote JWKS docs: https://github.com/panva/jose/blob/main/docs/jwks/remote/functions/createRemoteJWKSet.md
- `panva/jose` JWT verify options: https://github.com/panva/jose/blob/main/docs/jwt/verify/interfaces/JWTVerifyOptions.md
- Official package metadata: https://raw.githubusercontent.com/panva/jose/main/package.json (version 6.2.12)

## Tests and verification

- TDD red: focused test initially failed because the verifier module did not exist.
- TDD red/green for fetch timeout: the test failed because the fetcher was not aborted, then passed after adding a deadline and AbortSignal.
- TDD red/green for subject and audience: the regression test first failed because a validly signed token without `sub` was accepted. It now covers missing/empty `sub`, multi-audience tokens without `azp`, wrong `azp`, and a valid array audience.
- TDD red/green for subject bounds: a generated token with 256 ASCII characters in `sub` was accepted before the fix. The updated test rejects 256 characters and non-ASCII values while accepting the 255-character boundary.
- TDD green: `npm test -- --run test/oidc-token-verifier.test.ts` — 16 passed after subject-bound validation. Generated signing fixtures cover RS256, ES256/P-256, and PS256/RSA-PSS. Cases cover malformed tokens, disallowed algorithms, invalid signatures, wrong/ambiguous/private/encryption-only keys, bounded ASCII subject, issuer/audience/`azp`, expiration/issued-at skew, nonce, JWKS cache TTL, rotation, unknown-kid refresh, concurrent refresh coalescing, fetch timeout, and TTL bounds.
- `npm run typecheck` — passed after the review fix.
- `npm run build` — passed.
- `npm test` — 13 files, 117 tests passed after the review fix.
- `npx eslint spa-bff/src/oidc-token-verifier.ts spa-bff/test/oidc-token-verifier.test.ts` — passed with no output after the review fix.
- `npm --prefix .. run lint` — zero errors; nine existing warnings were reported in SPA files, none in T18 files.
- Dependency install audit — zero vulnerabilities reported by npm.

## Review boundary / remaining work

This packet implements verifier behavior only. It does not demonstrate interoperability with a production issuer or establish production issuer/JWKS/client configuration. The injected `fetchJwks` boundary must be wired by T24 with a bounded HTTP timeout and approved issuer/JWKS configuration. Independent security review `/root/t18_review`: **PASS** after two scoped follow-ups. T24 still owns approved production issuer/JWKS configuration and route integration.
