# T17 — Independent review

## Verdict: PASS

Reviewed the T17 implementation against `task-T17-brief.md` and the D6-1 acceptance criteria. No implementation or shared-ledger files were changed during this review.

## Findings

- **Production caller search: PASS.** Searched the full checkout (excluding only `.venv` and `node_modules`) for `issue_app_session_token`, `verify_app_session_token`, and `oidc-session-v1`. The only Python occurrences are the definitions in `src/saas/identity_contract.py`; production Python caller scope `src`, `backend_app`, and `scripts` contains no calls. Other hits are tests, the new BFF test, or documentation/history. This is an in-repository result only; it does not inventory deployed services, jobs, integrations, or downstream packages.
- **Deprecation and compatibility: PASS.** Both Python method docstrings explicitly call the methods deprecated and non-authoritative, identify the SPA BFF as the only supported session minter/verifier, and retain the methods pending external consumer inventory. The implementation diff changes only docstrings. The `oidc-session-v1` tag, flat claims, compact sorted JSON serialization, and HMAC-SHA256 formula remain intact. Neither method was deleted.
- **Python-token rejection: PASS.** The BFF test uses the flat Python-format payload with sorted keys, compact JSON, base64url encoding, and a valid SHA-256 HMAC using the shared test secret. It asserts the BFF verifier returns `null` for the well-formed, unexpired token.
- **Native BFF positive control: PASS.** Existing adjacent coverage still issues and verifies a native BFF `v1` session token.
- **Deletion gate: PASS.** The report correctly leaves D6-4 open and requires an application/deployment-owner inventory of external consumers before deletion. It makes no claim of complete external inventory.

## Verification run

- `.venv\Scripts\python.exe -m pytest tests/test_saas_identity_contract.py -q` — **13 passed**.
- `npm test -- test/session.test.ts` in `spa-bff` — **9 passed**.
- `npm run typecheck` in `spa-bff` — **passed**.

## Scope limit

The repository search cannot establish whether external or deployed consumers exist. D6-4 deletion remains externally gated, as the implementation report states.
