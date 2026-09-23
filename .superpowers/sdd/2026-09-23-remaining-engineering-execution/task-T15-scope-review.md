# T15 / C6 scope reconciliation review

**Verdict: PASS**

## Findings

- The canonical register and execution plan consistently distinguish routes from rendered states. C6 lists `alignment` and `RTL` as user surfaces, then explicitly says they are not routes; T15 requires actual route-specific UI for route flows and rendered alignment/RTL states for the other surfaces. No `/alignment` or `/rtl` path is invented.
- This matches the current app. The shell owns actual paths `/`, `/admin`, `/check-in`, `/daily`, `/dashboard`, `/retrobox`, `/timeline`, and `/weekly` (`spa-web/src/app/(shell)/layout.tsx` and `route-ownership.test.ts`). The alignment controls are rendered by `InspectorAlignmentPanel`, mounted from `AtlasShell`; RTL is produced by `rtlStyle` for text rendered in Inspector panels (`InspectorEditAnalysisPanel.tsx`, `InspectorTaskWorkHistoryPanel.tsx`, and `lib/rtl.ts`).
- Role and isolation criteria remain explicit in both documents: run role-parameterized flows, deny admin-only surfaces to managers and members, and isolate test data per run. This matches the existing E2E role fixture and its temporary SQLite database under `tmp_path_factory` (`tests/test_e2e_playwright_spa_login_to_atlas.py`).
- The reconciliation changes scope wording only. C6 remains `Not started` in the authoritative register's Phase 2 remainder, and the reconciliation record explicitly leaves T15 open pending T12's access review. No implementation status was upgraded.

## Implementer note

When T15 is briefed, translate “appropriate role” into a route/surface-to-role matrix and assert denied access through the UI boundary, not only the absence of the Admin navigation button. This is an implementation detail to make the stated acceptance executable; it does not block the scope reconciliation.

## Review limits

This was a read-only scope review. I did not run the opt-in browser E2E suite or change code, status, or planning documents.
