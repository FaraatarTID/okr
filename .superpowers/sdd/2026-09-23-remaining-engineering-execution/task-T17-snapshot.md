Documentation HQ: [README](../../../README.md)

# T17 evidence snapshot

Date: 2026-09-23

## Scope searched

Command: `rg -n "issue_app_session_token|verify_app_session_token" --glob '!**/node_modules/**' --glob '!**/.venv/**' .`

In-checkout matches: method definitions in `src/saas/identity_contract.py`,
compatibility tests in `tests/test_saas_identity_contract.py`, and plan/history
documentation. No production call sites appear. The production directories
checked are `src`, `backend_app`, and `scripts`. Search does not cover deployed
environments or consumers outside this checkout.

## Compatibility token shape retained

The issuer still emits `oidc-session-v1` with its existing flat claim set,
compact JSON serialization using sorted keys, base64url payload, and
hexadecimal HMAC-SHA256 signature over the encoded payload. The verifier's
runtime checks are unchanged. Only method documentation changed to state that
this pair is deprecated and non-authoritative.

## BFF authority test

`spa-bff/test/session.test.ts` creates the Python shape with
`v: "oidc-session-v1"`, a future expiry, base64url-encodes the compact JSON,
and computes `createHmac("sha256", "session-secret").update(payloadB64)`.
`verifySessionToken` returns `null` despite the valid signature. The existing
native BFF token test continues to assert successful verification.

## External gate

No external consumer inventory was available in this task. Retain the Python
pair until the application/deployment owner confirms that no external service,
job, integration, or downstream package depends on `oidc-session-v1`. This is
the prerequisite for D6-4 deletion; repository search alone does not satisfy
it.
