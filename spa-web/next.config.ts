import path from "node:path";
import type { NextConfig } from "next";

function getE2eDistDir(): string | undefined {
  const configuredDistDir = process.env.OKR_E2E_NEXT_DIST_DIR?.trim();
  if (!configuredDistDir) {
    return undefined;
  }

  const projectRoot = process.cwd();
  const resolvedDistDir = path.resolve(projectRoot, configuredDistDir);
  const projectRelativeDistDir = path.relative(projectRoot, resolvedDistDir);
  if (
    !projectRelativeDistDir ||
    projectRelativeDistDir === ".." ||
    projectRelativeDistDir.startsWith(`..${path.sep}`) ||
    path.isAbsolute(projectRelativeDistDir)
  ) {
    throw new Error("OKR_E2E_NEXT_DIST_DIR must stay inside the spa-web project.");
  }

  return projectRelativeDistDir;
}

const e2eDistDir = getE2eDistDir();
const nextConfig: NextConfig = {
  // Next dev replays effects in Strict Mode; keep the waterfall's session
  // count representative of production while this isolated E2E config is set.
  ...(e2eDistDir
    ? { distDir: e2eDistDir, reactStrictMode: false }
    : {}),
  outputFileTracingRoot: path.join(process.cwd(), ".."),
};

export default nextConfig;
