import { configDefaults, defineConfig } from "vitest/config";

// The 3.x line excluded build output, tool config files and editor/cache
// directories from test discovery by default. The 4.x line reduced the default
// exclude to only `**/node_modules/**` and `**/.git/**`
// (see https://v4.vitest.dev/guide/migration, "Simplified exclude"), and this
// package moved 3.x -> 5.x, so it silently inherited the smaller list.
//
// That mattered here because `tsconfig.json` used to compile `test/**/*.ts`
// into `dist/test/`. Any tree with a build present therefore collected every
// test twice — once from source and once from the stale compiled copy — and the
// duplicated Fastify servers pushed the slowest test past its 5s budget. CI
// escaped only because `SPA BFF tests` runs before `SPA BFF build`.
//
// `tsconfig.build.json` now keeps tests out of `dist/` entirely, so the
// duplication cannot recur. This list restores the documented pre-4.x
// behaviour as well, so correctness does not depend on build ordering either.
export default defineConfig({
  test: {
    exclude: [
      ...configDefaults.exclude,
      "**/dist/**",
      "**/cypress/**",
      "**/.{idea,git,cache,output,temp}/**",
      "**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build,eslint,prettier}.config.*",
    ],
  },
});
