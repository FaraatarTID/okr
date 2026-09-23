Documentation HQ: [README](../../../README.md)

# T18 implementation snapshot

- `spa-bff/src/oidc-token-verifier.ts`: isolated verifier module; no route wiring.
- `spa-bff/test/oidc-token-verifier.test.ts`: 16 focused tests with generated RS256, ES256/P-256, and PS256/RSA-PSS keys; includes 1–255 ASCII `sub` and string/array audience plus `azp` validation.
- `spa-bff/package.json`: exact `jose` 6.2.12 runtime dependency.
- `package-lock.json` and `spa-bff/package-lock.json`: npm-generated dependency records.
- Report: `task-T18-report.md`.

No production issuer, client ID, JWKS URI, redirect URI, or public origin is embedded. T24 owns route integration after deployment configuration and D8/D9 requirements are settled.
