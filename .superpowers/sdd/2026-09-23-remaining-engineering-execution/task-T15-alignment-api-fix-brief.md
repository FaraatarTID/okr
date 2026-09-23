Documentation HQ: [README](../../../README.md)

# T15 follow-up — Alignment Inspector read API defect

Status: narrowly authorized backend support fix to unblock T15's required rendered alignment E2E state. Systematic-debugging Phase 1 is complete; see `task-T15-report.md` for the exact failing traceback and same-database reproduction.

## Root cause

`backend_app/read_query_helpers.py:1247` calls `main._enum_value(...)`, but `backend_app.main` does not expose `_enum_value`. The failing request is `alignments.context`; the exact observed failure is `AttributeError: module 'backend_app.main' has no attribute '_enum_value'`. The seeded edge and `AlignmentType.SUPPORTS` value are valid. Existing code imports the helper from `src.serialization_helpers`.

## Owned files

- Production: only `backend_app/read_query_helpers.py`, importing and calling the existing `_enum_value` helper correctly.
- Regression coverage: a focused new backend test, preferably `tests/test_alignment_context_read.py` (or an existing tightly scoped read-query test if cleaner).
- Update the T15 report with this follow-up and final verification.

Do not change SPA/backend business logic, alignment permissions, generated OpenAPI, API schemas, task visibility, or `tests/test_e2e_playwright_spa_login_to_atlas.py`. T02 is editing different files. T32 has not started; finish and review this line before T32 reserves its budget path in `read_query_helpers.py`.

## Required TDD and acceptance

1. Add a behavioral regression first: create an authorized user, cycle, goal, objective, and `AlignmentEdge`; exercise the real read endpoint or `read_query_payload` with `kind="alignments.context"`; assert HTTP 200 and serialized edge `{parent_id, child_id, alignment_type: "SUPPORTS"}`. Run it and record the expected pre-fix 500/AttributeError.
2. Apply the smallest import/call correction only.
3. Re-run regression and neighboring alignment/read tests; type/lint the owned file.
4. Run the single opted-in T15 browser case `test_atlas_deep_link_and_rendered_alignment` and verify the edge actually renders. The browser test's fixture process cleanup should be checked; use only its unique ports.
5. If any broader access-control/API issue is uncovered, stop and report separately; do not bundle it into this fix.