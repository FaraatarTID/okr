import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { defineConfig } from "vitest/config";

const rootDir = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  test: {
    environment: "happy-dom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    pool: "vmThreads",
    maxWorkers: 1,
  },
  resolve: {
    alias: {
      "@": resolve(rootDir, "src"),
    },
  },
});
