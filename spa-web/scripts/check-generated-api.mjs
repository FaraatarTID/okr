import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const workspaceDir = resolve(fileURLToPath(new URL("..", import.meta.url)));
const inputPath = join(workspaceDir, "src", "lib", "api", "openapi.json");
const committedPath = join(
  workspaceDir,
  "src",
  "lib",
  "api",
  "generated",
  "schema.d.ts",
);
const generatorCommand = process.platform === "win32" ? "openapi-typescript.cmd" : "openapi-typescript";

const temporaryDir = await mkdtemp(join(tmpdir(), "okr-openapi-types-") );
const generatedPath = join(temporaryDir, "schema.d.ts");

try {
  await execFileAsync(generatorCommand, [inputPath, "-o", generatedPath], {
    cwd: workspaceDir,
    shell: process.platform === "win32",
  });
  const [generated, committed] = await Promise.all([
    readFile(generatedPath),
    readFile(committedPath),
  ]);
  if (!generated.equals(committed)) {
    console.error("[FAIL] Generated OpenAPI types are stale.");
    console.error("Run: npm --prefix spa-web run gen:api");
    process.exitCode = 1;
  } else {
    console.log("[PASS] Generated OpenAPI types are up to date.");
  }
} finally {
  await rm(temporaryDir, { recursive: true, force: true });
}
