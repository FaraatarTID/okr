import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { defineConfig } from "vitest/config";

const rootDir = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  oxc: {
    jsx: { runtime: "automatic" },
  },
  test: {
    environment: "happy-dom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    // The VM-thread pool leaks mocked module instances between files with this
    // suite's shared hook mocks. Use fork isolation so each test file gets a
    // fresh module registry on the single-worker CI runner.
    pool: "forks",
    maxWorkers: 1,
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      reportsDirectory: "./coverage",
      // `src/lib` is included so the shared cache modules added for C1 are
      // gate-enforced. Measured on 2026-09-20 this is 67.5% statements and 53.8%
      // branches against a 25/20 floor, so the whole of `src/lib` fits without
      // threatening the gate, and a module added tomorrow is covered by default
      // rather than only after someone remembers to widen this list.
      include: [
        "src/components/atlas-shell/**/*.ts",
        "src/components/atlas-shell/**/*.tsx",
        "src/lib/**/*.ts",
      ],
      exclude: ["**/*.test.ts", "**/*.test.tsx"],
      thresholds: {
        statements: 25,
        branches: 20,
        functions: 25,
        lines: 25,
      },
    },
  },
  resolve: {
    alias: {
      "@": resolve(rootDir, "src"),
    },
  },
});
