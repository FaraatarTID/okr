# T33 report — SPA-to-BFF private client-IP boundary

## Result

Added three behavioral tests to `spa-web/src/lib/bff-proxy.test.ts`. They execute `proxyToBff` with an upstream-fetch spy and inspect the actual outgoing request headers:

- present `x-okr-client-ip` is forwarded;
- absent `x-okr-client-ip` remains absent;
- caller-supplied `x-forwarded-for` and `x-real-ip` are not forwarded, while the private header is forwarded.

The request helper accepts additional headers for these cases. No production code, workflow, package manifest, lockfile, SPA E2E test, or canonical register was changed.

## Verification

- `npm test -- --run src/lib/bff-proxy.test.ts` — passed, 8 tests.
- `npm run typecheck` — passed.
- No SPA lint script or local ESLint executable is configured, so lint was unavailable.
- Vitest emitted the existing Vite `configLoader: 'native'` compatibility warning; all focused tests passed.

## Boundary and remaining evidence

The relay cannot distinguish an edge-provided private header from a caller-supplied one; forwarding a present private header is not proof of spoof rejection. T31 must still prove the edge overwrites caller input and the BFF cannot be reached directly. Existing BFF and backend IP-trust tests remain unchanged.
