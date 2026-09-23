Documentation HQ: [README](../../../README.md)

# T17 — Single session authority

## Objective

Implement D6-1: the BFF is the only supported session minter and verifier. Search
the repository for Python-format consumers, deprecate the Python issuer/verifier
as non-authoritative, and prove the BFF rejects a correctly signed Python-format
token. Preserve the Python pair until an external-consumer search proves
D6-4 deletion is safe; a repository-only search is not proof about consumers
outside this checkout.

## Exact ownership

- `src/saas/identity_contract.py` (deprecation documentation only; preserve
  current format/signature behavior unless test evidence requires otherwise)
- `tests/test_saas_identity_contract.py`
- `spa-bff/test/session.test.ts`
- T17 report/snapshot/review artifacts under this SDD directory.

Do not edit `spa-bff/src/session.ts` unless the current BFF rejection behavior
fails the required test, and then first report the exact mismatch. Do not edit
T14 password-change files, T15 E2E routes, generated contracts, D1/D2/D3/D4
production code, or the shared ledger.

## Acceptance

- Repository search finds no production caller of the Python issuer/verifier;
  document the search scope and exact external-consumer deletion gate.
- Mark both Python functions clearly deprecated and non-authoritative without
  deleting the recorded `oidc-session-v1` compatibility formula.
- Add a test that creates a well-formed Python-format token with a valid HMAC
  under the test secret and asserts the BFF verifier rejects it. Retain positive
  control coverage for native BFF session tokens.
- Run focused Python/BFF tests; run BFF typecheck if test/source typing changes.
- Do not claim D6-4 complete or infer an external consumer inventory.

## Workflow

Use test-first changes, keep Python compatibility separate from BFF session
authority, preserve user work, and report external gates explicitly. `.git` is
read-only; no branches, worktrees, index writes, or commits.
