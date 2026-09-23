# T33 brief — SPA-to-BFF private client-IP boundary

## Objective

Add behavioral tests around `proxyToBff` in `spa-web/src/lib/bff-proxy.test.ts` proving that the SPA relay forwards `X-OKR-Client-IP` when present, leaves it absent when absent, and excludes caller-supplied `X-Forwarded-For` and `X-Real-IP`.

## Scope

- Edit only `spa-web/src/lib/bff-proxy.test.ts` for implementation.
- Exercise the real `proxyToBff` function and inspect headers passed to the mocked upstream fetch.
- Preserve existing production code, client-IP ADR, and later-boundary tests.

## Limits

The SPA relay sees only the incoming request and cannot prove whether `X-OKR-Client-IP` originated at the trusted edge or was supplied by a caller. These tests establish relay behavior only. T31 owns edge overwrite and direct-BFF reachability proof.
