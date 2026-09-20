import { describe, expect, it } from "vitest";

import { modeForLocation, modeForPath } from "@/components/atlas-shell/navigation";

/**
 * `modeForLocation` is shared by the shell's boot sync and its navigation
 * watcher, so these cases pin the contract both rely on (C8).
 */
describe("modeForLocation", () => {
  it("uses the path when the query carries no mode", () => {
    expect(modeForLocation("/weekly", "")).toBe("weekly");
    expect(modeForLocation("/daily", "")).toBe("daily");
    expect(modeForLocation("/timeline", "")).toBe("timeline");
    expect(modeForLocation("/retrobox", "")).toBe("retrobox");
    expect(modeForLocation("/admin", "")).toBe("admin");
    expect(modeForLocation("/dashboard", "")).toBe("dashboard");
    expect(modeForLocation("/check-in", "")).toBe("ritual");
    expect(modeForLocation("/ritual", "")).toBe("ritual");
    expect(modeForLocation("/", "")).toBe("atlas");
  });

  it("lets an explicit mode parameter outrank the path", () => {
    expect(modeForLocation("/weekly", "?mode=timeline")).toBe("timeline");
    expect(modeForLocation("/admin", "?mode=atlas")).toBe("atlas");
  });

  it("accepts the check-in alias in the query", () => {
    expect(modeForLocation("/", "?mode=check-in")).toBe("ritual");
  });

  it("falls back to the path for an unknown or empty mode parameter", () => {
    expect(modeForLocation("/daily", "?mode=not-a-mode")).toBe("daily");
    expect(modeForLocation("/daily", "?mode=")).toBe("daily");
    expect(modeForLocation("/daily", "?mode=%20")).toBe("daily");
  });

  it("falls back to the default mode for an unknown path", () => {
    expect(modeForLocation("/does-not-exist", "")).toBe("atlas");
  });

  it("handles a query string with or without the leading question mark", () => {
    expect(modeForLocation("/weekly", "mode=timeline")).toBe("timeline");
    expect(modeForLocation("/weekly", "?mode=timeline")).toBe("timeline");
  });

  it("keeps modeForPath behaviour unchanged for the shell's path mapping", () => {
    expect(modeForPath("/check-in")).toBe("ritual");
    expect(modeForPath("/ritual")).toBe("ritual");
    expect(modeForPath("/unknown")).toBe("atlas");
  });
});
