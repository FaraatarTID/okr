import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { policySignatures } from "../src/allowlist.js";

function extractDocSignatures(markdown: string): string[] {
  const marker = "### Allowlist Signatures (Machine-Checked)";
  const markerIndex = markdown.indexOf(marker);
  if (markerIndex < 0) {
    throw new Error("Contract inventory marker section not found.");
  }

  const afterMarker = markdown.slice(markerIndex + marker.length);
  const fenceStart = afterMarker.indexOf("```text");
  if (fenceStart < 0) {
    throw new Error("Allowlist signature code block start not found.");
  }
  const contentStart = fenceStart + "```text".length;
  const fenceEnd = afterMarker.indexOf("```", contentStart);
  if (fenceEnd < 0) {
    throw new Error("Allowlist signature code block end not found.");
  }

  const content = afterMarker.slice(contentStart, fenceEnd);
  return content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("#"))
    .sort();
}

describe("allowlist/docs drift guard", () => {
  it("keeps documented signatures aligned with bff allowlist policy", () => {
    const contractDocPath = resolve(
      process.cwd(),
      "..",
      "docs",
      "HYBRID_FRONTEND_API_CONTRACT_INVENTORY.md",
    );
    const markdown = readFileSync(contractDocPath, "utf-8");
    const documented = extractDocSignatures(markdown);
    const allowlisted = policySignatures();
    expect(documented).toEqual(allowlisted);
  });
});

