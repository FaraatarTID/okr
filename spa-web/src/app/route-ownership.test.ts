import { readFileSync } from "node:fs";
import { readdir } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * Structural guard for C8: the shell must be mounted once by a shared layout,
 * never by an individual route.
 *
 * The defect this fences: eight sibling routes each rendered their own
 * `<AtlasShell />`, so every navigation unmounted and re-booted the entire shell
 * (all 2268 lines of state, the auth bootstrap, and the snapshot lifecycle).
 * Nothing failed when that pattern was introduced, and nothing would fail if it
 * came back, so this test asserts the structure instead of the behaviour.
 *
 * If a route needs the shell, put the route inside the `(shell)` group; the
 * group's layout already renders it.
 */

const appDirectory = dirname(fileURLToPath(import.meta.url));

/** Routes that must stay outside the shell group, with the reason. */
const SHELL_FREE_ROUTES = ["login", "ritual"];

async function collectPageFiles(directory: string): Promise<string[]> {
  const found: string[] = [];
  const entries = await readdir(directory, { withFileTypes: true });
  for (const entry of entries) {
    const full = join(directory, entry.name);
    if (entry.isDirectory()) {
      found.push(...(await collectPageFiles(full)));
    } else if (entry.name === "page.tsx") {
      found.push(full);
    }
  }
  return found;
}

/** The path segments between the app root and the page file. */
function routeSegments(pageFile: string): string[] {
  return relative(appDirectory, dirname(pageFile))
    .split(/[\\/]/)
    .filter(Boolean);
}

function displayPath(pageFile: string): string {
  return relative(appDirectory, pageFile).replace(/\\/g, "/");
}

describe("route ownership of AtlasShell", () => {
  it("no route renders AtlasShell directly; only the shared layout may", async () => {
    const offenders: string[] = [];

    for (const pageFile of await collectPageFiles(appDirectory)) {
      if (/AtlasShell/.test(readFileSync(pageFile, "utf8"))) {
        offenders.push(displayPath(pageFile));
      }
    }

    expect(
      offenders,
      "These routes render AtlasShell themselves, so the shell remounts on every " +
        "navigation between them. Move the route into the (shell) group instead and " +
        "let (shell)/layout.tsx own the single mount.",
    ).toEqual([]);
  });

  it("the shell group exists, renders the shell, and owns the eight app routes", async () => {
    const layoutSource = readFileSync(
      join(appDirectory, "(shell)", "layout.tsx"),
      "utf8",
    );
    expect(layoutSource).toContain("AtlasShell");

    const grouped = (await collectPageFiles(join(appDirectory, "(shell)")))
      .map((pageFile) => routeSegments(pageFile).slice(1).join("/"))
      .sort();
    expect(grouped).toEqual([
      "",
      "admin",
      "check-in",
      "daily",
      "dashboard",
      "retrobox",
      "timeline",
      "weekly",
    ]);
  });

  it("only the documented shell-free routes sit outside the group", async () => {
    const outside = (await collectPageFiles(appDirectory))
      .filter((pageFile) => !routeSegments(pageFile).includes("(shell)"))
      .map((pageFile) => routeSegments(pageFile).join("/"))
      .filter((route) => route !== "" && route !== "api")
      .sort();
    expect(outside).toEqual([...SHELL_FREE_ROUTES].sort());
  });
});
