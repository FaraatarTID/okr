Documentation HQ: [README](../../../README.md)

# T18 independent security review

Reviewer: `/root/t18_review`

**Verdict: PASS** after two scoped follow-ups. Initial review found missing required `sub`; the first follow-up added non-empty `sub` and standard array-audience/`azp` handling. Final review found and closed the OIDC `sub` bound: accepted values are 1–255 ASCII characters. Generated-key tests reject missing, empty, 256-character, and non-ASCII subjects, and accept the 255-character boundary. Audience tests cover string and array forms, `azp` requirements, and mismatch rejection.

Independent checks: 16 focused verifier tests, BFF typecheck, and scoped ESLint passed. No verifier route or session integration was found. T24 still owns production issuer/JWKS configuration and route integration.
