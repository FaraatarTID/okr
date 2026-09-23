# T33 snapshot

Implementation snapshot: `spa-web/src/lib/bff-proxy.test.ts`

The test helper now accepts additional incoming headers. Three cases observe the actual headers passed to the mocked upstream `fetch` call: private header forwarded when present, absent header remains absent, and XFF/X-Real-IP are excluded even when the incoming request contains them.

Verification snapshot: focused Vitest file passed (8 tests); SPA TypeScript typecheck passed. No lint executable/script was configured. See `task-T33-report.md` for limitations and edge-proof ownership.
