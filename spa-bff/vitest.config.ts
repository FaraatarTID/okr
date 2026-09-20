import { defineConfig } from "vitest/config";

// This package previously relied on vitest's built-in defaults. The 3.x line
// excluded `**/dist/**` by default, but from the 4.x line the default list is
// only `**/node_modules/**` and `**/.git/**`. Because this package moved from
// 3.x to 5.x, the compiled tree `tsc` writes to `dist/` — which includes
// `dist/test/` — is now collected alongside the sources, so every test runs
// twice and the duplicated servers push the slowest test past its 5s budget.
// CI is unaffected only because `SPA BFF tests` happens to run before
// `SPA BFF build`; a local build-then-test run fails. Pinning the intended set
// here removes that ordering dependency.
export default defineConfig({
  test: {
    exclude: [
      "**/node_modules/**",
      "**/dist/**",
      "**/.git/**",
      "**/coverage/**",
    ],
  },
});
