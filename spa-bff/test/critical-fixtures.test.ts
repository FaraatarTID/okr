import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { isAllowlistedRoute } from "../src/allowlist.js";

interface FixtureManifestEntry {
  id: string;
  method: string;
  path: string;
  request: string;
  response: string;
}

function readJson<T>(path: string): T {
  const content = readFileSync(path, "utf-8").replace(/^\uFEFF/, "");
  return JSON.parse(content) as T;
}

describe("hybrid frontend critical fixture policy", () => {
  const fixtureDir = resolve(process.cwd(), "..", "docs", "fixtures", "hybrid_frontend");
  const manifestPath = resolve(fixtureDir, "manifest.json");
  const manifest = readJson<FixtureManifestEntry[]>(manifestPath);

  it("keeps every critical fixture endpoint allowlisted", () => {
    expect(Array.isArray(manifest)).toBe(true);
    expect(manifest.length).toBeGreaterThan(0);

    for (const entry of manifest) {
      expect(entry.id).toBeTruthy();
      expect(entry.method).toBeTruthy();
      expect(entry.path.startsWith("/v1/")).toBe(true);
      expect(isAllowlistedRoute(entry.method, entry.path)).toBe(true);
    }
  });

  it("ensures request/response fixture files are valid JSON objects", () => {
    for (const entry of manifest) {
      const requestPayload = readJson<unknown>(resolve(fixtureDir, entry.request));
      const responsePayload = readJson<unknown>(resolve(fixtureDir, entry.response));

      expect(requestPayload).toBeTypeOf("object");
      expect(requestPayload).not.toBeNull();
      expect(responsePayload).toBeTypeOf("object");
      expect(responsePayload).not.toBeNull();
    }
  });
});
