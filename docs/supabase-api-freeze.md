# supabase_api mode is frozen

Documentation HQ: [README](../README.md)

Status: `IN FORCE` from 2026-09-29. Whether to deprecate the mode is a separate decision that
is **not** made here and is deliberately deferred (see *Decision still open*).

## The rule

No new read kind and no new mutation function may be added to `supabase_api` mode
(`OKR_DATA_ACCESS_MODE=supabase_api`, the HTTPS-to-Supabase path).

`supabase_api` is an alpha/on-premise compatibility mode. The SaaS target is
`OKR_DEPLOYMENT_PROFILE=single_tenant_saas` with `OKR_DATA_ACCESS_MODE=database`
([runtime-entrypoint-contract.md](runtime-entrypoint-contract.md)). Every capability added to the
mode has to be written twice, once against the database and once over HTTPS, and the two paths
have already diverged: the deployed enum labels are uppercase while the local ORM expects
lowercase, and several scope and authentication checks exist in two implementations.

## What is enforced

`tests/test_supabase_api_freeze.py` reads the mode's source with `ast` and compares it with
`tests/supabase_api_freeze_baseline.json`:

- every `*_via_supabase_api` function under `src/services/supabase_api_mode*.py` (31 today);
- every read kind `read_query_via_supabase_api` dispatches on (25 today);
- every read kind named in the routing tables of `backend_app/read_query_helpers.py`, which must
  not go beyond the frozen set.

It fails on an **addition**. It also fails on a **removal** that is not reflected in the baseline,
so the baseline only ever shrinks as the mode is retired.

## What a new feature does instead

Implement it for the `database` path only, and make the HTTPS path refuse it explicitly rather than
omit it, so an operator on `supabase_api` gets a clear error and not a silent gap.

## Changing the baseline on purpose

- **Retiring** something: delete its entry from the baseline in the same change that deletes the code.
- **Adding** something: not permitted by this rule. If a real need appears, that is the moment to make the
  deprecation decision below, not to edit the baseline. A reviewer should treat a baseline edit that
  adds an entry as a request to reopen this document.

## What this does not do

- It does not stop **changes** to existing functions; bug fixes and security fixes stay allowed.
- It inspects names, not behaviour. A new branch inside an existing function that adds a
  capability would not be seen.
- It scans `src/services/supabase_api_mode*.py` only. A new module outside that glob would not be
  scanned, and the routing-table check is the only cover for it.

## Decision still open: deprecate the mode?

Not decided, on purpose. It needs input from the people who run the mode, and this repository
cannot answer it:

1. Which deployments still set `OKR_DATA_ACCESS_MODE=supabase_api`, and can they move to `database`?
2. Is there a date after which the compatibility baseline in `deploy/docker` is no longer supported?
3. What is the migration path for data that lives in Supabase today?

Until those are answered, the freeze keeps the cost from growing without removing anything.
