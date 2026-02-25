Documentation HQ: [README](../README.md)

Hybrid Frontend Phase 0 Baseline Snapshot

Date
- 2026-02-25

Backlog mapping
- Work item: `HFM-000`

Source record
- Machine-readable baseline snapshot: [HYBRID_FRONTEND_PHASE0_BASELINE_2026-02-25.json](HYBRID_FRONTEND_PHASE0_BASELINE_2026-02-25.json)

## 1. Baseline Command Results

1. `python -m pytest -q`
- Result: `pass`
- Summary: `629 passed, 1 skipped in 181.19s`
- Note: full repository baseline captured after migration validation checks.

2. `OKR_RUN_PLAYWRIGHT_E2E=1 python -m pytest -q -rs tests/test_e2e_playwright_login_to_atlas.py`
- Result: `skipped`
- Summary: `1 skipped in 0.09s`
- Skip reason: Playwright package/runtime unavailable in current environment.

3. `python scripts/check_deploy_config.py --mode runtime --env-file tmp/hfm-baseline/runtime.env --secrets-file tmp/hfm-baseline/runtime.secrets.toml`
- Result: `pass`
- Summary: `Deploy config check passed (mode=runtime) with 0 warning(s).`

## 2. Acceptance Outcome

- `pytest -q` baseline recorded.
- Playwright happy-path result recorded.
- Runtime config gate pass recorded with production-style runtime profile.

Exit
- `HFM-000` acceptance criteria are met.
